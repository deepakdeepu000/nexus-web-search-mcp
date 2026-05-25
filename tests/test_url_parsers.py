"""Tests for URL parser functions across all specialized content loaders."""
import pytest

from src.content.wikipedia import parse_wikipedia_url, WikipediaError
from src.content.arxiv import parse_arxiv_url, ArxivError
from src.content.stackexchange import parse_stackexchange_url, StackExchangeError
from src.content.github_issues import parse_github_issue_url, GitHubIssueError


# ── Wikipedia ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected_lang,expected_title", [
    ("https://en.wikipedia.org/wiki/Python_(programming_language)", "en", "Python_(programming_language)"),
    ("https://de.wikipedia.org/wiki/Berlin", "de", "Berlin"),
    ("https://fr.wikipedia.org/wiki/Tour_Eiffel", "fr", "Tour_Eiffel"),
])
def test_parse_wikipedia_url_valid(url, expected_lang, expected_title):
    lang, title = parse_wikipedia_url(url)
    assert lang == expected_lang
    assert title == expected_title


@pytest.mark.parametrize("url", [
    "https://example.com/wiki/Python",
    "https://en.wikipedia.org/",
    "https://en.wikipedia.org/search?q=python",
])
def test_parse_wikipedia_url_invalid(url):
    with pytest.raises(WikipediaError):
        parse_wikipedia_url(url)


# ── arXiv ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected_id", [
    ("https://arxiv.org/abs/2301.00001", "2301.00001"),
    ("https://arxiv.org/pdf/1706.03762v5", "1706.03762v5"),
    ("https://arxiv.org/abs/cs.AI/0612017", "cs.AI/0612017"),
])
def test_parse_arxiv_url_valid(url, expected_id):
    arxiv_id = parse_arxiv_url(url)
    assert arxiv_id == expected_id


@pytest.mark.parametrize("url", [
    "https://example.com/abs/2301.00001",
    "https://arxiv.org/",
    "https://arxiv.org/search/?query=attention",
])
def test_parse_arxiv_url_invalid(url):
    with pytest.raises(ArxivError):
        parse_arxiv_url(url)


# ── StackExchange ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected_site,expected_id", [
    ("https://stackoverflow.com/questions/11828270/how-do-i-exit-vim", "stackoverflow", 11828270),
    ("https://superuser.com/questions/12345/title", "superuser", 12345),
    ("https://askubuntu.com/questions/99999/some-question", "askubuntu", 99999),
    ("https://math.stackexchange.com/questions/1/example", "math", 1),
])
def test_parse_stackexchange_url_valid(url, expected_site, expected_id):
    site, qid = parse_stackexchange_url(url)
    assert site == expected_site
    assert qid == expected_id


@pytest.mark.parametrize("url", [
    "https://example.com/questions/123/title",
    "https://stackoverflow.com/",
    "https://stackoverflow.com/users/12345",
])
def test_parse_stackexchange_url_invalid(url):
    with pytest.raises(StackExchangeError):
        parse_stackexchange_url(url)


# ── GitHub Issues ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    ("https://github.com/python/cpython/issues/12345", ("python", "cpython", 12345)),
    ("https://github.com/torvalds/linux/issues/1", ("torvalds", "linux", 1)),
])
def test_parse_github_issue_url_valid(url, expected):
    result = parse_github_issue_url(url)
    assert result == expected


@pytest.mark.parametrize("url", [
    "https://example.com/python/cpython/issues/1",
    "https://github.com/python/cpython/pulls/1",
    "https://github.com/python/cpython",
])
def test_parse_github_issue_url_invalid(url):
    with pytest.raises(GitHubIssueError):
        parse_github_issue_url(url)
