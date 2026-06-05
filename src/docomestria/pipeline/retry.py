"""Retry policy for transient LLM errors."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, TypeVar

from .providers.base import LLMError, LLMRateLimitError, LLMTimeoutError

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """Wraps a callable, retrying on selected exception types."""

    max_retries: int = 3
    backoff: Literal["none", "linear", "exponential"] = "exponential"
    initial_delay_s: float = 1.0
    retry_on: tuple[type[Exception], ...] = field(
        default_factory=lambda: (LLMRateLimitError, LLMTimeoutError)
    )

    def call(self, fn: Callable[[], T], *, sleep: Callable[[float], None] = time.sleep) -> T:
        """Execute `fn`, retrying on configured errors with backoff."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return fn()
            except self.retry_on as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                sleep(self._delay(attempt))
        if last_exc is None:  # pragma: no cover - defensive
            raise LLMError("RetryPolicy: no exception captured")
        raise last_exc

    def _delay(self, attempt: int) -> float:
        if self.backoff == "none":
            return 0.0
        if self.backoff == "linear":
            return self.initial_delay_s * (attempt + 1)
        return self.initial_delay_s * (2**attempt)


__all__ = ["RetryPolicy"]
