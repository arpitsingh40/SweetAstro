"""
Chat layer configuration — environment driven with optional .env support.
The DeepSeek key is never hard-coded; it lives in .env (git-ignored) or the
process environment.
"""

import logging
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def _load_dotenv() -> None:
    """Load .env without requiring python-dotenv (falls back to a tiny parser)."""
    if not _ENV_FILE.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_ENV_FILE, override=False)
        return
    except ImportError:
        pass
    try:
        for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
    except OSError:
        pass


_load_dotenv()

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash").strip() or "deepseek-flash"
DEEPSEEK_TIMEOUT = float(os.environ.get("DEEPSEEK_TIMEOUT", "180"))
DEEPSEEK_MAX_TOKENS = int(os.environ.get("DEEPSEEK_MAX_TOKENS", "8000"))
CHAT_HISTORY_LIMIT = int(os.environ.get("CHAT_HISTORY_LIMIT", "8"))
CHAT_MAX_SESSIONS = int(os.environ.get("CHAT_MAX_SESSIONS", "500"))

# Production knobs
# Optional API token: when set, every /api/* route except the exempt ones
# requires header `X-Auth-Token` (or `Authorization: Bearer <token>`).
API_TOKEN = os.environ.get("SWEETASTRO_API_TOKEN", "").strip()
# Per-client requests per minute for the chat endpoints (LLM cost guard).
CHAT_RATE_LIMIT_PER_MINUTE = int(os.environ.get("CHAT_RATE_LIMIT_PER_MINUTE", "20"))
# Opt-in session persistence to disk (off by default: chats contain birth data).
CHAT_PERSIST = os.environ.get("CHAT_PERSIST", "0").strip().lower() in ("1", "true", "yes", "on")
CHAT_PERSIST_PATH = Path(os.environ.get(
    "CHAT_PERSIST_PATH",
    str(_PROJECT_ROOT / "data" / "chat_sessions" / "sessions.json"),
))

# Reasoning ("thinking") control. The flash model supports
# {"thinking": {"type": "disabled"}} which removes the 10-30s reasoning phase
# before the answer starts. Extraction/guide calls always disable it; final
# answers now default to reasoning ON because evidence chains are the product
# (generic replies trace back to a disabled thinking phase). Set
# DEEPSEEK_ANSWER_THINKING=off for the fastest (lower-reasoning) mode.
_ANSWER_THINKING_ENV = os.environ.get("DEEPSEEK_ANSWER_THINKING", "on").strip().lower()
DEEPSEEK_ANSWER_THINKING = _ANSWER_THINKING_ENV not in ("0", "false", "no", "off", "disabled")


def has_api_key() -> bool:
    return bool(DEEPSEEK_API_KEY)


def _setup_package_logging() -> None:
    """Route the 'sweetastro' logger to stderr so stage timings are visible."""
    logger = logging.getLogger("sweetastro")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S"
        ))
        logger.addHandler(handler)
    logger.setLevel(os.environ.get("SWEETASTRO_LOG_LEVEL", "INFO").upper())


_setup_package_logging()
