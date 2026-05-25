"""Unit tests for the Serper search provider."""
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.search.serper import search_serper, SerperConfigError


SERPER_RESPONSE = {
    "organic": [
        {"title": "Python Official", "link": "https://python.org", "snippet": "Welcome to Python."},
        {"title": "Real Python", "link": "https://realpython.com", "snippet": "Learn Python."},
    ]
}
SERPAPI_RESPONSE = {
    "organic_results": [
        {"title": "Python Official", "link": "https://python.org", "snippet": "Welcome to Python."},
        {"title": "Real Python", "link": "https://realpython.com", "snippet": "Learn Python."},
    ]
}


@pytest.mark.asyncio
async def test_raises_config_error_without_key(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    with pytest.raises(SerperConfigError):
        await search_serper("python", num_results=3)


@pytest.mark.asyncio
async def test_returns_empty_for_blank_query(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "fake-key")
    results = await search_serper("  ", num_results=3)
    assert results == []

@pytest.mark.asyncio
async def test_parses_serpapi_results(monkeypatch, respx_mock):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.setenv("SERPAPI_API_KEY", "fake-key")
    respx_mock.get("https://serpapi.com/search.json").mock(
        return_value=httpx.Response(200, json=SERPAPI_RESPONSE)
    )
    results = await search_serper("python", num_results=5)
    assert len(results) == 2
    assert results[0].title == "Python Official"
    assert results[0].link == "https://python.org"
    assert results[0].snippet == "Welcome to Python."
    assert results[0].page_content == ""


@pytest.mark.asyncio
async def test_parses_organic_results(monkeypatch, respx_mock):
    monkeypatch.setenv("SERPER_API_KEY", "fake-key")
    respx_mock.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(200, json=SERPER_RESPONSE)
    )
    results = await search_serper("python", num_results=5)
    assert len(results) == 2
    assert results[0].title == "Python Official"
    assert results[0].link == "https://python.org"
    assert results[0].snippet == "Welcome to Python."
    assert results[0].page_content == ""


@pytest.mark.asyncio
async def test_respects_num_results_limit(monkeypatch, respx_mock):
    monkeypatch.setenv("SERPER_API_KEY", "fake-key")
    respx_mock.post("https://google.serper.dev/search").mock(
        return_value=httpx.Response(200, json=SERPER_RESPONSE)
    )
    results = await search_serper("python", num_results=1)
    assert len(results) == 1
