"""
Chat API routes — SSE streaming + non-streaming fallback.

Endpoints:
  POST /api/chat/stream        SSE stream of status/meta/delta/done events
  POST /api/chat               non-streaming JSON reply (tests, simple clients)
  GET  /api/chat/session/{id}  session snapshot (slots, chart basis)
  DELETE /api/chat/session/{id}  reset a session
  GET  /api/chat/config        model + key availability for the UI
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..chat.config import CHAT_RATE_LIMIT_PER_MINUTE, DEEPSEEK_MODEL, has_api_key
from ..chat.orchestrator import ChatOrchestrator
from .ratelimit import SlidingWindowLimiter

router = APIRouter(prefix="/api/chat", tags=["chat"])

_orchestrator: Optional[ChatOrchestrator] = None
_lock = threading.Lock()
LIMITER = SlidingWindowLimiter(CHAT_RATE_LIMIT_PER_MINUTE)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(request: Request) -> None:
    key = _client_key(request)
    if not LIMITER.allow(key):
        retry = int(LIMITER.retry_after_seconds(key)) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit reached ({LIMITER.limit} requests/minute). Try again in {retry}s.",
            headers={"Retry-After": str(retry)},
        )


def get_orchestrator() -> ChatOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        with _lock:
            if _orchestrator is None:
                _orchestrator = ChatOrchestrator()
    return _orchestrator


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=8000)
    language: Optional[str] = Field(default=None, max_length=40)


def _sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/config")
def chat_config() -> Dict[str, Any]:
    return {
        "model": DEEPSEEK_MODEL,
        "api_key_configured": has_api_key(),
        "provider": "DeepSeek",
    }


@router.post("/stream")
def chat_stream(req: ChatRequest, request: Request):
    _enforce_rate_limit(request)
    orchestrator = get_orchestrator()
    session = orchestrator.store.get_or_create(req.session_id)
    sid = session.session_id

    def event_generator() -> Iterator[str]:
        yield _sse({"type": "session", "session_id": sid})
        try:
            for event in orchestrator.handle_message(sid, req.message, language=req.language):
                yield _sse(event.to_sse_payload(sid))
        except Exception as exc:  # pragma: no cover - last-resort guard
            yield _sse({"type": "error", "session_id": sid, "message": f"Stream failure: {exc}"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("")
def chat_once(req: ChatRequest, request: Request) -> Dict[str, Any]:
    """Non-streaming fallback: runs the full turn and returns the final reply."""
    _enforce_rate_limit(request)
    orchestrator = get_orchestrator()
    session = orchestrator.store.get_or_create(req.session_id)

    content_parts: List[str] = []
    events: List[Dict[str, Any]] = []
    birth_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    for event in orchestrator.handle_message(session.session_id, req.message, language=req.language):
        payload = event.to_sse_payload(session.session_id)
        events.append(payload)
        if event.type == "delta" and event.data.get("channel") == "content":
            content_parts.append(event.data.get("text", ""))
        elif event.type == "meta":
            birth_data = event.data.get("birth_data")
        elif event.type == "done":
            content_parts = [event.data.get("content", "".join(content_parts))]
            birth_data = event.data.get("birth_data") or birth_data
        elif event.type == "error":
            error = event.data.get("message")

    if error and not "".join(content_parts).strip():
        return {
            "session_id": session.session_id,
            "reply": "",
            "error": error,
            "birth_data": birth_data,
            "events": events,
        }

    return {
        "session_id": session.session_id,
        "reply": "".join(content_parts).strip(),
        "error": error,
        "birth_data": birth_data,
        "topic": session.slots.topic or "general",
        "last_missing": session.last_missing,
        "events": events,
    }


@router.get("/memory")
def chat_memory(limit: int = 20) -> Dict[str, Any]:
    """Long-term memory: profiles (kundali owners) with linked session counts."""
    memory = getattr(get_orchestrator(), "memory", None)
    if memory is None:
        return {"enabled": False, "profiles": []}
    capped = min(max(limit, 1), 50)
    return {"enabled": True, "profiles": memory.list_profiles(limit=capped)}


@router.get("/memory/{profile_id}")
def chat_memory_profile(profile_id: str) -> Dict[str, Any]:
    """Full profile record (structured birth details + kundali)."""
    memory = getattr(get_orchestrator(), "memory", None)
    profile = memory.get(profile_id) if memory is not None else None
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return profile


@router.get("/sessions")
def chat_sessions(limit: int = 20) -> Dict[str, Any]:
    """Recent chat sessions (most recently updated first) for the history panel."""
    capped = min(max(limit, 1), 50)
    sessions = get_orchestrator().store.list_sessions(limit=capped)
    return {"sessions": sessions}


@router.get("/session/{session_id}")
def chat_session(session_id: str) -> Dict[str, Any]:
    session = get_orchestrator().store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id": session.session_id,
        "messages": session.messages,
        "birth_data": session.slots.to_card(),
        "chart_basis": session.chart_basis,
        "kundali": session.kundali,
        "topic": session.slots.topic or "general",
    }


@router.delete("/session/{session_id}")
def delete_chat_session(session_id: str) -> Dict[str, Any]:
    deleted = get_orchestrator().store.delete(session_id)
    return {"deleted": deleted, "session_id": session_id}
