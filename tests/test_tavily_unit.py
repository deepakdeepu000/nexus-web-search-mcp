"""Unit tests for the Tavily search provider."""
import pytest
import httpx

from src.search.tavily import search_tavily, TavilyConfigError


TAVILY_RESPONSE = {
    "results": [
        {"title": "Tavily Result 1", "url": "https://result1.com", "content": "First result."},
        {"title": "Tavily Result 2", "url": "https://result2.com", "content": "Second result."},
    ]
}


@pytest.mark.asyncio
async def test_raises_config_error_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(TavilyConfigError):
        await search_tavily("python", num_results=3)


@pytest.mark.asyncio
async def test_returns_empty_for_blank_query(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
    results = await search_tavily("", num_results=3)
    assert results == []


@pytest.mark.asyncio
async def test_parses_results(monkeypatch, respx_mock):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
    respx_mock.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(200, json=TAVILY_RESPONSE)
    )
    results = await search_tavily("python", num_results=5)
    assert len(results) == 2
    assert results[0].title == "Tavily Result 1"
    assert results[0].link == "https://result1.com"
    assert results[0].snippet == "First result."
    assert results[0].page_content == ""


@pytest.mark.asyncio
async def test_respects_num_results(monkeypatch, respx_mock):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
    respx_mock.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(200, json=TAVILY_RESPONSE)
    )
    results = await search_tavily("python", num_results=1)
    assert len(results) == 1
