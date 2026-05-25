"""StackExchange / StackOverflow content fetcher using the StackExchange API."""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import httpx

_SE_HOSTS = re.compile(
    r"^(?:www\.)?(stackoverflow\.com|stackexchange\.com|"
    r"(?:[a-z]+)\.stackexchange\.com|"
    r"superuser\.com|serverfault\.com|askubuntu\.com|"
    r"mathoverflow\.net|unix\.stackexchange\.com)$"
)
_QUESTION_PATH = re.compile(r"^/questions/(\d+)")
_MAX_CHARS_DEFAULT = 20_000
_SE_API_BASE = "https://api.stackexchange.com/2.3"


class StackExchangeError(ValueError):
    pass


def _infer_site(host: str) -> str:
    """Map a StackExchange hostname to an API `site` parameter."""
    clean = host.lstrip("www.")
    if clean == "stackoverflow.com":
        return "stackoverflow"
    if clean == "superuser.com":
        return "superuser"
    if clean == "serverfault.com":
        return "serverfault"
    if clean == "askubuntu.com":
        return "askubuntu"
    if clean == "mathoverflow.net":
        return "mathoverflow"
    # For xyz.stackexchange.com → site=xyz
    m = re.match(r"^([a-z]+)\.stackexchange\.com$", clean)
    if m:
        return m.group(1)
    return clean


def parse_stackexchange_url(url: str) -> tuple[str, int]:
    """
    Parse a StackExchange URL and return (site, question_id).

    Raises StackExchangeError if not a SE question URL.
    """
    parsed = urlparse(url)
    host = parsed.netloc or ""
    if not _SE_HOSTS.match(host):
        raise StackExchangeError(f"Not a StackExchange URL: {url!r}")
    m = _QUESTION_PATH.match(parsed.path or "")
    if not m:
        raise StackExchangeError(f"Not a StackExchange question URL: {url!r}")
    site = _infer_site(host)
    question_id = int(m.group(1))
    return site, question_id


def _html_to_text(html: str) -> str:
    """Very minimal HTML → plain text using regex (no heavy dep in this module)."""
    from markdownify import markdownify  # type: ignore[import-untyped]
    return markdownify(html, heading_style="ATX").strip()


async def fetch_stackexchange_thread_markdown(url: str) -> str:
    """Fetch a StackExchange question + answers and return as Markdown."""
    site, question_id = parse_stackexchange_url(url)

    api_key = os.environ.get("STACKEXCHANGE_KEY", "").strip() or None
    se_filter = os.environ.get("STACKEXCHANGE_FILTER", "withbody").strip() or "withbody"
    max_chars_raw = os.environ.get("STACKEXCHANGE_MAX_CHARS", str(_MAX_CHARS_DEFAULT)).strip()
    try:
        max_chars = int(max_chars_raw)
    except ValueError:
        max_chars = _MAX_CHARS_DEFAULT

    q_params: dict[str, str] = {
        "site": site,
        "filter": se_filter,
        "order": "desc",
        "sort": "votes",
    }
    if api_key:
        q_params["key"] = api_key

    a_params = {**q_params, "pagesize": "10"}

    async with httpx.AsyncClient(timeout=20) as client:
        q_resp = await client.get(
            f"{_SE_API_BASE}/questions/{question_id}", params=q_params
        )
        q_resp.raise_for_status()
        q_data = q_resp.json()

        a_resp = await client.get(
            f"{_SE_API_BASE}/questions/{question_id}/answers", params=a_params
        )
        a_resp.raise_for_status()
        a_data = a_resp.json()

    q_items = q_data.get("items", [])
    if not q_items:
        raise StackExchangeError(f"Question {question_id} not found on {site!r}")

    q = q_items[0]
    title = q.get("title", "Untitled")
    body_html = q.get("body", "") or ""
    body_md = _html_to_text(body_html) if body_html else "_No body_"
    score = q.get("score", 0)
    view_count = q.get("view_count", 0)

    parts: list[str] = [
        f"# {title}",
        f"**Score:** {score} | **Views:** {view_count}",
        f"Source: {url}",
        "",
        "## Question",
        "",
        body_md,
    ]

    answers = a_data.get("items", [])
    if answers:
        parts += ["", f"## Answers ({len(answers)})"]
        for i, ans in enumerate(answers, 1):
            ans_score = ans.get("score", 0)
            accepted = " ✓ Accepted" if ans.get("is_accepted") else ""
            ans_body_html = ans.get("body", "") or ""
            ans_md = _html_to_text(ans_body_html) if ans_body_html else "_No body_"
            parts += [
                "",
                f"### Answer {i} (score: {ans_score}{accepted})",
                "",
                ans_md,
            ]

    result = "\n".join(parts)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n_[Content truncated]_"
    return result
