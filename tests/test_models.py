"""Tests for Pydantic response models."""
import pytest
from src.models import WebSearchResult, WebSearchResponse, GetContentResponse


def test_web_search_result_basic():
    r = WebSearchResult(
        title="Test Title",
        link="https://example.com",
        snippet="A test snippet.",
        page_content="# Test\n\nSome content.",
    )
    assert r.title == "Test Title"
    assert r.link == "https://example.com"
    assert r.diagnostics is None


def test_web_search_result_with_diagnostics():
    r = WebSearchResult(
        title="T",
        link="https://example.com",
        snippet="s",
        page_content="c",
        diagnostics=[{"stage": "test", "msg": "ok"}],
    )
    assert r.diagnostics is not None
    assert r.diagnostics[0]["stage"] == "test"


def test_web_search_response_serialization():
    resp = WebSearchResponse(
        results=[
            WebSearchResult(title="A", link="https://a.com", snippet="s", page_content="c")
        ]
    )
    d = resp.model_dump(exclude_none=True)
    assert "results" in d
    assert len(d["results"]) == 1
    assert "diagnostics" not in d["results"][0]


def test_get_content_response():
    resp = GetContentResponse(url="https://example.com", page_content="# Hello")
    d = resp.model_dump(exclude_none=True)
    assert d["url"] == "https://example.com"
    assert d["page_content"] == "# Hello"
    assert "diagnostics" not in d
