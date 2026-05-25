"""Tests for the content resolution pipeline."""
import pytest
from unittest.mock import AsyncMock, patch
import asyncio
from src.content.resolver import resolve_page_content_markdown


WIKI_URL = "https://en.wikipedia.org/wiki/Python_(programming_language)"
SO_URL = "https://stackoverflow.com/questions/11828270/how-do-i-exit-vim"
GH_URL = "https://github.com/python/cpython/issues/12345"
ARXIV_URL = "https://arxiv.org/abs/2301.00001"
PLAIN_URL = "https://example.com/some-article"


@pytest.mark.asyncio
async def test_routes_wikipedia():
    with patch(
        "src.content.resolver.fetch_wikipedia_article_markdown",
        new=AsyncMock(return_value="# Python\n\nGreat language."),
    ) as mock_fn:
        result = await resolve_page_content_markdown(WIKI_URL)
    mock_fn.assert_called_once_with(WIKI_URL)
    assert result == "# Python\n\nGreat language."


@pytest.mark.asyncio
async def test_routes_stackexchange():
    with patch(
        "src.content.resolver.fetch_stackexchange_thread_markdown",
        new=AsyncMock(return_value="# How to exit vim\n\nPress :q!"),
    ) as mock_fn:
        result = await resolve_page_content_markdown(SO_URL)
    mock_fn.assert_called_once_with(SO_URL)
    assert "vim" in result


@pytest.mark.asyncio
async def test_routes_arxiv():
    with patch(
        "src.content.resolver.fetch_arxiv_paper_markdown",
        new=AsyncMock(return_value="# Some Paper\n\nAbstract here."),
    ) as mock_fn:
        result = await resolve_page_content_markdown(ARXIV_URL)
    mock_fn.assert_called_once_with(ARXIV_URL)
    assert "Paper" in result


@pytest.mark.asyncio
async def test_falls_back_to_html_for_unknown_url():
    with patch(
        "src.content.resolver.load_url_as_markdown",
        new=AsyncMock(return_value="# Example\n\nContent here."),
    ) as mock_fn:
        result = await resolve_page_content_markdown(PLAIN_URL)
    mock_fn.assert_called_once()
    assert result is not None


@pytest.mark.asyncio
async def test_stackexchange_error_returns_note():
    with patch(
        "src.content.resolver.fetch_stackexchange_thread_markdown",
        new=AsyncMock(side_effect=RuntimeError("API error")),
    ):
        result = await resolve_page_content_markdown(SO_URL)
    assert result is not None
    assert "_Failed" in result
    assert SO_URL in result


@pytest.mark.asyncio
async def test_wikipedia_fallback_to_html():
    with patch(
        "src.content.resolver.fetch_wikipedia_article_markdown",
        new=AsyncMock(side_effect=Exception("timeout")),
    ):
        with patch(
            "src.content.resolver.load_url_as_markdown",
            new=AsyncMock(return_value="# Fallback Content"),
        ) as mock_html:
            result = await resolve_page_content_markdown(WIKI_URL)
    mock_html.assert_called_once()
    assert result == "# Fallback Content"
