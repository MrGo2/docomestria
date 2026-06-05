"""Native Google Gemini provider via the `google-genai` SDK.

Use this when you want direct access to Gemini-only features (context
caching, file inputs). Most users should prefer `OpenRouter` for the simpler
single-API-key story.
"""

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
class GeminiFlashLite:
    """Gemini provider, defaults to Flash Lite (cheapest in the family)."""

    api_key: str
    model: str = "gemini-2.5-flash-lite"
    timeout_s: float = 60.0

    def complete(
        self,
        system: str,
        user: str,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            from google import genai  # type: ignore[import-not-found]
            from google.genai import types  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "GeminiFlashLite requires `google-genai`. "
                "Install with `pip install docomestria[gemini]`."
            ) from exc

        client = genai.Client(api_key=self.api_key)
        config_kwargs: dict[str, Any] = {"system_instruction": system}
        if response_format and response_format.get("type") == "json_object":
            config_kwargs["response_mime_type"] = "application/json"

        try:
            resp = client.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:  # pragma: no cover - error mapping
            raise _map_exception(exc) from exc

        text = getattr(resp, "text", None) or ""
        if not text:
            raise LLMInvalidResponseError("Gemini returned empty completion")

        usage = getattr(resp, "usage_metadata", None)
        tokens_in = int(getattr(usage, "prompt_token_count", 0) or 0)
        tokens_out = int(getattr(usage, "candidates_token_count", 0) or 0)
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
    if "RateLimit" in name or "ResourceExhausted" in name or "429" in msg:
        return LLMRateLimitError(msg)
    if "Timeout" in name or "DeadlineExceeded" in name:
        return LLMTimeoutError(msg)
    return LLMError(f"{name}: {msg}")


__all__ = ["GeminiFlashLite"]
