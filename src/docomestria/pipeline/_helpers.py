"""Internal helpers for `Pipeline` — extracted to keep `pipeline.py` focused.

This module is private (leading underscore) and re-exported only inside the
pipeline sub-package. Public symbols belong in `pipeline/__init__.py`.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal

from ..llm.models import BoundValue, ProvenanceIssue
from ..llm.validation import detect_hallucinations, detect_role_mismatches
from .providers.base import LLMProvider, LLMResponse
from .result import CostReport, ExtractionResult
from .step import TOTAL_STEPS, PipelineStep, explanation_for, title_for

if TYPE_CHECKING:  # pragma: no cover
    from ..result import FusionResult

HallucinationPolicy = Literal["flag", "drop", "retry_llm"]

JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


class StepEmitter:
    """Tracks step index + timings and builds `PipelineStep` instances.

    Kept as a small internal helper so `Pipeline.stream()` reads top-to-bottom
    without manually threading counters and timestamps through every yield.
    """

    def __init__(
        self,
        *,
        lang: str,
        callback: Callable[[PipelineStep], None] | None,
        total_steps: int = TOTAL_STEPS,
    ) -> None:
        self.lang = lang
        self.callback = callback
        self.total_steps = total_steps
        self._index = 0
        self._t0 = time.perf_counter()
        self._phase_start = self._t0

    def cumulative_ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)

    def emit(
        self,
        name: str,
        engine: str,
        *,
        bboxes: tuple = (),
        payload: dict[str, Any] | None = None,
        is_terminal: bool = False,
        is_error: bool = False,
        error_message: str | None = None,
        fusion: "FusionResult | None" = None,
        bound: tuple[BoundValue, ...] | None = None,
        issues: tuple[ProvenanceIssue, ...] | None = None,
        typed_fields: dict[str, Any] | None = None,
    ) -> PipelineStep:
        now = time.perf_counter()
        elapsed_ms = int((now - self._phase_start) * 1000)
        cumulative_ms = int((now - self._t0) * 1000)
        self._phase_start = now
        self._index += 1
        step = PipelineStep(
            name=name,
            title=title_for(name),
            explanation=explanation_for(name, self.lang),
            engine=engine,
            step_index=self._index,
            total_steps=self.total_steps,
            elapsed_ms=elapsed_ms,
            cumulative_ms=cumulative_ms,
            bboxes=tuple(bboxes),
            payload=payload or {},
            is_terminal=is_terminal,
            is_error=is_error,
            error_message=error_message,
            fusion=fusion,
            bound=bound,
            issues=issues,
            typed_fields=typed_fields,
        )
        if self.callback is not None:
            self.callback(step)
        return step


def llm_id(llm: LLMProvider) -> str:
    """Stable string identifier for the LLM, used in the cache key."""
    model = getattr(llm, "model", None)
    models = getattr(llm, "models", None)
    if model:
        return f"{type(llm).__name__}:{model}"
    if models:
        return f"{type(llm).__name__}:{'|'.join(models)}"
    return type(llm).__name__


def parse_json(text: str) -> dict[str, Any]:
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


def collect_issues(
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


def drop_hallucinations(bound: list[BoundValue]) -> list[BoundValue]:
    return [bv for bv in bound if bv.match_method != "not_found"]


def aggregate_cost(calls: list[LLMResponse]) -> CostReport:
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


def with_cache_hit(result: ExtractionResult) -> ExtractionResult:
    """Return a copy of `result` with `cache_hit=True`."""
    return replace(result, cache_hit=True)


__all__ = [
    "HallucinationPolicy",
    "StepEmitter",
    "aggregate_cost",
    "collect_issues",
    "drop_hallucinations",
    "llm_id",
    "parse_json",
    "with_cache_hit",
]
