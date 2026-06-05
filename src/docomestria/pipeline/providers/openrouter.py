"""OpenRouter provider — the recommended default.

One API key buys access to 200+ models. The provider supports two ways to
get fallback behavior:

  - Pass a fallback chain via `models=(...)`. With `route="fallback"`, this
    walks the chain locally — if model N fails, the next is tried. With
    `route="lowest-cost"` or `"fastest"`, the list is delegated to
    OpenRouter via the `models` request body parameter.
  - Pass a single `model=...` for the simple case.

We use the official `openai` SDK with a custom `base_url`; OpenRouter is
OpenAI-API-compatible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .base import (
    LLMError,
    LLMInvalidResponseError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class OpenRouter:
    """OpenRouter-backed LLM provider.

    Either `model` or `models` must be provided. When `models` is set and
    `route == "fallback"`, the provider walks the chain locally; otherwise the
    list is forwarded to OpenRouter as the request-level `models` parameter.
    """

    api_key: str
    model: str | None = None
    models: tuple[str, ...] = field(default_factory=tuple)
    route: Literal["fallback", "lowest-cost", "fastest"] = "fallback"
    site_url: str | None = None
    app_name: str | None = "docomestria"
    timeout_s: float = 60.0
    extra_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model and not self.models:
            raise ValueError("Provide either `model` or `models`")

    # ------------------------------------------------------------------ API

    def complete(
        self,
        system: str,
        user: str,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        client = self._client()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        headers = self._build_headers()

        if self.models and self.route == "fallback":
            return self._walk_fallback(client, messages, response_format, headers)
        return self._call_once(
            client,
            self._effective_model(),
            messages,
            response_format,
            headers,
            extra_models=self._extra_models_param(),
        )

    # -------------------------------------------------------------- helpers

    def _client(self) -> Any:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised by user envs
            raise LLMError(
                "OpenRouter requires the `openai` SDK. Install with "
                "`pip install docomestria[openrouter]`."
            ) from exc

        return OpenAI(
            api_key=self.api_key,
            base_url=OPENROUTER_BASE_URL,
            timeout=self.timeout_s,
        )

    def _build_headers(self) -> dict[str, str]:
        headers = dict(self.extra_headers)
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers

    def _effective_model(self) -> str:
        if self.model:
            return self.model
        return self.models[0]

    def _extra_models_param(self) -> tuple[str, ...] | None:
        """Delegate fallback to OpenRouter via request body `models` field."""
        if not self.models:
            return None
        if self.route == "fallback":
            return None
        # lowest-cost / fastest → let OpenRouter pick from the list.
        return self.models

    def _walk_fallback(
        self,
        client: Any,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> LLMResponse:
        last_exc: Exception | None = None
        for candidate in self.models:
            try:
                return self._call_once(
                    client, candidate, messages, response_format, headers, extra_models=None
                )
            except (LLMRateLimitError, LLMTimeoutError, LLMInvalidResponseError) as exc:
                last_exc = exc
                continue
            except LLMError as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            raise last_exc
        raise LLMError("OpenRouter fallback chain exhausted with no models tried")

    def _call_once(
        self,
        client: Any,
        model: str,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None,
        headers: dict[str, str],
        *,
        extra_models: tuple[str, ...] | None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "extra_headers": headers or None,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        extra_body: dict[str, Any] = {}
        if extra_models is not None:
            extra_body["models"] = list(extra_models)
            extra_body["route"] = self.route
        # Ask OpenRouter to include cost in the usage payload.
        extra_body["usage"] = {"include": True}
        kwargs["extra_body"] = extra_body

        try:
            raw = client.chat.completions.create(**kwargs)
        except Exception as exc:  # pragma: no cover - error class mapping
            raise _map_exception(exc) from exc

        return _to_llm_response(raw, fallback_model=model)


# ----------------------------------------------------------- exception mapping


def _map_exception(exc: Exception) -> LLMError:
    """Best-effort mapping of openai SDK errors to docomestria errors."""
    name = type(exc).__name__
    if "RateLimit" in name or "Quota" in name:
        return LLMRateLimitError(str(exc))
    if "Timeout" in name or "Connection" in name:
        return LLMTimeoutError(str(exc))
    if "APIStatus" in name or "BadRequest" in name or "Invalid" in name:
        return LLMInvalidResponseError(str(exc))
    return LLMError(f"{name}: {exc}")


def _to_llm_response(raw: Any, *, fallback_model: str) -> LLMResponse:
    """Convert an openai SDK response object into LLMResponse."""
    text = ""
    model_used = fallback_model
    tokens_in = 0
    tokens_out = 0
    usd = 0.0
    raw_dict: dict[str, Any] = {}

    try:
        raw_dict = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
    except Exception:  # pragma: no cover - defensive
        raw_dict = {}

    choices = raw_dict.get("choices") or []
    if choices:
        msg = choices[0].get("message") or {}
        text = msg.get("content") or ""

    model_used = raw_dict.get("model") or fallback_model

    usage = raw_dict.get("usage") or {}
    tokens_in = int(usage.get("prompt_tokens") or 0)
    tokens_out = int(usage.get("completion_tokens") or 0)
    # OpenRouter exposes cost inside usage when extra_body.usage.include=True.
    cost_field = usage.get("cost")
    if cost_field is not None:
        try:
            usd = float(cost_field)
        except (TypeError, ValueError):
            usd = 0.0

    if not text:
        raise LLMInvalidResponseError("OpenRouter returned an empty completion")

    return LLMResponse(
        text=text,
        model_used=model_used,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        usd=usd,
        raw_response=raw_dict,
    )


__all__ = ["OPENROUTER_BASE_URL", "OpenRouter"]
