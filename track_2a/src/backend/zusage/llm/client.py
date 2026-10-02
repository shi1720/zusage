"""Minimal, dependency-light client for any OpenAI-compatible chat endpoint.

Apertus 1.5 is served by many stacks (CSCS, vLLM, llama.cpp, Ollama, MLX,
Public AI, Infomaniak). They all speak ``POST {base}/chat/completions`` but
differ in the details, so this client is defensive by design:

- ``response_format={"type": "json_object"}`` is sent when supported and
  silently dropped forever after the first server that rejects it;
- JSON is extracted tolerantly (code fences, leading prose, trailing commas);
- exactly ONE repair retry is attempted if the output is not valid JSON, and
  every attempt is counted - the FHGR budget is "< 5 LLM calls per answer",
  so we measure it instead of assuming it;
- Apertus "thinking" is explicitly disabled (``enable_thinking: false``):
  it would add latency without improving short structured outputs.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

log = logging.getLogger("zusage.llm")


class LLMError(RuntimeError):
    """codes: unreachable | auth | rate_limited | timeout | bad_output | server"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Usage:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0

    def add(self, other: Usage) -> None:
        self.calls += other.calls
        self.tokens_in += other.tokens_in
        self.tokens_out += other.tokens_out
        self.latency_ms += other.latency_ms

    def as_dict(self) -> dict:
        return {
            "calls": self.calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_ms": self.latency_ms,
        }


@dataclass
class JSONResult:
    data: dict
    raw: str
    model: str
    usage: Usage = field(default_factory=Usage)


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_THINK = re.compile(r"<\|inner_prefix\|>.*?<\|inner_suffix\|>", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """Best-effort extraction of the first JSON object in ``text``."""
    if not text:
        return None
    text = _THINK.sub("", text).strip()
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    for candidate in candidates:
        start = candidate.find("{")
        if start < 0:
            continue
        depth, in_str, escape = 0, False, False
        for i in range(start, len(candidate)):
            ch = candidate[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blob = candidate[start : i + 1]
                    for attempt in (blob, _TRAILING_COMMA.sub(r"\1", blob)):
                        try:
                            parsed = json.loads(attempt)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(parsed, dict):
                            return parsed
                    break
    return None


class ChatClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout_s: float = 60.0,
        temperature: float = 0.3,
        json_mode: bool = True,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 4,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.json_mode = json_mode
        self.max_retries = max_retries
        headers = {"User-Agent": "Zusage/1.0 (+https://github.com/shi1720/zusage)"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.Client(timeout=timeout_s, headers=headers, transport=transport)

    # ------------------------------------------------------------------
    def _post(self, messages: list[dict], max_tokens: int, json_mode: bool) -> tuple[str, Usage]:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            # Apertus chat template: keep deliberation off for low latency.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        try:
            resp = self._http.post(f"{self.base_url}/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMError("timeout", f"LLM timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise LLMError("unreachable", f"LLM unreachable: {exc}") from exc
        latency = int((time.perf_counter() - started) * 1000)

        if resp.status_code == 400 and (json_mode or "chat_template_kwargs" in resp.text):
            # Some servers reject unknown fields - retry once in plain mode.
            raise _Downgrade()
        if resp.status_code in (401, 403):
            raise LLMError("auth", "The LLM endpoint rejected the API key.")
        if resp.status_code == 429:
            err = LLMError("rate_limited", "The LLM endpoint is rate limiting requests.")
            with contextlib.suppress(ValueError):
                err.retry_after = float(resp.headers.get("retry-after", "0")) or None  # type: ignore[attr-defined]
            raise err
        if resp.status_code >= 400:
            raise LLMError("server", f"LLM error {resp.status_code}: {resp.text[:300]}")

        return self._decode(resp, latency)

    @staticmethod
    def _decode(resp: httpx.Response, latency: int) -> tuple[str, Usage]:
        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            if content is None:
                content = ""
            if not isinstance(content, str):
                raise TypeError("content must be text")
            usage = body.get("usage") or {}
            return content, Usage(
                calls=1,
                tokens_in=int(usage.get("prompt_tokens") or 0),
                tokens_out=int(usage.get("completion_tokens") or 0),
                latency_ms=latency,
            )
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMError("bad_output", "The LLM endpoint returned an invalid response") from exc

    def _post_adaptive(self, messages: list[dict], max_tokens: int) -> tuple[str, Usage]:
        """POST with retries: 429 / 5xx / timeouts back off exponentially (honouring
        Retry-After). Only successful completions count as model calls."""
        delay = 1.5
        for attempt in range(self.max_retries + 1):
            try:
                return self._post_once(messages, max_tokens)
            except LLMError as exc:
                if exc.code not in ("rate_limited", "server", "timeout", "unreachable") or attempt == self.max_retries:
                    raise
                wait = getattr(exc, "retry_after", None) or delay
                log.info("LLM %s - retrying in %.1fs (attempt %d)", exc.code, wait, attempt + 1)
                time.sleep(min(wait, 30))
                delay *= 2
        raise LLMError("server", "unreachable")  # pragma: no cover

    def _post_once(self, messages: list[dict], max_tokens: int) -> tuple[str, Usage]:
        try:
            return self._post(messages, max_tokens, self.json_mode)
        except _Downgrade:
            log.info("endpoint rejected json_mode/template kwargs - falling back to plain requests")
            self.json_mode = False
            return self._post_plain(messages, max_tokens)

    def _post_plain(self, messages: list[dict], max_tokens: int) -> tuple[str, Usage]:
        payload = {"model": self.model, "messages": messages, "temperature": self.temperature, "max_tokens": max_tokens}
        started = time.perf_counter()
        try:
            resp = self._http.post(f"{self.base_url}/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMError("timeout", "LLM request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError("unreachable", f"LLM unreachable: {exc}") from exc
        if resp.status_code in (401, 403):
            raise LLMError("auth", "The LLM endpoint rejected the API key.")
        if resp.status_code == 429:
            raise LLMError("rate_limited", "The LLM endpoint is rate limiting requests.")
        if resp.status_code >= 400:
            raise LLMError("server", f"LLM error {resp.status_code}: {resp.text[:300]}")
        return self._decode(resp, int((time.perf_counter() - started) * 1000))

    # ------------------------------------------------------------------
    def complete_json(self, system: str, user: str, *, max_tokens: int = 900) -> JSONResult:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        total = Usage()
        raw, usage = self._post_adaptive(messages, max_tokens)
        total.add(usage)
        data = extract_json(raw)
        if data is None:
            # One repair attempt, counted against the budget.
            messages += [
                {"role": "assistant", "content": raw[:2000]},
                {"role": "user", "content": "That was not valid JSON. Reply again with ONLY the JSON object."},
            ]
            raw, usage = self._post_adaptive(messages, max_tokens)
            total.add(usage)
            data = extract_json(raw)
        if data is None:
            raise LLMError("bad_output", f"Model did not return JSON: {raw[:200]!r}")
        return JSONResult(data=data, raw=raw, model=self.model, usage=total)

    def ping(self) -> tuple[bool, str]:
        """Cheap health check used by /api/health and the setup screen."""
        try:
            raw, _ = self._post_adaptive([{"role": "user", "content": "Reply with the word: ok"}], 5)
            return True, raw.strip()[:40]
        except LLMError as exc:
            return False, f"{exc.code}: {exc}"


class _Downgrade(Exception):
    pass
