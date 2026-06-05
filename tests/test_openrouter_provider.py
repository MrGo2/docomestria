"""Mock-based tests for the OpenRouter provider.

We patch the openai SDK to verify base_url, headers, and fallback semantics
without making any network calls.
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any

import pytest

from docomestria.pipeline.providers.base import LLMError, LLMRateLimitError
from docomestria.pipeline.providers.openrouter import OPENROUTER_BASE_URL, OpenRouter


class _FakeChatCompletion:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self) -> dict[str, Any]:
        return self._payload


class _FakeCompletions:
    def __init__(self, sink: list[dict[str, Any]], scripted: list[Any]) -> None:
        self.sink = sink
        self.scripted = list(scripted)

    def create(self, **kwargs):
        self.sink.append(kwargs)
        outcome = self.scripted.pop(0) if self.scripted else _ok_response("openai/gpt-x")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeChat:
    def __init__(self, sink, scripted):
        self.completions = _FakeCompletions(sink, scripted)


class _FakeClient:
    def __init__(self, init_sink, sink, scripted, **kwargs):
        init_sink.append(kwargs)
        self.chat = _FakeChat(sink, scripted)


def _ok_response(model: str, usd: float = 0.0001) -> _FakeChatCompletion:
    return _FakeChatCompletion(
        {
            "model": model,
            "choices": [{"message": {"content": json.dumps({"hello": "world"})}}],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "cost": usd,
            },
        }
    )


@pytest.fixture
def fake_openai(monkeypatch):
    init_sink: list[dict[str, Any]] = []
    call_sink: list[dict[str, Any]] = []
    scripted: list[Any] = []

    def factory(**kwargs):
        return _FakeClient(init_sink, call_sink, scripted, **kwargs)

    module = types.ModuleType("openai")
    module.OpenAI = factory  # type: ignore[attr-defined]

    class _RateLimitError(Exception):
        pass

    module.RateLimitError = _RateLimitError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", module)
    return init_sink, call_sink, scripted


def test_openrouter_sets_base_url_and_headers(fake_openai):
    init_sink, call_sink, scripted = fake_openai
    scripted.append(_ok_response("google/gemini-2.5-flash-lite"))

    provider = OpenRouter(
        api_key="sk-test",
        model="google/gemini-2.5-flash-lite",
        site_url="https://docomestria.dev",
    )
    resp = provider.complete("sys", "user")

    assert init_sink[0]["base_url"] == OPENROUTER_BASE_URL
    assert init_sink[0]["api_key"] == "sk-test"
    headers = call_sink[0]["extra_headers"]
    assert headers["HTTP-Referer"] == "https://docomestria.dev"
    assert headers["X-Title"] == "docomestria"
    assert resp.model_used == "google/gemini-2.5-flash-lite"
    assert resp.usd == pytest.approx(0.0001)
    assert resp.tokens_in == 50
    assert resp.tokens_out == 10


def test_openrouter_response_format_passed_through(fake_openai):
    init_sink, call_sink, scripted = fake_openai
    scripted.append(_ok_response("anthropic/claude-haiku-4.5"))

    provider = OpenRouter(api_key="k", model="anthropic/claude-haiku-4.5")
    provider.complete("sys", "user", response_format={"type": "json_object"})

    assert call_sink[0]["response_format"] == {"type": "json_object"}


def test_openrouter_fallback_chain_walks_models_locally(fake_openai):
    init_sink, call_sink, scripted = fake_openai
    scripted.extend(
        [LLMRateLimitError("first model rate-limited"), _ok_response("anthropic/claude-haiku-4.5")]
    )

    provider = OpenRouter(
        api_key="k",
        models=("google/gemini-2.5-flash-lite", "anthropic/claude-haiku-4.5"),
        route="fallback",
    )
    resp = provider.complete("sys", "user")

    models_tried = [call["model"] for call in call_sink]
    assert models_tried == [
        "google/gemini-2.5-flash-lite",
        "anthropic/claude-haiku-4.5",
    ]
    assert resp.model_used == "anthropic/claude-haiku-4.5"


def test_openrouter_lowest_cost_delegates_to_openrouter(fake_openai):
    init_sink, call_sink, scripted = fake_openai
    scripted.append(_ok_response("anthropic/claude-haiku-4.5"))

    provider = OpenRouter(
        api_key="k",
        models=("google/gemini-2.5-flash-lite", "anthropic/claude-haiku-4.5"),
        route="lowest-cost",
    )
    provider.complete("sys", "user")

    body = call_sink[0]["extra_body"]
    assert body["models"] == [
        "google/gemini-2.5-flash-lite",
        "anthropic/claude-haiku-4.5",
    ]
    assert body["route"] == "lowest-cost"


def test_openrouter_requires_model_or_models():
    with pytest.raises(ValueError):
        OpenRouter(api_key="k")


def test_openrouter_propagates_error_after_chain_exhausted(fake_openai):
    init_sink, call_sink, scripted = fake_openai
    scripted.extend([LLMRateLimitError("a"), LLMRateLimitError("b")])

    provider = OpenRouter(
        api_key="k",
        models=("a/x", "b/y"),
        route="fallback",
    )
    with pytest.raises(LLMError):
        provider.complete("sys", "user")
