"""
AI Agent — Claude API orchestration
Owner: Piyush Sandhikar (skeleton wired for Claude)

Uses Anthropic SDK; API key from ANTHROPIC_API_KEY in .env
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from src.data_prep import load_config

logger = logging.getLogger(__name__)

load_dotenv()


def get_claude_client():
    """Return Anthropic client or None if API key is missing."""
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        logger.warning("anthropic package not installed: %s", exc)
        return None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return Anthropic(api_key=api_key)


def parse_problem(natural_language_input: str, client=None) -> dict:
    """Parse user intent into structured optimization inputs (stub for Piyush)."""
    _ = natural_language_input, client
    return {"budget": None, "objective": "maximize_conversions", "constraints": []}


def run_agent(
    user_message: str,
    system_prompt: str,
    conversation_history: list[dict],
    config_path: str = "config.yaml",
) -> str:
    """
    Run one agent turn with Claude.

    Falls back to a clear placeholder if ANTHROPIC_API_KEY is not set.
    """
    config = load_config(config_path)
    llm_cfg = config.get("llm", {})
    model = llm_cfg.get("model", "claude-sonnet-4-20250514")
    temperature = float(llm_cfg.get("temperature", 0.2))
    max_tokens = int(llm_cfg.get("max_tokens", 1024))

    client = get_claude_client()
    if client is None:
        return (
            "[Agent — add ANTHROPIC_API_KEY to .env to enable Claude]\n\n"
            "Your message was received. Guardrails and system prompts are active; "
            "connect the API key to get live responses."
        )

    messages: list[dict] = []
    for turn in conversation_history[-20:]:
        role = "user" if turn.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": turn.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else ""
    except Exception as exc:
        logger.exception("Claude API call failed")
        return (
            "I could not reach the language model right now. "
            f"Please try again. (Error: {type(exc).__name__})"
        )


def run_benchmark(messages: list[str]) -> dict:
    """Benchmark agent responses (stub)."""
    return {"messages": messages, "status": "not_implemented"}


# Backward-compatible alias during team migration away from Gemini
get_gemini_client = get_claude_client
