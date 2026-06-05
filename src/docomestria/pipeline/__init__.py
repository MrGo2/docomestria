"""Pipeline orchestrator — fuse → LLM → bind → schema in one call.

Optional sub-package. Install with `pip install docomestria[pipeline]`
plus a provider extra such as `[openrouter]`, `[gemini]`, `[claude]`,
or `[openai]`.
"""

from __future__ import annotations

from .cache import CacheBackend, DiskCache, MemoryCache, build_cache_key
from .context import build_llm_context
from .pipeline import Pipeline
from .prompts import SYSTEM_PROMPT, build_extraction_prompt, build_reprompt
from .result import CostReport, ExtractionResult
from .retry import RetryPolicy

__all__ = [
    "SYSTEM_PROMPT",
    "CacheBackend",
    "CostReport",
    "DiskCache",
    "ExtractionResult",
    "MemoryCache",
    "Pipeline",
    "RetryPolicy",
    "build_cache_key",
    "build_extraction_prompt",
    "build_llm_context",
    "build_reprompt",
]
