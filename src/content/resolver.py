"""Content resolution pipeline.

Routes URLs to specialized handlers before falling back to the universal HTML loader.

Stage 1: StackExchange API
Stage 2: GitHub Issues API
Stage 3: Wikipedia API
Stage 4: arXiv Atom API
Stage 5: Universal HTML loader (httpx → nodriver headless browser)
"""
from __future__ import annotations

from typing import Any

from .stackexchange import (
    StackExchangeError,
    fetch_stackexchange_thread_markdown,
    parse_stackexchange_url,
)
from .github_issues import (
    GitHubIssueError,
    fetch_github_issue_thread_markdown,
    parse_github_issue_url,
)
from .wikipedia import (
    WikipediaError,
    fetch_wikipedia_article_markdown,
    parse_wikipedia_url,
)
from .arxiv import (
    ArxivError,
    fetch_arxiv_paper_markdown,
    parse_arxiv_url,
)
from .universal_html import load_url_as_markdown


async def resolve_page_content_markdown(
    url: str,
    *,
    diagnostics: Any | None = None,  # Diagnostics | None
) -> str | None:
    """
    Resolve a URL to LLM-ready Markdown.

    Returns None for unsupported/skipped content (e.g. binary files).
    Always returns a string for parseable pages — errors become descriptive Markdown notes.
    """
    if diagnostics:
        diagnostics.emit("resolver.start", "Resolving URL", {"url": url})

    # ── Stage 1: StackExchange ──────────────────────────────────────────────
    try:
        parse_stackexchange_url(url)
    except StackExchangeError:
        pass
    else:
        if diagnostics:
            diagnostics.emit("resolver.route", "Matched StackExchange", {"handler": "stackexchange"})
        try:
            return await fetch_stackexchange_thread_markdown(url)
        except Exception as exc:
            if diagnostics:
                diagnostics.emit(
                    "resolver.error", "StackExchange handler failed",
                    {"handler": "stackexchange", "error": type(exc).__name__},
                )
            return f"_Failed to retrieve StackExchange content: {type(exc).__name__}_\n\nSource: {url}\n"

    # ── Stage 2: GitHub Issues ──────────────────────────────────────────────
    try:
        parse_github_issue_url(url)
    except GitHubIssueError:
        pass
    else:
        if diagnostics:
            diagnostics.emit("resolver.route", "Matched GitHub Issue", {"handler": "github_issue"})
        try:
            return await fetch_github_issue_thread_markdown(url)
        except Exception:
            if diagnostics:
                diagnostics.emit(
                    "resolver.fallback",
                    "GitHub Issue handler failed; falling back to HTML",
                    {"handler": "github_issue"},
                )
            fallback = await load_url_as_markdown(url, diagnostics=diagnostics)
            if fallback is not None:
                return fallback
            return f"_Failed to retrieve GitHub Issue content._\n\nSource: {url}\n"

    # ── Stage 3: Wikipedia ──────────────────────────────────────────────────
    try:
        parse_wikipedia_url(url)
    except WikipediaError:
        pass
    else:
        if diagnostics:
            diagnostics.emit("resolver.route", "Matched Wikipedia", {"handler": "wikipedia"})
        try:
            return await fetch_wikipedia_article_markdown(url)
        except Exception:
            if diagnostics:
                diagnostics.emit(
                    "resolver.fallback",
                    "Wikipedia handler failed; falling back to HTML",
                    {"handler": "wikipedia"},
                )
            fallback = await load_url_as_markdown(url, diagnostics=diagnostics)
            if fallback is not None:
                return fallback
            return f"_Failed to retrieve Wikipedia content._\n\nSource: {url}\n"

    # ── Stage 4: arXiv ──────────────────────────────────────────────────────
    try:
        parse_arxiv_url(url)
    except ArxivError:
        pass
    else:
        if diagnostics:
            diagnostics.emit("resolver.route", "Matched arXiv", {"handler": "arxiv"})
        try:
            return await fetch_arxiv_paper_markdown(url)
        except Exception as exc:
            if diagnostics:
                diagnostics.emit(
                    "resolver.error", "arXiv handler failed",
                    {"handler": "arxiv", "error": type(exc).__name__},
                )
            return f"_Failed to retrieve arXiv content: {type(exc).__name__}_\n\nSource: {url}\n"

    # ── Stage 5: Universal HTML ─────────────────────────────────────────────
    if diagnostics:
        diagnostics.emit("resolver.route", "Falling back to universal HTML", {"handler": "html"})
    return await load_url_as_markdown(url, diagnostics=diagnostics)
