"""Wikipedia content fetcher using the MediaWiki Action API."""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import httpx

_WIKI_DOMAINS = re.compile(r"^([a-z]{2,})\.wikipedia\.org$")
_DEFAULT_UA = "mcp-web-search/1.0 (contact: user@example.com)"
_MAX_CHARS_DEFAULT = 50_000


class WikipediaError(ValueError):
    pass


def parse_wikipedia_url(url: str) -> tuple[str, str]:
    """
    Parse a Wikipedia URL and return (lang, page_title).

    Raises WikipediaError if the URL is not a Wikipedia article.
    """
    parsed = urlparse(url)
    m = _WIKI_DOMAINS.match(parsed.netloc or "")
    if not m:
        raise WikipediaError(f"Not a Wikipedia URL: {url!r}")
    lang = m.group(1)
    path = parsed.path or ""
    if not path.startswith("/wiki/"):
        raise WikipediaError(f"Not a Wikipedia article path: {url!r}")
    title = path[len("/wiki/"):]
    if not title:
        raise WikipediaError(f"Empty Wikipedia article title in: {url!r}")
    return lang, title


async def fetch_wikipedia_article_markdown(url: str) -> str:
    """Fetch a Wikipedia article and return it as clean Markdown text."""
    lang, title = parse_wikipedia_url(url)

    ua = os.environ.get("WIKIPEDIA_USER_AGENT", _DEFAULT_UA).strip() or _DEFAULT_UA
    max_chars_raw = os.environ.get("WIKIPEDIA_MAX_CHARS", str(_MAX_CHARS_DEFAULT)).strip()
    try:
        max_chars = int(max_chars_raw)
    except ValueError:
        max_chars = _MAX_CHARS_DEFAULT

    api_url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts",
        "exlimit": 1,
        "explaintext": True,
        "redirects": True,
        "titles": title,
        "format": "json",
        "formatversion": 2,
    }
    headers = {"User-Agent": ua}

    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        resp = await client.get(api_url, params=params)
        resp.raise_for_status()
        data = resp.json()

    pages = data.get("query", {}).get("pages", [])
    if not pages:
        raise WikipediaError(f"No pages returned for: {title!r}")

    page = pages[0]
    if "missing" in page:
        raise WikipediaError(f"Wikipedia article not found: {title!r}")

    page_title = page.get("title", title)
    extract = page.get("extract", "")
    if not extract:
        raise WikipediaError(f"Empty extract for Wikipedia article: {title!r}")

    # Truncate if needed
    if len(extract) > max_chars:
        extract = extract[:max_chars] + "\n\n_[Content truncated]_"

    return f"# {page_title}\n\nSource: {url}\n\n{extract}\n"
