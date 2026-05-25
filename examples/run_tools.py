#!/usr/bin/env python3
"""
Example script for manually testing MCP tool logic outside of an MCP client.

Usage:
    SERPER_API_KEY=your_key python examples/run_tools.py
    TAVILY_API_KEY=your_key python examples/run_tools.py
    SERPAPI_API_KEY=your_key python examples/run_tools.py
    SEARXNG_BASE_URL=https://searx.example.org python examples/run_tools.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

# Add src to path for local runs (not needed when installed)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


async def demo_web_search(query: str, num_results: int = 2) -> None:
    """Run a web_search and pretty-print the results."""
    from src.search import search_web
    from src.content.resolver import resolve_page_content_markdown

    print(f"\n{'='*60}")
    print(f"web_search({query!r}, num_results={num_results})")
    print("="*60)

    results = await search_web(query, num_results=num_results)
    if not results:
        print("No results returned.")
        return

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r.title}")
        print(f"    URL: {r.link}")
        print(f"    Snippet: {r.snippet[:100]}...")

        print(f"    Fetching page content...")
        try:
            md = await resolve_page_content_markdown(r.link)
            if md:
                preview = md[:300].replace("\n", " ")
                print(f"    Content preview: {preview}...")
            else:
                print("    Content: (skipped — binary or unsupported)")
        except Exception as exc:
            print(f"    Content error: {exc}")


async def demo_get_content(url: str) -> None:
    """Fetch a single URL and print its Markdown content."""
    from src.content.resolver import resolve_page_content_markdown

    print(f"\n{'='*60}")
    print(f"get_content({url!r})")
    print("="*60)

    md = await resolve_page_content_markdown(url)
    if md:
        print(md[:1000])
        if len(md) > 1000:
            print(f"\n... [{len(md) - 1000} more characters]")
    else:
        print("(No content — binary or unsupported URL)")


async def main() -> None:
    # Test web search
    await demo_web_search("Python asyncio tutorial", num_results=2)

    # Test get_content with specialized handlers
    print("\n\n[Testing specialized handlers]")

    # Wikipedia
    await demo_get_content("https://en.wikipedia.org/wiki/Python_(programming_language)")

    # arXiv
    await demo_get_content("https://arxiv.org/abs/1706.03762")


if __name__ == "__main__":
    asyncio.run(main())
