"""Native OpenAI provider via the `openai` SDK (direct, not via OpenRouter)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import (
    LLMError,
    LLMInvalidResponseError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
)
from .pricing import estimate_usd


@dataclass(frozen=True)
class OpenAINative:
    """Direct OpenAI client (not via OpenRouter)."""

    api_key: str
    model: str = "gpt-5-nano"
    timeout_s: float = 60.0

    def complete(
        self,
        system: str,
        user: str,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "OpenAINative requires the `openai` SDK. "
                "Install with `pip install docomestria[openai]`."
            ) from exc

        client = OpenAI(api_key=self.api_key, timeout=self.timeout_s)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        try:
            raw = client.chat.completions.create(**kwargs)
        except Exception as exc:  # pragma: no cover
            raise _map_exception(exc) from exc

        try:
            raw_dict = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
        except Exception:  # pragma: no cover
            raw_dict = {}

        choices = raw_dict.get("choices") or []
        text = ""
        if choices:
            msg = choices[0].get("message") or {}
            text = msg.get("content") or ""
        if not text:
            raise LLMInvalidResponseError("OpenAI returned empty completion")

        usage = raw_dict.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        return LLMResponse(
            text=text,
            model_used=raw_dict.get("model") or self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            usd=estimate_usd(self.model, tokens_in, tokens_out),
            raw_response=raw_dict,
        )


def _map_exception(exc: Exception) -> LLMError:
    name = type(exc).__name__
    msg = str(exc)
    if "RateLimit" in name or "Quota" in name or "429" in msg:
        return LLMRateLimitError(msg)
    if "Timeout" in name or "Connection" in name:
        return LLMTimeoutError(msg)
    if "BadRequest" in name or "Invalid" in name:
        return LLMInvalidResponseError(msg)
    return LLMError(f"{name}: {msg}")


__all__ = ["OpenAINative"]
