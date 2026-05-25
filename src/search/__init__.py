"""Search provider router: Serper → Tavily → SerpApi → SearXNG (strict order, no cross-fallback)."""
from __future__ import annotations

import os
from typing import Awaitable, Callable

import httpx

from ..models import WebSearchResult
from ..utils.diagnostics import Diagnostics
from .searxng import search_searxng
from .serper import search_serper
from .serpapi import search_serpapi
from .tavily import search_tavily


class WebSearchProviderError(RuntimeError):
    pass


def _has_serper() -> bool:
    return bool(os.environ.get("SERPER_API_KEY", "").strip())


def _has_serpapi() -> bool:
    return bool(os.environ.get("SERPAPI_API_KEY", "").strip())


def _has_tavily() -> bool:
    return bool(os.environ.get("TAVILY_API_KEY", "").strip())


def _has_searxng() -> bool:
    return bool(os.environ.get("SEARXNG_BASE_URL", "").strip())


async def search_web(
    query: str,
    *,
    num_results: int,
    http_client: httpx.AsyncClient | None = None,
    diagnostics: Diagnostics | None = None,
) -> list[WebSearchResult]:
    """
    Route to the first configured provider.

    Priority (strict): Serper → Tavily → serpapi → SearXNG.
    No cross-provider fallback — if the chosen provider fails, the error propagates.
    """
    has_serper = _has_serper()
    has_tavily = _has_tavily()
    has_searxng = _has_searxng()
    has_serpapi = _has_serpapi()

    if not has_serper and not has_serpapi and not has_tavily and not has_searxng:
        raise WebSearchProviderError(
            "No search provider configured. Set SERPER_API_KEY, SERPAPI_API_KEY, "
            "TAVILY_API_KEY, or SEARXNG_BASE_URL."
        )

    provider: Callable[..., Awaitable[list[WebSearchResult]]]
    if has_serper:
        provider = search_serper
        provider_name = "serper"
    elif has_tavily:
        provider = search_tavily
        provider_name = "tavily"
    elif has_serpapi:
        provider = search_serpapi
        provider_name = "serpapi" 
    else:
        provider = search_searxng
        provider_name = "searxng"

    if diagnostics:
        diagnostics.emit(
            "search.provider_select",
            "Selected search provider",
            {
                "provider": provider_name,
                "query": query,
                "num_results": num_results,
                "has_serper": has_serper,
                "has_serpapi": has_serpapi,
                "has_tavily": has_tavily,
                "has_searxng": has_searxng,
            },
        )

    async def _run(client: httpx.AsyncClient) -> list[WebSearchResult]:
        return await provider(query, num_results=num_results, http_client=client)

    if http_client is not None:
        return await _run(http_client)

    async with httpx.AsyncClient(timeout=30) as client:
        return await _run(client)
