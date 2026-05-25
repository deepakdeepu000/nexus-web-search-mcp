"""Pydantic models for MCP tool responses."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    """A single web search result with extracted page content."""

    title: str = Field(description="Human-readable result title.")
    link: str = Field(description="Canonical URL for the result.")
    snippet: str = Field(description="Search engine snippet/preview text.")
    page_content: str = Field(
        description="LLM-ready Markdown content fetched from `link` (best-effort). Always a string.",
    )
    diagnostics: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional diagnostics emitted when MCP_DIAGNOSTICS=1 is set.",
    )


class WebSearchResponse(BaseModel):
    """Response envelope for the web_search tool."""

    results: list[WebSearchResult]


class GetContentResponse(BaseModel):
    """Response envelope for the get_content tool."""

    url: str = Field(description="The requested URL.")
    page_content: str = Field(
        description="LLM-ready Markdown extracted from the URL (best-effort)."
    )
    diagnostics: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional diagnostics emitted when MCP_DIAGNOSTICS=1 is set.",
    )
