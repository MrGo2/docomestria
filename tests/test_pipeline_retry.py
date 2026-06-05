"""Retry policy tests — verifies backoff and max_retries semantics."""

from __future__ import annotations

import pytest

from docomestria.pipeline import RetryPolicy
from docomestria.pipeline.providers.base import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)


def test_retry_returns_value_on_first_attempt():
    policy = RetryPolicy(max_retries=2)
    assert policy.call(lambda: 42) == 42


def test_retry_retries_on_rate_limit_then_succeeds():
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky() -> int:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise LLMRateLimitError("slow down")
        return 7

    policy = RetryPolicy(max_retries=3, backoff="exponential", initial_delay_s=1.0)
    assert policy.call(flaky, sleep=sleeps.append) == 7
    assert attempts["n"] == 3
    assert sleeps == [1.0, 2.0]  # 2 backoffs before the successful 3rd call


def test_retry_raises_after_max_retries():
    policy = RetryPolicy(max_retries=2, backoff="none")

    def always_fails() -> int:
        raise LLMTimeoutError("nope")

    with pytest.raises(LLMTimeoutError):
        policy.call(always_fails, sleep=lambda _s: None)


def test_retry_does_not_catch_unlisted_exception():
    policy = RetryPolicy(max_retries=3, backoff="none", retry_on=(LLMRateLimitError,))

    def explodes() -> int:
        raise LLMError("untyped")

    with pytest.raises(LLMError):
        policy.call(explodes, sleep=lambda _s: None)


def test_retry_linear_backoff_progression():
    sleeps: list[float] = []
    attempts = {"n": 0}

    def flaky() -> int:
        attempts["n"] += 1
        if attempts["n"] < 4:
            raise LLMRateLimitError("x")
        return 1

    policy = RetryPolicy(max_retries=5, backoff="linear", initial_delay_s=0.5)
    policy.call(flaky, sleep=sleeps.append)
    assert sleeps == [0.5, 1.0, 1.5]
