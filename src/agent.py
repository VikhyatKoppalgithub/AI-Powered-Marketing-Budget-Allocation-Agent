"""
Gemini agent orchestration
Owner: Piyush Sandhikar

Uses google.generativeai; API key from GEMINI_API_KEY env var.
"""
from __future__ import annotations


def get_gemini_client():
    """Return configured Gemini client."""
    pass


def parse_problem(user_message: str, context: dict) -> dict:
    """Parse user intent into structured problem."""
    pass


def run_agent(
    user_message: str,
    system_prompt: str,
    conversation_history: list[dict],
) -> str:
    """Run agent turn with Gemini."""
    pass


def run_benchmark(messages: list[str]) -> dict:
    """Benchmark agent responses."""
    pass
