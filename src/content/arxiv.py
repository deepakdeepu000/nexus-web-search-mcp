from __future__ import annotations

import os
import re
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

_ARXIV_HOST = re.compile(r"^(?:www\.)?arxiv\.org$")
_ARXIV_ID = re.compile(
    r"(?:abs|pdf|html)/(\d{4}\.\d{4,5}(?:v\d+)?|[a-zA-Z\-]+(?:\.[a-zA-Z]+)?/\d{7}(?:v\d+)?)"
)
_DEFAULT_UA = "mcp-web-search/1.0 (contact: user@example.com)"
_MAX_CHARS_DEFAULT = 50_000
_ARXIV_ATOM = "https://export.arxiv.org/api/query?id_list={arxiv_id}"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivError(ValueError):
    pass


def parse_arxiv_url(url: str) -> str:
    """
    Parse an arXiv URL and return the arXiv paper ID.

    Raises ArxivError if not a valid arXiv URL.
    """
    parsed = urlparse(url)
    if not _ARXIV_HOST.match(parsed.netloc or ""):
        raise ArxivError(f"Not an arXiv URL: {url!r}")
    path = parsed.path or ""
    m = _ARXIV_ID.search(path)
    if not m:
        raise ArxivError(f"Could not extract arXiv ID from: {url!r}")
    return m.group(1)


async def fetch_arxiv_paper_markdown(url: str) -> str:
    """Fetch an arXiv paper abstract and metadata, return as Markdown."""
    arxiv_id = parse_arxiv_url(url)

    ua = os.environ.get("ARXIV_USER_AGENT", _DEFAULT_UA).strip() or _DEFAULT_UA
    max_chars_raw = os.environ.get("ARXIV_MAX_CHARS", str(_MAX_CHARS_DEFAULT)).strip()
    try:
        max_chars = int(max_chars_raw)
    except ValueError:
        max_chars = _MAX_CHARS_DEFAULT

    atom_url = _ARXIV_ATOM.format(arxiv_id=arxiv_id)
    headers = {"User-Agent": ua}

    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        resp = await client.get(atom_url)
        resp.raise_for_status()
        xml_text = resp.text

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise ArxivError(f"Failed to parse arXiv Atom feed: {exc}") from exc

    entries = root.findall("atom:entry", NS)
    if not entries:
        raise ArxivError(f"No arXiv entry found for ID: {arxiv_id!r}")

    entry = entries[0]

    def _text(tag: str, ns_prefix: str = "atom") -> str:
        el = entry.find(f"{ns_prefix}:{tag}", NS)
        return (el.text or "").strip() if el is not None else ""

    title = _text("title")
    summary = _text("summary")
    published = _text("published")[:10]

    authors: list[str] = []
    for author_el in entry.findall("atom:author", NS):
        name_el = author_el.find("atom:name", NS)
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    # Get canonical arxiv link
    canonical_url = url
    for link_el in entry.findall("atom:link", NS):
        if link_el.get("rel") == "alternate":
            canonical_url = link_el.get("href", url)
            break

    # Get categories/subject
    primary_category = entry.find("arxiv:primary_category", NS)
    subject = (primary_category.get("term", "") if primary_category is not None else "")

    parts: list[str] = [
        f"# {title}",
        f"**Authors:** {', '.join(authors) if authors else 'Unknown'}",
        f"**Published:** {published}" + (f" | **Subject:** {subject}" if subject else ""),
        f"Source: {canonical_url}",
        "",
        "## Abstract",
        "",
        summary,
    ]

    result = "\n".join(parts)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n_[Content truncated]_"
    return result
