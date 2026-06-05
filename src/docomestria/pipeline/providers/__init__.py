"""LLM providers for the pipeline orchestrator.

`OpenRouter` is the recommended default — one API key, 200+ models,
built-in fallback, accurate cost reporting.

`GeminiFlashLite`, `Claude`, and `OpenAINative` are direct SDK wrappers for
users who prefer the native APIs.
"""

from __future__ import annotations

from .base import (
    LLMError,
    LLMInvalidResponseError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
)
from .claude import Claude
from .gemini import GeminiFlashLite
from .openai_native import OpenAINative
from .openrouter import OPENROUTER_BASE_URL, OpenRouter

__all__ = [
    "OPENROUTER_BASE_URL",
    "Claude",
    "GeminiFlashLite",
    "LLMError",
    "LLMInvalidResponseError",
    "LLMProvider",
    "LLMRateLimitError",
    "LLMResponse",
    "LLMTimeoutError",
    "OpenAINative",
    "OpenRouter",
]
