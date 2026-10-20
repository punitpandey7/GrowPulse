"""
GrowPulse — Groq LLM client (stdlib only)
=========================================
Loads GROQ_API_KEY from the environment or a local .env file (which is
GITIGNORED — only .env.example is committed) and talks to Groq's
OpenAI-compatible chat completions endpoint via urllib. No SDK required.

    from llm import is_available, chat
    if is_available():
        reply = chat("Say hi", system="You are terse.")

Streamlit users can also paste a key in the sidebar; the app exports it to
the environment before calling the drafting module.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
REPO_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: str | Path | None = None) -> None:
    """Tiny .env parser — KEY=VALUE lines, # comments, no dependencies."""
    path = Path(path) if path else REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:  # real env wins over .env
            os.environ[key] = value


def api_key() -> str | None:
    load_dotenv()
    key = os.environ.get("GROQ_API_KEY", "").strip()
    return key or None


def is_available() -> bool:
    return api_key() is not None


def chat(user: str, system: str = "", model: str | None = None,
         temperature: float = 0.2, max_tokens: int = 1600, timeout: int = 60) -> str:
    """One chat completion. Raises RuntimeError with a clear message on failure."""
    key = api_key()
    if not key:
        raise RuntimeError("GROQ_API_KEY not set (see .env.example)")

    body = {
        "model": model or DEFAULT_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": ([{"role": "system", "content": system}] if system else [])
        + [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # Groq's CDN (Cloudflare) blocks Python's default urllib signature with
            # error 1010, so send an honest, identifiable User-Agent.
            "User-Agent": "GrowPulse/2.0 (github.com/punitpandey7/GrowPulse)",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Groq API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Groq API unreachable: {exc.reason}") from exc

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Groq response shape: {str(data)[:300]}") from exc
