"""Native Anthropic Claude provider via the `anthropic` SDK."""

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
class Claude:
    """Direct Anthropic Claude client."""

    api_key: str
    model: str = "claude-haiku-4.5"
    max_tokens: int = 4096
    timeout_s: float = 60.0

    def complete(
        self,
        system: str,
        user: str,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            from anthropic import Anthropic  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "Claude requires the `anthropic` SDK. "
                "Install with `pip install docomestria[claude]`."
            ) from exc

        client = Anthropic(api_key=self.api_key, timeout=self.timeout_s)
        # Claude has no native JSON mode; we rely on prompt discipline.
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # pragma: no cover
            raise _map_exception(exc) from exc

        blocks = getattr(resp, "content", None) or []
        text = ""
        for block in blocks:
            t = getattr(block, "text", None)
            if t:
                text += t
        if not text:
            raise LLMInvalidResponseError("Claude returned empty completion")

        usage = getattr(resp, "usage", None)
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
        return LLMResponse(
            text=text,
            model_used=self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            usd=estimate_usd(self.model, tokens_in, tokens_out),
            raw_response={"text": text},
        )


def _map_exception(exc: Exception) -> LLMError:
    name = type(exc).__name__
    msg = str(exc)
    if "RateLimit" in name or "429" in msg:
        return LLMRateLimitError(msg)
    if "Timeout" in name or "Connection" in name:
        return LLMTimeoutError(msg)
    if "BadRequest" in name or "Invalid" in name:
        return LLMInvalidResponseError(msg)
    return LLMError(f"{name}: {msg}")


__all__ = ["Claude"]
