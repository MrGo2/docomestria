"""`bind_provenance` — main entry point of the LLM provenance layer."""

from __future__ import annotations

from typing import Any

from ..models import BBox, FusedItem
from .matching import FusedItemIndex, MatchResult
from .models import BoundValue


def bind_provenance(
    llm_output: dict[str, Any],
    fused_items: list[FusedItem],
    *,
    fuzzy_threshold: float = 0.85,
) -> list[BoundValue]:
    """Bind each scalar value in `llm_output` to its source in `fused_items`.

    `llm_output` may be flat (`{"nif": "X"}`) or nested
    (`{"datos_titular": {"nif": "X"}}`). Nested dicts are walked recursively;
    the leaf key becomes `field_name`. Lists of scalars produce one
    `BoundValue` per element using the parent key (suffixed with the index).

    Non-string scalars are coerced to `str`. `None` values are skipped.
    """
    if not isinstance(llm_output, dict):
        raise TypeError("llm_output must be a dict")

    index = FusedItemIndex(fused_items)
    bound: list[BoundValue] = []
    for field, raw_value in _walk(llm_output):
        value = _coerce(raw_value)
        if value is None:
            continue
        result = index.find(value, fuzzy_threshold=fuzzy_threshold)
        bound.append(_build_bound(field, value, fused_items, result))
    return bound


# --- helpers --------------------------------------------------------------


def _walk(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Yield (field_name, value) pairs from arbitrarily nested dict/list/scalar."""
    out: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            field = f"{prefix}.{key}" if prefix else key
            out.extend(_walk(v, field))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            field = f"{prefix}[{i}]" if prefix else f"[{i}]"
            out.extend(_walk(v, field))
    else:
        out.append((prefix, obj))
    return out


def _coerce(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        # bools are surprising; serialize to "true"/"false"
        return "true" if value else "false"
    text = str(value).strip()
    return text or None


def _build_bound(
    field_name: str,
    value: str,
    items: list[FusedItem],
    result: MatchResult,
) -> BoundValue:
    if not result.source_indices:
        return BoundValue(
            field_name=field_name,
            value=value,
            source_items=(),
            bbox=None,
            section_title=None,
            docling_label=None,
            match_method=result.method,
            match_score=result.score,
            page=None,
        )

    sources = [items[i] for i in result.source_indices]
    union_bbox = _union_bbox(sources)
    pages = {it.page for it in sources}
    page = sources[0].page if len(pages) == 1 else sources[0].page
    section = _first_non_null(it.section_title for it in sources)
    label = _label_at_centroid(union_bbox, sources)

    return BoundValue(
        field_name=field_name,
        value=value,
        source_items=tuple(str(i) for i in result.source_indices),
        bbox=union_bbox,
        section_title=section,
        docling_label=label,
        match_method=result.method,
        match_score=result.score,
        page=page,
    )


def _union_bbox(items: list[FusedItem]) -> BBox:
    left = min(it.bbox.left for it in items)
    top = min(it.bbox.top for it in items)
    right = max(it.bbox.right for it in items)
    bottom = max(it.bbox.bottom for it in items)
    return BBox.from_ltrb(left, top, right, bottom)


def _first_non_null(values: Any) -> str | None:
    for v in values:
        if v:
            return v
    return None


def _label_at_centroid(bbox: BBox, items: list[FusedItem]) -> str | None:
    """Pick the docling label of the item whose centroid is closest to `bbox` centroid."""
    cx, cy = bbox.centroid
    best: FusedItem | None = None
    best_dist = float("inf")
    for it in items:
        ix, iy = it.bbox.centroid
        dist = (ix - cx) ** 2 + (iy - cy) ** 2
        if dist < best_dist:
            best = it
            best_dist = dist
    return best.docling_label if best is not None else None
