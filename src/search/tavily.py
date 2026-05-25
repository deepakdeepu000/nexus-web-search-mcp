"""Tavily Search API provider."""
from __future__ import annotations

import os
from typing import Any

import httpx

from ..models import WebSearchResult

TAVILY_ENDPOINT = "https://api.tavily.com/search"


class TavilyError(RuntimeError):
    pass


class TavilyConfigError(TavilyError):
    pass


def _get_api_key() -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise TavilyConfigError(
            "TAVILY_API_KEY is not set. Get a key at https://tavily.com"
        )
    return key


async def search_tavily(
    query: str,
    *,
    num_results: int,
    http_client: httpx.AsyncClient | None = None,
) -> list[WebSearchResult]:
    """
    Query Tavily Search API.

    Endpoint: POST https://api.tavily.com/search
    Auth: Authorization: Bearer <key>
    Docs: https://docs.tavily.com/documentation/api-reference/endpoint/search
    """
    if not query.strip() or num_results < 1:
        return []

    api_key = _get_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "query": query,
        "max_results": num_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }

    async def _request(client: httpx.AsyncClient) -> dict[str, Any]:
        resp = await client.post(TAVILY_ENDPOINT, headers=headers, json=payload)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            raise TavilyError("Tavily returned non-JSON response.") from exc
        if not isinstance(data, dict):
            raise TavilyError("Tavily response was not a JSON object.")
        return data

    if http_client is not None:
        data = await _request(http_client)
    else:
        async with httpx.AsyncClient(timeout=30) as client:
            data = await _request(client)

    raw_results = data.get("results", [])
    if not isinstance(raw_results, list):
        raise TavilyError("Tavily response missing `results` list.")

    results: list[WebSearchResult] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        link = item.get("url")
        snippet = item.get("content", "")
        if not isinstance(title, str) or not isinstance(link, str):
            continue
        results.append(
            WebSearchResult(title=title, link=link, snippet=snippet or "", page_content="")
        )
        if len(results) >= num_results:
            break

    return results

