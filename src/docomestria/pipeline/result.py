"""`ExtractionResult` — top-level output of `Pipeline.run()`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..llm.models import BoundValue, ProvenanceIssue
    from ..result import FusionResult, ProvenanceTrace
    from ..transform.models import TypedValue


@dataclass(frozen=True)
class CostReport:
    """Aggregated cost across all LLM calls made during a single `run()`."""

    tokens_in: int
    tokens_out: int
    usd: float
    model_used: str
    breakdown: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class ExtractionResult:
    """Pipeline output bundling fusion + LLM binding + typed fields + cost."""

    typed_fields: dict[str, "TypedValue"]
    issues: tuple["ProvenanceIssue", ...]
    fusion: "FusionResult"
    bound: tuple["BoundValue", ...]
    cost: CostReport
    duration_ms: int
    cache_hit: bool
    llm_calls: int

    def trace(self, field_key: str) -> "ProvenanceTrace":
        """Convenience: get the full provenance trace for one typed field."""
        from ..result import build_trace

        tv = self.typed_fields[field_key]
        return build_trace(tv, self.fusion)


__all__ = ["CostReport", "ExtractionResult"]
