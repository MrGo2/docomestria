"""LLM provider protocol and shared response/error types.

Each provider in this package implements `LLMProvider.complete()` and returns
an `LLMResponse`. The pipeline orchestrator depends only on this protocol,
which keeps the SDK imports lazy and per-provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class LLMResponse:
    """Outcome of a single LLM call.

    `usd` is the actual cost when the provider returns it (OpenRouter), or an
    estimate derived from a local pricing table for native providers.
    """

    text: str
    model_used: str
    tokens_in: int
    tokens_out: int
    usd: float
    raw_response: dict[str, Any] = field(default_factory=dict)


class LLMError(Exception):
    """Base class for all provider errors."""


class LLMRateLimitError(LLMError):
    """Raised when the provider returns a 429 / quota exceeded."""


class LLMTimeoutError(LLMError):
    """Raised on connection or read timeouts."""


class LLMInvalidResponseError(LLMError):
    """Raised when the provider response cannot be parsed."""


@runtime_checkable
class LLMProvider(Protocol):
    """Minimum contract every provider must satisfy."""

    def complete(
        self,
        system: str,
        user: str,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse: ...


__all__ = [
    "LLMError",
    "LLMInvalidResponseError",
    "LLMProvider",
    "LLMRateLimitError",
    "LLMResponse",
    "LLMTimeoutError",
]
