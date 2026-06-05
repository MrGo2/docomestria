"""Stream-phase implementations for `Pipeline._stream_internal`.

Extracted from `pipeline.py` to keep that module readable. Each function
here is a small generator focused on one phase (extraction, context, LLM,
binding, issue detection, typing). The Pipeline.run-as-stream invariant
lives entirely in `pipeline.py`; the helpers here only know how to emit
their slice of steps.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..llm.models import BoundValue
from ..llm.provenance import bind_provenance
from ..result import FusionResult
from ._helpers import (
    StepEmitter,
    aggregate_cost,
    collect_issues,
    drop_hallucinations,
    parse_json,
    with_cache_hit,
)
from .context import build_llm_context
from .prompts import SYSTEM_PROMPT, build_extraction_prompt
from .providers.base import LLMResponse
from .result import ExtractionResult
from .step import PipelineStep

if TYPE_CHECKING:  # pragma: no cover
    from .pipeline import Pipeline


def stream_cache_hit(
    emitter: StepEmitter,
    cached: ExtractionResult,
) -> Iterator[PipelineStep]:
    """Emit the short-circuit sequence for a cache hit."""
    yield emitter.emit(
        "cache_hit",
        "system",
        payload={"result": cached},
        fusion=cached.fusion,
        bound=cached.bound,
        issues=cached.issues,
        typed_fields=cached.typed_fields,
    )
    yield emitter.emit(
        "complete",
        "system",
        payload={"result": with_cache_hit(cached)},
        is_terminal=True,
        fusion=cached.fusion,
        bound=cached.bound,
        issues=cached.issues,
        typed_fields=cached.typed_fields,
    )


def stream_extract(
    pipe: "Pipeline",
    pdf_path: str | Path,
    emitter: StepEmitter,
) -> Iterator[PipelineStep]:
    """Yield extract-* steps + the final fuse step. Returns FusionResult."""
    if pipe._fuse_fn is not None or pipe.parallel_extract:
        fusion = pipe._fuse(pdf_path)
        yield emitter.emit(
            "extract_all",
            "system",
            bboxes=(
                tuple(li.bbox for li in fusion.lite_items)
                + tuple(b.bbox for b in fusion.docling_blocks)
                + tuple(r.bbox for r in fusion.visual_rects)
            ),
            payload={
                "liteparse_items": len(fusion.lite_items),
                "docling_blocks": len(fusion.docling_blocks),
                "visual_rects": len(fusion.visual_rects),
            },
            fusion=fusion,
        )
        yield emitter.emit("fuse", "fusion", payload=_fuse_payload(fusion), fusion=fusion)
        return fusion

    from ..engines import (  # lazy: avoid importing engines at module load
        extract_docling_blocks,
        extract_lite_items,
        extract_visual_rects,
    )
    from ..fusion import fuse_from_engines

    lite = extract_lite_items(pdf_path)
    yield emitter.emit(
        "extract_liteparse",
        "liteparse",
        bboxes=tuple(li.bbox for li in lite),
        payload={
            "items_count": len(lite),
            "sample_texts": [li.text for li in lite[:3] if li.text],
        },
    )

    docling = extract_docling_blocks(pdf_path)
    yield emitter.emit(
        "extract_docling",
        "docling",
        bboxes=tuple(b.bbox for b in docling),
        payload={
            "blocks_count": len(docling),
            "sample_labels": [b.label for b in docling[:3]],
        },
    )

    rects = extract_visual_rects(pdf_path)
    yield emitter.emit(
        "extract_pdfplumber",
        "pdfplumber",
        bboxes=tuple(r.bbox for r in rects),
        payload={
            "rects_count": len(rects),
            "sample_types": [r.rect_type for r in rects[:3]],
        },
    )

    stats = fuse_from_engines(lite, docling, rects)
    fusion = FusionResult(
        items=stats.items,
        lite_items=tuple(lite),
        docling_blocks=tuple(docling),
        visual_rects=tuple(rects),
        coverage=stats.coverage,
        matched_to_docling=stats.matched_to_docling,
        matched_to_box=stats.matched_to_box,
        total_items=stats.total_items,
    )
    yield emitter.emit("fuse", "fusion", payload=_fuse_payload(fusion), fusion=fusion)
    return fusion


def stream_llm(
    pipe: "Pipeline",
    emitter: StepEmitter,
    fusion: FusionResult,
) -> Iterator[PipelineStep]:
    """Build context, call the LLM, and parse the response.

    Returns `(parsed_json, llm_calls, context)`.
    """
    context = build_llm_context(fusion.items)
    sections = context.get("sections", [])
    section_titles = [s.get("title") for s in sections][:3] if isinstance(sections, list) else []
    yield emitter.emit(
        "build_context",
        "llm",
        payload={
            "sections_count": len(sections) if isinstance(sections, list) else 0,
            "sample_sections": section_titles,
        },
        fusion=fusion,
    )

    prompt = build_extraction_prompt(pipe.schema, context)
    response = pipe._call_llm(SYSTEM_PROMPT, prompt)
    llm_calls: list[LLMResponse] = [response]
    yield emitter.emit(
        "llm_call",
        "llm",
        payload={
            "model": response.model_used,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "usd": response.usd,
        },
        fusion=fusion,
    )

    parsed = parse_json(response.text)
    yield emitter.emit(
        "parse_response",
        "llm",
        payload={"fields_count": len(parsed), "field_names": list(parsed.keys())[:3]},
        fusion=fusion,
    )
    return parsed, llm_calls, context


def stream_bind_and_type(
    pipe: "Pipeline",
    emitter: StepEmitter,
    fusion: FusionResult,
    parsed: dict[str, Any],
    llm_calls: list[LLMResponse],
    context: dict[str, Any],
) -> Iterator[PipelineStep]:
    """Bind → detect issues → apply schema → emit complete."""
    bound = bind_provenance(parsed, list(fusion.items))
    bound, llm_calls = pipe._maybe_reprompt(bound, fusion, context, llm_calls)
    bound_tuple: tuple[BoundValue, ...] = tuple(bound)
    bind_bboxes = tuple(bv.bbox for bv in bound if bv.bbox is not None)
    yield emitter.emit(
        "bind_provenance",
        "provenance",
        bboxes=bind_bboxes,
        payload={
            "bound_count": len(bound),
            "llm_calls": len(llm_calls),
            "sample_fields": [bv.field_name for bv in bound[:3]],
        },
        fusion=fusion,
        bound=bound_tuple,
    )

    issues = collect_issues(
        bound,
        policy=pipe.on_hallucination,
        low_conf_threshold=pipe.on_low_confidence_field,
    )
    if pipe.on_hallucination == "drop":
        bound = drop_hallucinations(bound)
        bound_tuple = tuple(bound)
    issues_tuple = tuple(issues)
    yield emitter.emit(
        "detect_issues",
        "provenance",
        payload={
            "issues_count": len(issues),
            "issue_types": sorted({iss.issue_type for iss in issues}),
        },
        fusion=fusion,
        bound=bound_tuple,
        issues=issues_tuple,
    )

    typed = pipe.schema.apply(bound, fusion)
    yield emitter.emit(
        "apply_schema",
        "transform",
        payload={
            "typed_count": len(typed),
            "ok_count": sum(1 for tv in typed.values() if getattr(tv, "ok", False)),
        },
        fusion=fusion,
        bound=bound_tuple,
        issues=issues_tuple,
        typed_fields=typed,
    )

    cost = aggregate_cost(llm_calls)
    duration_ms = emitter.cumulative_ms()
    result = ExtractionResult(
        typed_fields=typed,
        issues=issues_tuple,
        fusion=fusion,
        bound=bound_tuple,
        cost=cost,
        duration_ms=duration_ms,
        cache_hit=False,
        llm_calls=len(llm_calls),
    )
    pipe._cache_set(pipe._last_cache_key, result)

    yield emitter.emit(
        "complete",
        "system",
        payload={"result": result, "duration_ms": duration_ms, "cost_usd": cost.usd},
        is_terminal=True,
        fusion=fusion,
        bound=bound_tuple,
        issues=issues_tuple,
        typed_fields=typed,
    )


def stream_deterministic(
    pipe: "Pipeline",
    emitter: StepEmitter,
    fusion: FusionResult,
) -> Iterator[PipelineStep]:
    """Run the LLM-free pairing path: pair_fields → apply_schema → complete."""
    from .deterministic import extract_deterministic
    from .result import CostReport

    bound, det_issues = extract_deterministic(fusion, pipe.schema)
    bound_tuple: tuple[BoundValue, ...] = tuple(bound)
    issues_tuple: tuple = tuple(det_issues)

    pair_bboxes = tuple(bv.bbox for bv in bound if bv.bbox is not None)
    yield emitter.emit(
        "pair_fields",
        "pairing",
        bboxes=pair_bboxes,
        payload={
            "paired_count": len(bound),
            "missing_required": sum(
                1 for iss in det_issues if iss.issue_type == "missing_required"
            ),
            "sample_fields": [bv.field_name for bv in bound[:3]],
        },
        fusion=fusion,
        bound=bound_tuple,
        issues=issues_tuple,
    )

    typed = pipe.schema.apply(bound, fusion)
    yield emitter.emit(
        "apply_schema",
        "transform",
        payload={
            "typed_count": len(typed),
            "ok_count": sum(1 for tv in typed.values() if getattr(tv, "ok", False)),
        },
        fusion=fusion,
        bound=bound_tuple,
        issues=issues_tuple,
        typed_fields=typed,
    )

    cost = CostReport(tokens_in=0, tokens_out=0, usd=0.0, model_used="deterministic")
    duration_ms = emitter.cumulative_ms()
    result = ExtractionResult(
        typed_fields=typed,
        issues=issues_tuple,
        fusion=fusion,
        bound=bound_tuple,
        cost=cost,
        duration_ms=duration_ms,
        cache_hit=False,
        llm_calls=0,
    )
    pipe._cache_set(pipe._last_cache_key, result)

    yield emitter.emit(
        "complete",
        "system",
        payload={"result": result, "duration_ms": duration_ms, "cost_usd": cost.usd},
        is_terminal=True,
        fusion=fusion,
        bound=bound_tuple,
        issues=issues_tuple,
        typed_fields=typed,
    )


def _fuse_payload(fusion: FusionResult) -> dict[str, Any]:
    return {
        "items_count": len(fusion.items),
        "coverage": fusion.coverage,
        "matched_to_docling": fusion.matched_to_docling,
        "matched_to_box": fusion.matched_to_box,
        "sample_texts": [it.text for it in fusion.items[:3] if it.text],
    }


__all__ = [
    "stream_bind_and_type",
    "stream_cache_hit",
    "stream_deterministic",
    "stream_extract",
    "stream_llm",
]
