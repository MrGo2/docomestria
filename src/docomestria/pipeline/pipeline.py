"""`Pipeline` — fuse → context → LLM → bind → schema → trace, in one call."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from ..llm.models import BoundValue, ProvenanceIssue
from ..llm.provenance import bind_provenance
from ..llm.validation import detect_hallucinations, detect_role_mismatches
from ..result import FusionResult
from .cache import CacheBackend, DiskCache, build_cache_key
from .context import build_llm_context
from .prompts import SYSTEM_PROMPT, build_extraction_prompt, build_reprompt
from .providers.base import LLMProvider, LLMResponse
from .result import CostReport, ExtractionResult
from .retry import RetryPolicy

# Type alias for the fuse hook (kept open for tests).
FuseFn = Callable[[str | Path], FusionResult]

HallucinationPolicy = Literal["flag", "drop", "retry_llm"]

JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


class Pipeline:
    """End-to-end extraction orchestrator.

    The pipeline is intentionally mutable (not a frozen dataclass) because it
    composes long-lived collaborators (cache, retry, provider) that benefit
    from a regular __init__. Every value it *returns* is immutable.
    """

    def __init__(
        self,
        *,
        schema: Any,
        llm: LLMProvider,
        cache_dir: str | None = ".docomestria_cache",
        cache: CacheBackend | None = None,
        retry: RetryPolicy | None = None,
        on_hallucination: HallucinationPolicy = "flag",
        on_low_confidence_field: float = 0.0,
        fuse_fn: FuseFn | None = None,
    ) -> None:
        self.schema = schema
        self.llm = llm
        self.retry = retry or RetryPolicy()
        self.on_hallucination = on_hallucination
        self.on_low_confidence_field = on_low_confidence_field
        self._fuse_fn = fuse_fn
        if cache is not None:
            self.cache: CacheBackend | None = cache
        elif cache_dir is None:
            self.cache = None
        else:
            self.cache = DiskCache(cache_dir=cache_dir)

    # ----------------------------------------------------------------- API

    def run(self, pdf_path: str | Path) -> ExtractionResult:
        started = time.perf_counter()
        cache_key = self._cache_key(pdf_path)

        cached = self._cache_get(cache_key)
        if cached is not None:
            return _with_cache_hit(cached)

        fusion = self._fuse(pdf_path)
        context = build_llm_context(fusion.items)
        prompt = build_extraction_prompt(self.schema, context)

        llm_calls: list[LLMResponse] = []
        response = self._call_llm(SYSTEM_PROMPT, prompt)
        llm_calls.append(response)
        parsed = _parse_json(response.text)

        bound = bind_provenance(parsed, list(fusion.items))
        bound, llm_calls = self._maybe_reprompt(bound, fusion, context, llm_calls)

        issues = _collect_issues(
            bound,
            policy=self.on_hallucination,
            low_conf_threshold=self.on_low_confidence_field,
        )
        if self.on_hallucination == "drop":
            bound = _drop_hallucinations(bound)

        typed = self.schema.apply(bound, fusion)
        cost = _aggregate_cost(llm_calls)
        duration_ms = int((time.perf_counter() - started) * 1000)

        result = ExtractionResult(
            typed_fields=typed,
            issues=tuple(issues),
            fusion=fusion,
            bound=tuple(bound),
            cost=cost,
            duration_ms=duration_ms,
            cache_hit=False,
            llm_calls=len(llm_calls),
        )
        self._cache_set(cache_key, result)
        return result

    # ------------------------------------------------------------ internals

    def _fuse(self, pdf_path: str | Path) -> FusionResult:
        if self._fuse_fn is not None:
            return self._fuse_fn(pdf_path)
        from ..fusion import fuse  # lazy: avoid importing engines at module load

        return fuse(pdf_path)

    def _call_llm(self, system: str, user: str) -> LLMResponse:
        return self.retry.call(
            lambda: self.llm.complete(system, user, response_format={"type": "json_object"})
        )

    def _maybe_reprompt(
        self,
        bound: list[BoundValue],
        fusion: FusionResult,
        context: dict[str, Any],
        llm_calls: list[LLMResponse],
    ) -> tuple[list[BoundValue], list[LLMResponse]]:
        """Optionally re-prompt for hallucinations / low-confidence fields."""
        hallucinated = tuple(bv.field_name for bv in bound if bv.match_method == "not_found")
        low_conf = ()
        if self.on_low_confidence_field > 0:
            low_conf = tuple(
                bv.field_name
                for bv in bound
                if bv.match_method != "not_found" and bv.match_score < self.on_low_confidence_field
            )

        needs_rerun = (self.on_hallucination == "retry_llm" and hallucinated) or low_conf
        if not needs_rerun:
            return bound, llm_calls

        prompt = build_reprompt(
            self.schema, context, hallucinated=hallucinated, low_confidence=low_conf
        )
        response = self._call_llm(SYSTEM_PROMPT, prompt)
        llm_calls.append(response)
        parsed = _parse_json(response.text)
        bound = bind_provenance(parsed, list(fusion.items))
        return bound, llm_calls

    # --------------------------------------------------------------- cache

    def _cache_key(self, pdf_path: str | Path) -> str | None:
        if self.cache is None:
            return None
        return build_cache_key(pdf_path, repr(self.schema), _llm_id(self.llm))

    def _cache_get(self, key: str | None) -> ExtractionResult | None:
        if self.cache is None or key is None:
            return None
        return self.cache.get(key)

    def _cache_set(self, key: str | None, value: ExtractionResult) -> None:
        if self.cache is None or key is None:
            return
        self.cache.set(key, value)


# ---------------------------------------------------------------- helpers


def _llm_id(llm: LLMProvider) -> str:
    """Stable string identifier for the LLM, used in the cache key."""
    model = getattr(llm, "model", None)
    models = getattr(llm, "models", None)
    if model:
        return f"{type(llm).__name__}:{model}"
    if models:
        return f"{type(llm).__name__}:{'|'.join(models)}"
    return type(llm).__name__


def _parse_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from an LLM response.

    Strips markdown fences if present; falls back to locating the first
    balanced object.
    """
    candidate = text.strip()
    fence = JSON_FENCE_RE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        # Try to slice the first {...} block.
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            data = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return {}
    if not isinstance(data, dict):
        return {}
    return data


def _collect_issues(
    bound: list[BoundValue],
    *,
    policy: HallucinationPolicy,
    low_conf_threshold: float,
) -> list[ProvenanceIssue]:
    issues: list[ProvenanceIssue] = []
    threshold = low_conf_threshold if low_conf_threshold > 0 else 0.7
    issues.extend(detect_hallucinations(bound, require_score=threshold))
    issues.extend(detect_role_mismatches(bound))
    if policy == "drop":
        issues = [iss for iss in issues if iss.issue_type != "hallucination"]
    return issues


def _drop_hallucinations(bound: list[BoundValue]) -> list[BoundValue]:
    return [bv for bv in bound if bv.match_method != "not_found"]


def _aggregate_cost(calls: list[LLMResponse]) -> CostReport:
    if not calls:
        return CostReport(tokens_in=0, tokens_out=0, usd=0.0, model_used="", breakdown=())
    tokens_in = sum(c.tokens_in for c in calls)
    tokens_out = sum(c.tokens_out for c in calls)
    usd = sum(c.usd for c in calls)
    breakdown = tuple((c.model_used, c.usd) for c in calls)
    return CostReport(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        usd=round(usd, 8),
        model_used=calls[-1].model_used,
        breakdown=breakdown,
    )


def _with_cache_hit(result: ExtractionResult) -> ExtractionResult:
    """Return a copy of `result` with `cache_hit=True`."""
    from dataclasses import replace

    return replace(result, cache_hit=True)


__all__ = ["Pipeline"]
