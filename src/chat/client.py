"""
Minimal DeepSeek chat client (OpenAI-compatible) built on httpx.

Supports:
- complete()      : single-shot completion
- complete_json() : JSON-object mode for structured extraction
- stream()        : SSE streaming yielding reasoning/content deltas separately

The DeepSeek "flash" family is a reasoning model: it emits `reasoning_content`
deltas plus the final `content`. Both are exposed distinctly so the UI can show
a collapsible thinking pane without polluting the answer.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterator, List, Optional

import httpx

from .config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MAX_TOKENS,
    DEEPSEEK_MODEL,
    DEEPSEEK_TIMEOUT,
)


class DeepSeekError(RuntimeError):
    """Raised when the DeepSeek API cannot fulfil a request."""


class DeepSeekHTTPError(DeepSeekError):
    """HTTP-level failure with the status code preserved for retry policy."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def extract_json_object(raw: str) -> Dict[str, Any]:
    """Parses a JSON object out of a model reply, tolerating code fences."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text[:4].lower() == "json":
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise DeepSeekError(f"Model did not return a JSON object: {raw[:200]!r}")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise DeepSeekError(f"Model returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DeepSeekError("Model JSON response was not an object.")
    return data


class DeepSeekClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.api_key = (DEEPSEEK_API_KEY if api_key is None else api_key or "").strip()
        self.base_url = (base_url or DEEPSEEK_BASE_URL).rstrip("/")
        self.model = (model or DEEPSEEK_MODEL).strip()
        self.timeout = float(DEEPSEEK_TIMEOUT if timeout is None else timeout)
        self.max_tokens = int(DEEPSEEK_MAX_TOKENS if max_tokens is None else max_tokens)
        self.transport = transport

    # ------------------------------------------------------------------ utils
    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise DeepSeekError(
                "DEEPSEEK_API_KEY is not configured. Add it to SweetAstro/.env "
                "(DEEPSEEK_API_KEY=sk-...) or export it in the environment."
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _body(
        self,
        messages: List[Dict[str, str]],
        *,
        stream: bool,
        json_mode: bool,
        max_tokens: Optional[int],
        temperature: float,
        thinking: Optional[bool],
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "max_tokens": int(max_tokens or self.max_tokens),
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if thinking is False:
            # DeepSeek flash supports disabling the reasoning phase entirely.
            body["thinking"] = {"type": "disabled"}
        return body

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return
        detail = ""
        try:
            payload = resp.json()
            detail = (payload.get("error") or {}).get("message") or json.dumps(payload)[:300]
        except Exception:
            detail = (resp.text or "")[:300]
        raise DeepSeekHTTPError(resp.status_code, f"DeepSeek API error {resp.status_code}: {detail}")

    # -------------------------------------------------------------- complete
    def complete(
        self,
        messages: List[Dict[str, str]],
        *,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        thinking: Optional[bool] = None,
        retries: int = 1,
    ) -> str:
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                    resp = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=self._body(
                            messages,
                            stream=False,
                            json_mode=json_mode,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            thinking=thinking,
                        ),
                    )
                self._raise_for_status(resp)
                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise DeepSeekError("DeepSeek returned no completion choices.")
                choice = choices[0]
                content = (choice.get("message") or {}).get("content") or ""
                if not content and choice.get("finish_reason") == "length":
                    raise DeepSeekError(
                        "DeepSeek response was truncated before any content "
                        "(increase DEEPSEEK_MAX_TOKENS or reduce reasoning)."
                    )
                return content
            except DeepSeekHTTPError as exc:
                # Only transient failures are retried: rate limits and 5xx.
                retryable = exc.status_code == 429 or exc.status_code >= 500
                if retryable and attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
            except httpx.HTTPError as exc:
                # Network-level failures are retried; bad requests are not.
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise DeepSeekError(f"DeepSeek request failed: {exc}") from exc

    def complete_json(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
        thinking: Optional[bool] = False,
    ) -> Dict[str, Any]:
        raw = self.complete(
            messages, json_mode=True, max_tokens=max_tokens,
            temperature=temperature, thinking=thinking,
        )
        return extract_json_object(raw)

    # ---------------------------------------------------------------- stream
    def stream(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        thinking: Optional[bool] = None,
    ) -> Iterator[Dict[str, str]]:
        """Yields {"type": "reasoning"|"content", "text": ...} deltas."""
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._body(
                    messages,
                    stream=True,
                    json_mode=False,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    thinking=thinking,
                ),
            ) as resp:
                self._raise_for_status(resp)
                content_seen = False
                reasoning_seen = False
                finish_reason: Optional[str] = None
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    finish_reason = choices[0].get("finish_reason") or finish_reason
                    delta = choices[0].get("delta") or {}
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        reasoning_seen = True
                        yield {"type": "reasoning", "text": reasoning}
                    content = delta.get("content")
                    if content:
                        content_seen = True
                        yield {"type": "content", "text": content}

                if finish_reason == "length" and reasoning_seen and not content_seen:
                    raise DeepSeekError(
                        "The reasoning phase used the entire token budget, so no answer text was "
                        "produced. Retry, ask a shorter question, or set "
                        "DEEPSEEK_ANSWER_THINKING=off for the fast mode."
                    )
