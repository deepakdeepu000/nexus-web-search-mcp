"""Tests for the get_content tool in the MCP server."""

from __future__ import annotations

import asyncio
from unittest.mock import ANY, AsyncMock, patch

import pytest

from src.server import get_content

@pytest.mark.asyncio
async def test_get_content_returns_page_content(monkeypatch):
    monkeypatch.delenv("MCP_DIAGNOSTICS", raising=False)
    monkeypatch.setenv("TOOL_TOTAL_TIMEOUT_SECONDS", "5")

    async def run() -> dict:
        with patch(
            "src.server.resolve_page_content_markdown",
            new=AsyncMock(return_value="# Example\n\nFetched content."),
        ) as mock_resolver:
            result = await get_content(
                "https://simplescraper.io/blog/how-to-mcp#legacy-clients-http-sse"
            )
            mock_resolver.assert_awaited_once_with(
                "https://simplescraper.io/blog/how-to-mcp#legacy-clients-http-sse",
                diagnostics=ANY,
            )
            return result

    result = asyncio.run(run())
    assert result["url"] == "https://simplescraper.io/blog/how-to-mcp#legacy-clients-http-sse"
    assert result["page_content"] == "# Example\n\nFetched content."
    assert "diagnostics" not in result


