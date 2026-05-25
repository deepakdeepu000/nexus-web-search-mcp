"""Tests for the diagnostics module."""
import pytest
from src.utils.diagnostics import (
    diagnostics_enabled,
    mask_env_values,
    truncate_text,
    sample_data,
    Diagnostics,
    new_request_id,
)


def test_diagnostics_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DIAGNOSTICS", raising=False)
    assert not diagnostics_enabled()


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_diagnostics_enabled_truthy_values(value, monkeypatch):
    monkeypatch.setenv("MCP_DIAGNOSTICS", value)
    assert diagnostics_enabled()


def test_diagnostics_disabled_with_falsy(monkeypatch):
    monkeypatch.setenv("MCP_DIAGNOSTICS", "0")
    assert not diagnostics_enabled()


def test_mask_env_values():
    env = {
        "SERPER_API_KEY": "abc123",
        "LOG_LEVEL": "DEBUG",
        "GITHUB_TOKEN": "ghp_xyz",
        "SEARXNG_BASE_URL": "https://searx.example.org",
    }
    masked = mask_env_values(env)
    assert "abc123" not in masked["SERPER_API_KEY"]
    assert "ghp_xyz" not in masked["GITHUB_TOKEN"]
    assert masked["LOG_LEVEL"] == "DEBUG"
    assert masked["SEARXNG_BASE_URL"] == "https://searx.example.org"


def test_truncate_text_within_limit():
    text, truncated, length = truncate_text("hello", 100)
    assert text == "hello"
    assert not truncated
    assert length == 5


def test_truncate_text_over_limit():
    long_text = "x" * 200
    text, truncated, length = truncate_text(long_text, 100)
    assert truncated
    assert length == 200
    assert "truncated" in text


def test_truncate_text_none():
    text, truncated, length = truncate_text(None, 100)
    assert text == ""
    assert not truncated
    assert length == 0


def test_new_request_id_is_uuid_like():
    rid = new_request_id()
    assert len(rid) == 36
    assert rid.count("-") == 4


def test_diagnostics_emit_when_disabled():
    diag = Diagnostics("test-id", enabled=False)
    diag.emit("test.stage", "Test message", {"key": "value"})
    assert diag.entries == []


def test_diagnostics_emit_when_enabled():
    diag = Diagnostics("test-id", enabled=True)
    diag.emit("test.stage", "Test message", {"key": "value"})
    assert len(diag.entries) == 1
    entry = diag.entries[0]
    assert entry["stage"] == "test.stage"
    assert entry["msg"] == "Test message"
    assert entry["data"]["key"] == "value"
    assert entry["request_id"] == "test-id"
    assert "elapsed_ms" in entry


def test_diagnostics_emit_multiple():
    diag = Diagnostics("req-1", enabled=True)
    diag.emit("stage.a", "First")
    diag.emit("stage.b", "Second")
    assert len(diag.entries) == 2
    assert diag.entries[0]["stage"] == "stage.a"
    assert diag.entries[1]["stage"] == "stage.b"
