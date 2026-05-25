"""Tests for the search provider router."""
import os
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from src.search import search_web, WebSearchProviderError
from src.models import WebSearchResult


def _mock_result(n: int = 1) -> list[WebSearchResult]:
    return [
        WebSearchResult(title=f"T{i}", link=f"https://example{i}.com", snippet="s", page_content="")
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_raises_when_no_provider_configured(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_BASE_URL", raising=False)
    with pytest.raises(WebSearchProviderError):
        await search_web("test", num_results=3)


@pytest.mark.asyncio
async def test_uses_serper_when_key_present(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "fake-key")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_BASE_URL", raising=False)

    mock_results = _mock_result(2)
    with patch("src.search.search_serper", new=AsyncMock(return_value=mock_results)):
        results = await search_web("python asyncio", num_results=2)
    assert results == mock_results


@pytest.mark.asyncio
async def test_uses_tavily_when_serper_missing(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "fake-tavily")
    monkeypatch.delenv("SEARXNG_BASE_URL", raising=False)

    mock_results = _mock_result(1)
    with patch("src.search.search_tavily", new=AsyncMock(return_value=mock_results)):
        results = await search_web("test", num_results=1)
    assert results == mock_results


@pytest.mark.asyncio
async def test_uses_searxng_as_last_resort(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("SEARXNG_BASE_URL", "https://searx.example.org")

    mock_results = _mock_result(3)
    with patch("src.search.search_searxng", new=AsyncMock(return_value=mock_results)):
        results = await search_web("test", num_results=3)
    assert results == mock_results
