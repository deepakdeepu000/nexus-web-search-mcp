"""Unit tests for the SerpApi search provider."""

from __future__ import annotations

import httpx
import pytest

from src.search.serpapi import SerpApiConfigError, search_serpapi


SERPAPI_RESPONSE = {
    "search_metadata": {
        "id": "abc123",
        "status": "Success",
        "google_url": "https://www.google.com/search?q=Coffee",
        "total_time_taken": 0.86,
    },
    "search_parameters": {
        "engine": "google",
        "q": "Coffee",
        "location_requested": "Austin, Texas, United States",
        "location_used": "Austin,Texas,United States",
        "google_domain": "google.com",
        "device": "desktop",
    },
    "search_information": {
        "query_displayed": "Coffee",
        "total_results": 3140000000,
        "time_taken_displayed": 0.34,
        "organic_results_state": "Results for exact spelling",
        "results_for": "Austin, TX",
    },
    "local_results": {
        "places": [
            {
                "title": "Houndstooth Coffee",
                "type": "Coffee shop",
                "address": "401 Congress Ave. #100c",
                "rating": 4.5,
                "reviews": 1200,
                "price": "$1-10",
                "description": "Cozy hangout for carefully sourced brews",
            }
        ]
    },
    "knowledge_graph": {
        "title": "Coffee",
        "type": "Beverages",
        "kgmid": "/m/02vqfm",
        "description": "Coffee is a beverage brewed from roasted, ground coffee beans.",
        "source": {
            "name": "Wikipedia",
            "link": "https://en.wikipedia.org/wiki/Coffee",
        },
    },
    "related_questions": [
        {
            "title": "What is the 80/20 rule for coffee?",
            "snippet": "Focus on water temperature and grind size.",
            "link": "https://example.com/q1",
        }
    ],
    "perspectives": [
        {
            "author": "Lance Hedrick",
            "source": "YouTube",
            "title": "I Changed My Mind About Coffee",
            "link": "https://youtube.com/watch?v=vhdk2KuWVbc",
            "date": "4 days ago",
        }
    ],
    "related_searches": [
        {"query": "Coffee nearby", "link": "https://example.com/nearby"}
    ],
    "refine_this_search": [
        {"query": "Whole Bean", "link": "https://example.com/whole-bean"}
    ],
    "refine_search_filters": [
        {
            "type": "Type",
            "options": [{"title": "Ground", "link": "https://example.com/ground"}],
        }
    ],
    "things_to_know": {
        "buttons": [
            {
                "text": "Health Benefits",
                "title": "9 Health Benefits of Coffee",
                "link": "https://example.com/benefits",
                "snippet": "Coffee may benefit heart health.",
            }
        ]
    },
    "pagination": {"current": 1, "next": "https://example.com/page2"},
    "serpapi_pagination": {"current": 1, "next_link": "https://example.com/api-page2"},
    "organic_results": [
        {
            "position": 1,
            "title": "Coffee",
            "link": "https://en.wikipedia.org/wiki/Coffee",
            "snippet": "Coffee is a beverage brewed from roasted, ground coffee beans.",
            "source": "Wikipedia",
            "displayed_link": "en.wikipedia.org/wiki/Coffee",
            "sitelinks": {"inline": [{"title": "History of coffee", "link": "https://en.wikipedia.org/wiki/History_of_coffee"}]},
        },
        {
            "position": 2,
            "title": "Austin Coffee Shops",
            "link": "https://example.com/austin-coffee",
            "snippet": "Austin's coffee shops feature gourmet coffee and rotating selections.",
            "source": "Visit Austin, Texas",
        },
    ],
}


@pytest.mark.asyncio
async def test_raises_config_error_without_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    with pytest.raises(SerpApiConfigError):
        await search_serpapi("Coffee", num_results=2)


@pytest.mark.asyncio
async def test_includes_serpapi_context_in_first_result(monkeypatch, respx_mock):
    monkeypatch.setenv("SERPAPI_API_KEY", "fake-key")
    respx_mock.get("https://serpapi.com/search.json").mock(
        return_value=httpx.Response(200, json=SERPAPI_RESPONSE)
    )

    results = await search_serpapi("Coffee", num_results=2)

    assert len(results) == 2
    assert results[0].title == "Coffee"
    assert results[0].link == "https://en.wikipedia.org/wiki/Coffee"
    assert "Knowledge graph" in results[0].page_content
    assert "Local results" in results[0].page_content
    assert "Related questions" in results[0].page_content
    assert "Perspectives" in results[0].page_content
    assert "Things to know" in results[0].page_content
    assert "Pagination" in results[0].page_content
    assert results[1].title == "Austin Coffee Shops"
    assert "Knowledge graph" not in results[1].page_content
