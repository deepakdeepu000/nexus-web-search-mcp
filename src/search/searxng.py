"""SearXNG self-hosted search engine provider."""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urljoin

import httpx

from ..models import WebSearchResult


class SearXNGError(RuntimeError):
    pass


class SearXNGConfigError(SearXNGError):
    pass


def _get_base_url() -> str:
    url = os.environ.get("SEARXNG_BASE_URL", "").strip().rstrip("/")
    if not url:
        raise SearXNGConfigError(
            "SEARXNG_BASE_URL is not set. Point it at your SearXNG instance, "
            "e.g. https://searx.example.org"
        )
    return url


def _build_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    # Optional custom User-Agent
    ua = os.environ.get("SEARXNG_USER_AGENT", "").strip()
    if ua:
        headers["User-Agent"] = ua

    # Optional extra headers from JSON env var
    raw_extra = os.environ.get("SEARXNG_HEADERS_JSON", "").strip()
    if raw_extra:
        try:
            extra = json.loads(raw_extra)
            if isinstance(extra, dict):
                headers.update({str(k): str(v) for k, v in extra.items()})
        except (ValueError, TypeError):
            pass

    return headers


def _build_params(query: str, num_results: int) -> dict[str, Any]:
    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "pageno": 1,
    }
    language = os.environ.get("SEARXNG_LANGUAGE", "").strip()
    if language:
        params["language"] = language

    categories = os.environ.get("SEARXNG_CATEGORIES", "").strip()
    if categories:
        params["categories"] = categories

    engines = os.environ.get("SEARXNG_ENGINES", "").strip()
    if engines:
        params["engines"] = engines

    time_range = os.environ.get("SEARXNG_TIME_RANGE", "").strip()
    if time_range:
        params["time_range"] = time_range

    safesearch_raw = os.environ.get("SEARXNG_SAFESEARCH", "").strip()
    if safesearch_raw:
        try:
            params["safesearch"] = int(safesearch_raw)
        except ValueError:
            pass

    return params


async def search_searxng(
    query: str,
    *,
    num_results: int,
    http_client: httpx.AsyncClient | None = None,
) -> list[WebSearchResult]:
    """
    Query a self-hosted SearXNG instance.

    Endpoint: GET <SEARXNG_BASE_URL>/search?q=...&format=json
    """
    if not query.strip() or num_results < 1:
        return []

    base_url = _get_base_url()
    endpoint = urljoin(base_url + "/", "search")
    headers = _build_headers()
    params = _build_params(query, num_results)

    timeout_raw = os.environ.get("SEARXNG_TIMEOUT_SECONDS", "30").strip()
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 30.0

    async def _request(client: httpx.AsyncClient) -> dict[str, Any]:
        resp = await client.get(endpoint, headers=headers, params=params)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            raise SearXNGError("SearXNG returned non-JSON response.") from exc
        if not isinstance(data, dict):
            raise SearXNGError("SearXNG response was not a JSON object.")
        return data

    if http_client is not None:
        data = await _request(http_client)
    else:
        async with httpx.AsyncClient(timeout=timeout) as client:
            data = await _request(client)

    raw_results = data.get("results", [])
    if not isinstance(raw_results, list):
        return []

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
