"""
Claude agent orchestration
Owner: Piyush Sandhikar

Uses anthropic SDK; API key from ANTHROPIC_API_KEY env var.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "upload": ["upload", "zip", "csv", "file", "dataset"],
    "confirm": ["confirm", "schema", "column", "looks right", "target variable"],
    "analyze": ["backward", "analysis", "stage", "outcome", "saturation", "adstock"],
    "optimize": ["optimize", "optimization", "allocation", "allocate", "budget", "kkt", "shadow price", "solver"],
    "explore": ["chart", "sensitivity", "scenario", "breakdown", "curve", "tornado"],
}

_FALLBACK_NO_KEY = (
    "Claude is not configured yet — create a `.env` file in the project root with:\n\n"
    "`ANTHROPIC_API_KEY=sk-ant-...`\n\n"
    "Then restart Streamlit (`streamlit run app/app.py`).\n\n"
    "I'm your marketing budget optimization guide. Upload a `.zip` or `.csv` "
    "with daily channel spend and conversions to begin."
)

_OPTIMIZATION_BLOCKED = (
    "Optimization runs after you complete the 7-stage backward analysis and "
    "confirm the objective and constraints.\n\n"
    "Would you like to continue with the backward analysis first?"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_config(config_path: str | None = None) -> dict:
    path = Path(config_path) if config_path else _repo_root() / "config.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_ENV_KEY_NAMES = (
    "ANTHROPIC_API_KEY",
    "CLAUDE_API_KEY",
    "ANTHROPIC_KEY",
    "API_Key",
)


def _load_env_files() -> list[Path]:
    """Load .env from common locations; return paths that were found."""
    root = _repo_root()
    candidates = [
        root / ".env",
        root / "app" / ".env",
        Path.cwd() / ".env",
    ]
    loaded: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        load_dotenv(path, override=False)
        loaded.append(path)
    return loaded


def _api_key() -> str | None:
    _load_env_files()
    for name in _ENV_KEY_NAMES:
        value = (os.getenv(name) or "").strip()
        if value and value not in {"your_key_here", "changeme", "xxx"}:
            return value
    return None


def _resolved_model(model_name: str | None = None) -> str:
    config = _load_config()
    llm = config.get("llm", {})
    return model_name or os.getenv("ANTHROPIC_MODEL") or llm.get("model", "claude-sonnet-4-20250514")


def get_claude_client():
    """Return configured Anthropic client, or None if no API key."""
    api_key = _api_key()
    if not api_key:
        return None

    import anthropic

    return anthropic.Anthropic(api_key=api_key)


def _extract_response_text(response) -> str:
    parts = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts).strip()


def call_claude(
    messages: list[dict],
    system_prompt: str | None = None,
    model_name: str | None = None,
) -> str | None:
    """Send a Claude messages request; return text or None when unavailable."""
    client = get_claude_client()
    if client is None:
        return None

    config = _load_config().get("llm", {})
    response = client.messages.create(
        model=_resolved_model(model_name),
        max_tokens=config.get("max_tokens", 1024),
        temperature=config.get("temperature", 0.2),
        system=system_prompt or "",
        messages=messages,
    )
    text = _extract_response_text(response)
    return text or None


def parse_problem(user_message: str, context: dict | None = None) -> dict:
    """Parse user intent into a structured problem description."""
    context = context or {}
    lower = (user_message or "").strip().lower()

    intents = [
        intent
        for intent, keywords in _INTENT_KEYWORDS.items()
        if any(keyword in lower for keyword in keywords)
    ]
    primary_intent = intents[0] if intents else "general"

    optimization_blocked = not context.get("backward_analysis_confirmed", False)
    blocked_reason = None
    if primary_intent == "optimize" and optimization_blocked:
        blocked_reason = "backward_analysis_not_confirmed"

    return {
        "primary_intent": primary_intent,
        "intents": intents,
        "phase": context.get("phase", "upload_request"),
        "user_message": user_message,
        "requires_data": primary_intent in {"confirm", "analyze", "optimize", "explore"},
        "optimization_blocked": optimization_blocked,
        "blocked_reason": blocked_reason,
        "upload_complete": context.get("upload_complete", False),
        "schema_confirmed": context.get("schema_confirmed", False),
    }


def _normalize_history(conversation_history: list[dict], user_message: str) -> list[dict]:
    """Drop a trailing duplicate user turn if the app already appended it."""
    history = list(conversation_history or [])
    if history and history[-1].get("role") == "user":
        last_content = (history[-1].get("content") or "").strip()
        if last_content == (user_message or "").strip():
            history = history[:-1]
    return history


def _format_history_for_claude(history: list[dict]) -> list[dict]:
    formatted = []
    for msg in history:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content or role not in {"user", "assistant"}:
            continue
        formatted.append({"role": role, "content": content})
    return formatted


def _fallback_response(user_message: str, context: dict | None = None) -> str:
    parsed = parse_problem(user_message, context)
    if parsed.get("blocked_reason") == "backward_analysis_not_confirmed":
        return _OPTIMIZATION_BLOCKED
    if parsed["primary_intent"] == "upload":
        return (
            "Please upload your marketing dataset as a `.zip` or `.csv` using the "
            "uploader on the Upload page.\n\n"
            "What format is your data in today?"
        )
    return _FALLBACK_NO_KEY


def run_agent(
    user_message: str,
    system_prompt: str,
    conversation_history: list[dict],
    context: dict | None = None,
) -> str:
    """Run one agent turn with Claude; fall back gracefully when unavailable."""
    msg = (user_message or "").strip()
    if not msg:
        return "Please type a message so I can help you."

    parsed = parse_problem(msg, context)
    if parsed.get("blocked_reason") == "backward_analysis_not_confirmed":
        return _OPTIMIZATION_BLOCKED

    if get_claude_client() is None:
        return _fallback_response(msg, context)

    history = _normalize_history(conversation_history, msg)
    claude_messages = _format_history_for_claude(history)
    claude_messages.append({"role": "user", "content": msg})

    try:
        text = call_claude(claude_messages, system_prompt=system_prompt)
        if text:
            return text
        return (
            "Claude returned an empty response. Check your API key, model name, "
            "and account credits, then try again."
        )
    except Exception as exc:  # noqa: BLE001 - degrade gracefully for UI stability
        logger.warning("Claude call failed: %s", exc)
        return (
            "I couldn't reach Claude right now. "
            f"Error: {exc}\n\n"
            "Check that `ANTHROPIC_API_KEY` is valid in `.env` and restart the app."
        )


def run_benchmark(
    messages: list[str],
    system_prompt: str | None = None,
    context: dict | None = None,
) -> dict:
    """Benchmark agent responses for a list of in-scope messages."""
    from src.agent_prompts import build_system_prompt

    prompt = system_prompt or build_system_prompt("upload_request", 1)
    results: list[dict] = []
    latencies: list[float] = []

    for message in messages:
        started = time.perf_counter()
        try:
            response = run_agent(message, prompt, [], context=context)
            elapsed = time.perf_counter() - started
            latencies.append(elapsed)
            results.append(
                {
                    "message": message,
                    "response": response,
                    "latency_s": round(elapsed, 4),
                    "ok": True,
                    "response_chars": len(response),
                }
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - started
            results.append(
                {
                    "message": message,
                    "error": str(exc),
                    "latency_s": round(elapsed, 4),
                    "ok": False,
                }
            )

    success_count = sum(1 for row in results if row["ok"])
    avg_latency = round(sum(latencies) / len(latencies), 4) if latencies else 0.0

    return {
        "n_messages": len(messages),
        "n_success": success_count,
        "n_failed": len(messages) - success_count,
        "avg_latency_s": avg_latency,
        "results": results,
    }


def diagnose_claude_setup() -> dict:
    """Return non-secret diagnostics for troubleshooting Claude connectivity."""
    loaded_paths = [str(p) for p in _load_env_files()]
    api_key = _api_key()
    root = _repo_root()
    return {
        "repo_root": str(root),
        "env_files_loaded": loaded_paths,
        "env_file_at_repo_root": (root / ".env").is_file(),
        "api_key_configured": bool(api_key),
        "model": _resolved_model(),
        "accepted_env_vars": list(_ENV_KEY_NAMES),
    }
