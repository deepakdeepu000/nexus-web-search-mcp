"""Serper.dev Google Search API provider."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from ..models import WebSearchResult

logger = logging.getLogger(__name__)

SERPER_ENDPOINT = "https://google.serper.dev/search"


class SerperError(RuntimeError):
    pass


class SerperConfigError(SerperError):
    pass


def _get_api_key() -> str:
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if not key:
        raise SerperConfigError(
            "SERPER_API_KEY is not set. Get a free key at https://serper.dev"
        )
    return key


async def search_serper(
    query: str,
    *,
    num_results: int,
    http_client: httpx.AsyncClient | None = None,
) -> list[WebSearchResult]:
    if not query.strip() or num_results < 1:
        return []

    api_key = _get_api_key()
    logger.debug(f"Searching Serper for query: {query!r} with num_results={num_results}")
    logger.debug(f"Using SERPER_API_KEY: {api_key[:4]}***")
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload: dict[str, Any] = {"q": query}

    async def _request(client: httpx.AsyncClient) -> dict[str, Any]:
        resp = await client.post(SERPER_ENDPOINT, headers=headers, json=payload)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            logger.error("Serper returned non-JSON response.")
            raise SerperError("Serper returned non-JSON response.") from exc
        if not isinstance(data, dict):
            logger.error("Serper response was not a JSON object.")
            raise SerperError("Serper response was not a JSON object.")
        return data

    if http_client is not None:
        data = await _request(http_client)
    else:
        async with httpx.AsyncClient(timeout=30) as client:
            data = await _request(client)

    organic = data.get("organic", [])
    if not isinstance(organic, list):
        return []

    results: list[WebSearchResult] = []
    for item in organic:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        link = item.get("link")
        snippet = item.get("snippet", "")
        if not isinstance(title, str) or not isinstance(link, str):
            continue
        results.append(
            WebSearchResult(title=title, link=link, snippet=snippet or "", page_content="")
        )
        if len(results) >= num_results:
            break

    return results

