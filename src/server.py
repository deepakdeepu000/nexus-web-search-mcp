"""MCP Web Search Server.

Exposes two MCP tools:
  - web_search(query, num_results) → search + content extraction
  - get_content(url)               → fetch & extract a single URL
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .models import GetContentResponse, WebSearchResponse
from .content.resolver import resolve_page_content_markdown
from .search import search_web
from .utils.diagnostics import (
    Diagnostics,
    MAX_SAMPLE_CHARS,
    diagnostics_enabled,
    mask_env_values,
    new_request_id,
    sample_data,
)
from .utils.logging import configure_logging

configure_logging()
LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "mcp-web-search",
    instructions=(
        "Web search via Serper (default), Tavily, or a self-hosted SearXNG instance. "
        "Results are enriched with best-effort page extraction into LLM-ready Markdown."
    ),
)

Transport = Literal["stdio", "sse", "streamable-http"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_int_env(key: str, default: int) -> int:
    raw = (os.environ.get(key) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _get_float_env(key: str, default: float) -> float:
    raw = (os.environ.get(key) or "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _resolve_tool_timeout() -> float:
    value = _get_float_env("TOOL_TOTAL_TIMEOUT_SECONDS", 120.0)
    max_value = _get_float_env("TOOL_TOTAL_TIMEOUT_MAX_SECONDS", 600.0)
    return max(1.0, min(value, max(1.0, max_value)))


def _resolve_concurrency(num_results: int) -> int:
    raw = (os.environ.get("WEB_SEARCH_MAX_CONCURRENCY") or "").strip()
    value = 3
    if raw:
        try:
            parsed = int(raw)
            if parsed > 0:
                value = parsed
        except ValueError:
            pass
    value = max(1, min(value, 5))
    if num_results > 0:
        value = min(value, num_results)
    return value


def _timeout_note(url: str, *, scope: str | None = None) -> str:
    detail = f": {scope}" if scope else ""
    return f"_Failed to retrieve page content: TimeoutError{detail}_\n\nSource: {url}\n"


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def web_search(query: str, num_results: int = 3) -> dict:
    """Search the web and return top results with best-effort Markdown for each URL.

    Use this as the primary tool for web search. Especially useful for:
    - Debugging errors (search the exact error message or stack trace).
    - Verifying API signatures and breaking changes.
    - Checking current package versions and release notes.
    - Finding GitHub issues, StackOverflow threads, or authoritative references.

    If you already have a specific URL, prefer `get_content(url)` instead.

    Args:
        query: Search query string. Be specific; prefer exact error text where relevant.
        num_results: Number of results to return (1–5 recommended). Default: 3.

    Prerequisites:
        At least one env var must be set: SERPER_API_KEY, TAVILY_API_KEY, or SEARXNG_BASE_URL.

    Returns:
        {"results": [{"title": str, "link": str, "snippet": str, "page_content": str}, ...]}
    """
    started = time.monotonic()
    diag_enabled = diagnostics_enabled()
    parent_id = new_request_id() if diag_enabled else ""
    parent_diag = Diagnostics(parent_id, diag_enabled, stream=sys.stderr)

    if diag_enabled:
        env_snap = {
            "SERPER_API_KEY": os.environ.get("SERPER_API_KEY", ""),
            "SERPAPI_API_KEY": os.environ.get("SERPAPI_API_KEY", ""),
            "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY", ""),
            "SEARXNG_BASE_URL": os.environ.get("SEARXNG_BASE_URL", ""),
            "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
            "TOOL_TOTAL_TIMEOUT_SECONDS": os.environ.get("TOOL_TOTAL_TIMEOUT_SECONDS", ""),
            "WEB_SEARCH_MAX_CONCURRENCY": os.environ.get("WEB_SEARCH_MAX_CONCURRENCY", ""),
        }
        parent_diag.emit(
            "web_search.start", "Starting web_search",
            {"query": query, "num_results": num_results, "env": mask_env_values(env_snap)},
        )


    total_budget = _resolve_tool_timeout()
    results = await search_web(query, num_results=num_results, diagnostics=parent_diag)

    if not results:
        return WebSearchResponse(results=[]).model_dump(exclude_none=True)

    concurrency = _resolve_concurrency(len(results))
    semaphore = asyncio.Semaphore(concurrency)

    if diag_enabled:
        parent_diag.emit(
            "web_search.concurrency", "Resolved concurrency",
            {"concurrency": concurrency, "total_budget_seconds": total_budget},
        )

    async def enrich_one(r):
        result_diag = None
        if diag_enabled:
            rid = new_request_id()
            result_diag = Diagnostics(
                rid, True, stream=sys.stderr,
                context={"parent_request_id": parent_id, "url": r.link},
            )
            result_diag.emit("content.start", "Starting content fetch", {"url": r.link})

        async with semaphore:
            remaining = total_budget - (time.monotonic() - started)
            if remaining <= 0:
                page_md = _timeout_note(r.link, scope="web_search time budget exceeded")
                if result_diag:
                    result_diag.emit("content.timeout", "Budget exceeded before fetch",
                                     {"remaining_seconds": remaining})
            else:
                try:
                    page_md = await asyncio.wait_for(
                        resolve_page_content_markdown(r.link, diagnostics=result_diag),
                        timeout=remaining,
                    )
                except asyncio.TimeoutError:
                    page_md = _timeout_note(r.link)
                    if result_diag:
                        result_diag.emit("content.timeout", "Content fetch timed out",
                                         {"remaining_seconds": remaining})
                except Exception as exc:
                    full = str(exc).strip()
                    short = (full[:200].rstrip() + "…") if len(full) > 200 else full
                    suffix = f": {type(exc).__name__}: {short}" if short else f": {type(exc).__name__}"
                    page_md = f"_Failed to retrieve page content{suffix}_\n\nSource: {r.link}\n"
                    if result_diag:
                        result_diag.emit("content.error", "Content fetch failed",
                                         {"error": type(exc).__name__, "detail": full})

            if page_md is None:
                page_md = (
                    "_Could not retrieve content (possibly a PDF or unsupported type)._"
                    f"\n\nSource: {r.link}\n"
                )
                if result_diag:
                    result_diag.emit("content.skip", "Content fetch skipped",
                                     {"reason": "probable PDF or unsupported type"})

            if result_diag:
                result_diag.emit("content.result", "Resolved content",
                                 {"content_len": len(page_md), **sample_data(page_md, MAX_SAMPLE_CHARS)})

            return r.model_copy(
                update={
                    "page_content": page_md,
                    "diagnostics": result_diag.entries if result_diag else None,
                }
            )

    enriched = await asyncio.gather(*(enrich_one(r) for r in results))
    return WebSearchResponse(results=enriched).model_dump(exclude_none=True)


@mcp.tool()
async def get_content(url: str) -> dict:
    """Fetch a single URL and return best-effort, LLM-ready Markdown for that page.

    Use this when you already have a specific URL to read. If you need to discover
    relevant URLs first, use `web_search(query)` instead.

    Specialized loaders are used for StackExchange, GitHub Issues, Wikipedia, and arXiv.
    All other pages use a universal HTML loader.

    Args:
        url: The URL to fetch and extract.

    Returns:
        {"url": str, "page_content": str}
    """
    timeout_seconds = _resolve_tool_timeout()
    diag_enabled = diagnostics_enabled()
    request_id = new_request_id() if diag_enabled else ""
    diag = Diagnostics(request_id, diag_enabled, stream=sys.stderr)

    if diag_enabled:
        env_snap = {
            "TOOL_TOTAL_TIMEOUT_SECONDS": os.environ.get("TOOL_TOTAL_TIMEOUT_SECONDS", ""),
            "BROWSER_EXECUTABLE_PATH": os.environ.get("BROWSER_EXECUTABLE_PATH", ""),
        }
        diag.emit("get_content.start", "Starting content fetch",
                  {"url": url, "env": mask_env_values(env_snap)})

    try:
        page_md = await asyncio.wait_for(
            resolve_page_content_markdown(url, diagnostics=diag),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        page_md = _timeout_note(url, scope="tool time budget exceeded")
        if diag_enabled:
            diag.emit("content.timeout", "Content fetch timed out",
                      {"timeout_seconds": timeout_seconds})
    except Exception as exc:
        full = str(exc).strip()
        short = (full[:200].rstrip() + "…") if len(full) > 200 else full
        suffix = f": {type(exc).__name__}: {short}" if short else f": {type(exc).__name__}"
        page_md = f"_Failed to retrieve page content{suffix}_\n\nSource: {url}\n"
        if diag_enabled:
            diag.emit("content.error", "Content fetch failed",
                      {"error": type(exc).__name__, "detail": full})

    if page_md is None:
        page_md = (
            "_Could not retrieve content for this URL (possibly a PDF or unsupported type)._"
            f"\n\nSource: {url}\n"
        )
        if diag_enabled:
            diag.emit("content.skip", "Content skipped", {"reason": "probable PDF"})

    if diag_enabled:
        diag.emit("content.result", "Resolved content",
                  {"content_len": len(page_md), **sample_data(page_md, MAX_SAMPLE_CHARS)})

    return GetContentResponse(
        url=url,
        page_content=page_md,
        diagnostics=diag.entries if diag_enabled else None,
    ).model_dump(exclude_none=True)


# ---------------------------------------------------------------------------
# CLI / entrypoint
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-web-search",
        description="MCP server: multi-provider web search + robust content retrieval.",
    )
    transport_group = parser.add_mutually_exclusive_group()
    transport_group.add_argument(
        "--transport", choices=("stdio", "sse", "streamable-http"),
        help="Transport to use (default: stdio).",
    )
    transport_group.add_argument(
        "--stdio", dest="transport", action="store_const", const="stdio",
        help="Run using stdio transport (default).",
    )
    transport_group.add_argument(
        "--sse", dest="transport", action="store_const", const="sse",
        help="Run using SSE transport.",
    )
    transport_group.add_argument(
        "--http", "--streamable-http", dest="transport", action="store_const",
        const="streamable-http", help="Run using Streamable HTTP transport.",
    )
    parser.add_argument("--host", default=None,
                        help="Bind host for HTTP/SSE transports (overrides FASTMCP_HOST).")
    parser.add_argument("--port", type=int, default=None,
                        help="Bind port for HTTP/SSE transports (overrides FASTMCP_PORT).")
    return parser


def _resolve_transport(raw: str | None) -> Transport:
    if raw in ("stdio", "sse", "streamable-http"):
        return raw  # type: ignore[return-value]
    return "stdio"


def main(argv: list[str] | None = None) -> None:
    """Entrypoint for the MCP server."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    transport = _resolve_transport(args.transport)

    # Guard: stdio over a real TTY almost always means the user ran the binary
    # directly in a terminal, which is not how MCP clients launch servers.
    if (
        transport == "stdio"
        and sys.stdin.isatty()
        and os.environ.get("MCP_ALLOW_TTY_STDIO", "").strip().lower() not in ("1", "true", "yes")
    ):
        print(
            "Error: --stdio transport is intended to be launched by an MCP client via stdin/stdout.",
            file=sys.stderr,
        )
        print("Tip: run with --http for manual testing.", file=sys.stderr)
        print("Override: set MCP_ALLOW_TTY_STDIO=1 to force stdio on a TTY.", file=sys.stderr)
        raise SystemExit(2)

    if not (
        os.environ.get("SERPER_API_KEY", "").strip()
        or os.environ.get("SERPAPI_API_KEY", "").strip()
        or os.environ.get("TAVILY_API_KEY", "").strip()
        or os.environ.get("SEARXNG_BASE_URL", "").strip()
    ):
        LOGGER.warning(
            "No search provider configured (SERPER_API_KEY, SERPAPI_API_KEY, TAVILY_API_KEY, or SEARXNG_BASE_URL). "
            "`web_search` calls will fail until one is provided."
        )

    if transport in ("sse", "streamable-http"):
        host = args.host or os.environ.get("FASTMCP_HOST", "127.0.0.1")
        port_raw = str(args.port) if args.port is not None else os.environ.get("FASTMCP_PORT", "8000")
        try:
            port = int(port_raw)
        except ValueError:
            port = 8000
        if hasattr(mcp, "settings"):
            for key, val in (("host", host), ("port", port)):
                if hasattr(mcp.settings, key):
                    setattr(mcp.settings, key, val)

    mcp.run(transport=transport)
