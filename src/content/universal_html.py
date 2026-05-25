"""Universal HTML to Markdown loader.

Uses httpx for straightforward pages; falls back to a best-effort extraction.
Heavy headless-browser scraping (nodriver) is optional and requires an installed
Chromium/Chrome binary. We try httpx first for speed, then nodriver if available.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_SKIP_EXTENSIONS = re.compile(
    r"\.(pdf|zip|tar|gz|bz2|xz|7z|rar|exe|dmg|pkg|deb|rpm|mp4|mp3|mov|avi|mkv|iso)$",
    re.IGNORECASE,
)
_MAX_HTML_BYTES = 5 * 1024 * 1024  # 5 MB
_TRUNCATE_CHARS = 80_000


def _should_skip(url: str) -> bool:
    path = urlparse(url).path or ""
    return bool(_SKIP_EXTENSIONS.search(path))


def _html_to_markdown(html: str, url: str) -> str:
    """Convert HTML to LLM-friendly Markdown.

    Strategy:
    1. Try trafilatura (semantic extraction - filters boilerplate).
    2. Fall back to markdownify on full HTML (preserves structure).
    """
    # Try trafilatura first
    try:
        import trafilatura  # type: ignore[import-untyped]
        result = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="markdown",
            url=url,
        )
        if result and len(result.strip()) > 200:
            return _truncate(result)
    except Exception as exc:
        logger.debug("trafilatura failed: %s", exc)

    # Fall back to markdownify on cleaned HTML
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]
        from markdownify import markdownify  # type: ignore[import-untyped]

        soup = BeautifulSoup(html, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        body = soup.find("main") or soup.find("article") or soup.find("body") or soup
        clean_html = str(body)
        md = markdownify(clean_html, heading_style="ATX", bullets="*")
        # Collapse excessive blank lines
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        return _truncate(md)
    except Exception as exc:
        logger.debug("markdownify failed: %s", exc)

    return f"_Could not extract content from this page._\n\nSource: {url}\n"


def _truncate(text: str) -> str:
    if len(text) <= _TRUNCATE_CHARS:
        return text
    return text[:_TRUNCATE_CHARS] + "\n\n_[Content truncated for context efficiency]_"


async def _fetch_with_httpx(url: str) -> str | None:
    """Attempt a plain HTTP GET, return raw HTML text or None on failure."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; mcp-web-search/1.0; +https://github.com/you/mcp-web-search)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    timeout_raw = os.environ.get("HTML_TOTAL_TIMEOUT_SECONDS", "20").strip()
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 20.0

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                return None
            # Decode up to size limit
            raw = resp.content[:_MAX_HTML_BYTES]
            return raw.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.debug("httpx fetch failed for %s: %s", url, exc)
        return None



async def load_url_as_markdown(
    url: str,
    *,
    diagnostics: Any | None = None,  # Diagnostics | None
) -> str | None:
    """
    Load a URL and return LLM-ready Markdown.

    Returns None for URLs that should be skipped (binary files, PDFs, etc.).
    Returns a descriptive error string if extraction fails.
    """
    if _should_skip(url):
        if diagnostics:
            diagnostics.emit("html.skip", "Skipping non-HTML URL", {"url": url})
        return None

    if diagnostics:
        diagnostics.emit("html.start", "Starting HTML fetch", {"url": url, "method": "httpx"})

    # Attempt 1: plain httpx (fast, no JS)
    html = await _fetch_with_httpx(url)

    if html:
        if diagnostics:
            diagnostics.emit("html.fetched", "Fetched via httpx", {"html_len": len(html)})
        md = _html_to_markdown(html, url)
        if diagnostics:
            diagnostics.emit("html.converted", "Converted to Markdown", {"md_len": len(md)})
        return f"{md}\n\nSource: {url}\n"

    if diagnostics:
        diagnostics.emit("html.failed", "All fetch methods failed", {"url": url})

    return f"_Could not retrieve content from: {url}_\n\nSource: {url}\n"
