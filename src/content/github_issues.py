"""GitHub Issues content fetcher using the GitHub REST API."""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import httpx

_GITHUB_HOST = re.compile(r"^(?:www\.)?github\.com$")
_ISSUE_PATH = re.compile(r"^/([^/]+)/([^/]+)/issues/(\d+)")
_MAX_CHARS_DEFAULT = 20_000
_MAX_COMMENTS_DEFAULT = 50
_GH_API_BASE = "https://api.github.com"


class GitHubIssueError(ValueError):
    pass


def parse_github_issue_url(url: str) -> tuple[str, str, int]:
    """
    Parse a GitHub issue URL and return (owner, repo, issue_number).

    Raises GitHubIssueError if not a GitHub issue URL.
    """
    parsed = urlparse(url)
    if not _GITHUB_HOST.match(parsed.netloc or ""):
        raise GitHubIssueError(f"Not a GitHub URL: {url!r}")
    m = _ISSUE_PATH.match(parsed.path or "")
    if not m:
        raise GitHubIssueError(f"Not a GitHub issue URL: {url!r}")
    return m.group(1), m.group(2), int(m.group(3))


def _build_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def fetch_github_issue_thread_markdown(url: str) -> str:
    """Fetch a GitHub issue with comments and return as Markdown."""
    owner, repo, issue_number = parse_github_issue_url(url)

    max_chars_raw = os.environ.get("GITHUB_MAX_CHARS", str(_MAX_CHARS_DEFAULT)).strip()
    max_comments_raw = os.environ.get("GITHUB_MAX_COMMENTS", str(_MAX_COMMENTS_DEFAULT)).strip()
    try:
        max_chars = int(max_chars_raw)
    except ValueError:
        max_chars = _MAX_CHARS_DEFAULT
    try:
        max_comments = int(max_comments_raw)
    except ValueError:
        max_comments = _MAX_COMMENTS_DEFAULT

    headers = _build_headers()

    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        issue_resp = await client.get(
            f"{_GH_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"
        )
        issue_resp.raise_for_status()
        issue = issue_resp.json()

        comments_resp = await client.get(
            f"{_GH_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments",
            params={"per_page": str(min(max_comments, 100))},
        )
        comments_resp.raise_for_status()
        comments = comments_resp.json()

    title = issue.get("title", "Untitled Issue")
    state = issue.get("state", "unknown")
    labels = ", ".join(
        lbl.get("name", "") for lbl in (issue.get("labels") or [])
    )
    body = issue.get("body") or "_No description_"
    author = (issue.get("user") or {}).get("login", "unknown")

    parts: list[str] = [
        f"# {title}",
        f"**State:** {state} | **Author:** @{author}" + (f" | **Labels:** {labels}" if labels else ""),
        f"Source: {url}",
        "",
        "## Issue Body",
        "",
        body,
    ]

    if comments and isinstance(comments, list):
        parts += ["", f"## Comments ({len(comments)})"]
        for i, comment in enumerate(comments[:max_comments], 1):
            commenter = (comment.get("user") or {}).get("login", "unknown")
            created = (comment.get("created_at") or "")[:10]
            comment_body = comment.get("body") or "_No body_"
            parts += [
                "",
                f"### Comment {i} — @{commenter} ({created})",
                "",
                comment_body,
            ]

    result = "\n".join(parts)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n_[Content truncated]_"
    return result
