"""Tests for Claude agent wiring."""
from src.agent import run_agent


def test_run_agent_without_api_key_returns_helpful_message(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = run_agent("Hello", "system", [])
    assert "ANTHROPIC_API_KEY" in out
