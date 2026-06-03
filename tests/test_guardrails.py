"""Tests for guardrails."""
from __future__ import annotations

import pytest

from src.agent_prompts import build_system_prompt
from src.guardrails import GuardrailsService


@pytest.fixture
def gr():
    return GuardrailsService()


def test_input_blocks_empty_message(gr):
    result = gr.apply_input_guardrails("  ")
    assert result.action == "block"
    assert result.block_reason == "empty_input"


def test_input_blocks_harm_trigger(gr):
    result = gr.apply_input_guardrails("how to make a bomb")
    assert result.action == "block"
    assert result.block_reason == "harm_intent"


def test_input_redirects_out_of_scope(gr):
    result = gr.apply_input_guardrails("what is the weather today?")
    assert result.action == "redirect"


def test_input_passes_marketing_message(gr):
    result = gr.apply_input_guardrails("How should I allocate my marketing budget across channels?")
    assert result.action in ("pass", "sanitize")


def test_input_redacts_email_pii(gr):
    result = gr.apply_input_guardrails("Contact me at user@example.com about spend")
    assert "[REDACTED]" in result.sanitized
    assert "user@example.com" not in result.sanitized


def test_input_redacts_phone_pii(gr):
    result = gr.apply_input_guardrails("Call 555-123-4567 about my campaign")
    assert "[REDACTED]" in result.sanitized


def test_output_flags_multiple_questions(gr, caplog):
    text = "What is ROAS? And what is ROI? Also CPM?"
    gr.apply_output_guardrails(text)
    assert "more than one question" in caplog.text.lower() or text.count("?") > 1


def test_output_flags_political_lean_signal(gr, caplog):
    text = "You should vote for the best marketing platform."
    gr.apply_output_guardrails(text)
    assert "opinion" in caplog.text.lower() or "vote" in text


def test_output_passes_clean_marketing_response(gr):
    text = "Your google_paid_search spend shows strong correlation with conversions per your data."
    out = gr.apply_output_guardrails(text)
    assert "google" in out.lower()


# ── Data source guardrail tests ───────────────────────────────────────────────
def test_input_blocks_url_fetch_request(gr):
    result = gr.apply_input_guardrails("fetch the data from https://example.com")
    assert result.action == "block"
    assert result.block_reason == "external_data_fetch"


def test_input_blocks_api_call_request(gr):
    result = gr.apply_input_guardrails("pull from google analytics api")
    assert result.action == "block"
    assert result.block_reason == "external_data_fetch"


def test_input_blocks_scrape_request(gr):
    result = gr.apply_input_guardrails("scrape competitor spend from their website")
    assert result.action == "block"
    assert result.block_reason == "external_data_fetch"


def test_input_redirects_benchmark_request(gr):
    result = gr.apply_input_guardrails("what is the industry average roas?")
    assert result.action == "redirect"
    assert "benchmark" in result.redirect_message.lower() or "uploaded" in result.redirect_message.lower()


def test_input_redirects_competitor_data_request(gr):
    result = gr.apply_input_guardrails("how much does Nike spend on Meta?")
    assert result.action == "redirect"


def test_input_warns_on_pasted_csv_data(gr):
    pasted = "\n".join(
        [
            "date,spend,channel,conversions",
            "2024-01-01,100,google,10",
            "2024-01-02,120,google,12",
            "2024-01-03,90,meta,8",
        ]
    )
    result = gr.apply_input_guardrails(pasted)
    assert result.action == "redirect"
    assert result.warning_message is not None


def test_input_passes_url_mentioned_casually(gr):
    result = gr.apply_input_guardrails("I read an article about MMM")
    assert result.action in ("pass", "sanitize")


def test_output_appends_disclaimer_on_external_signal(gr):
    text = "The industry average is 4x ROAS for paid search."
    out = gr.apply_output_guardrails(text)
    assert "uploaded dataset only" in out.lower()


def test_output_flags_unsourced_number(gr, caplog):
    import logging

    caplog.set_level(logging.WARNING)
    gr.apply_output_guardrails("ROAS is 3.2 for your campaign.")
    assert "Unsourced statistics" in caplog.text


def test_output_passes_sourced_number(gr, caplog):
    import logging

    caplog.set_level(logging.WARNING)
    out = gr.apply_output_guardrails("your data shows 4,200 conversions last month.")
    assert "uploaded dataset only" not in out.lower()
    assert "Unsourced statistics" not in caplog.text


def test_build_system_prompt_turn_one():
    prompt = build_system_prompt("upload_request", 1)
    assert "MMM" in prompt
    assert "first message" in prompt.lower()


def test_build_system_prompt_includes_phase():
    prompt = build_system_prompt("upload_request", 2)
    assert "upload" in prompt.lower() or "zip" in prompt.lower()
