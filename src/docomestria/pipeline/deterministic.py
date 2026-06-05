"""Deterministic field pairing — no LLM, label-based extraction.

For each schema field, locate a label item (e.g. ``"NIF:"``) in the fused
items and pair it with the value to its right (or directly below). Checkbox
transformers receive special handling: each declared option label is matched
to the closest filled `VisualRect` in the same enclosing box.

This module is invoked from `_stream.stream_deterministic` when
``Pipeline(llm=None)``. It is intentionally side-effect free: callers receive
a tuple of `BoundValue`s plus the `ProvenanceIssue`s raised by missing
required fields.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, Any

from ..llm.models import BoundValue, ProvenanceIssue
from ..models import BBox, FusedItem
from ..transform.models import Field, infer_labels_from_key

if TYPE_CHECKING:  # pragma: no cover
    from ..result import FusionResult
    from ..transform.schema import Schema


# Two items are considered to be on the same row when their vertical centres
# differ by less than this many points (matches the pairing module's tolerance
# but slightly looser to accommodate noisy OCR).
ROW_TOLERANCE_PT = 8.0


def extract_deterministic(
    fusion: "FusionResult",
    schema: "Schema",
) -> tuple[list[BoundValue], list[ProvenanceIssue]]:
    """Pair every schema field with a value from `fusion.items` deterministically.

    Returns ``(bound_values, issues)``. Required fields with no pairing emit
    a ``"missing_required"`` issue at ``severity="high"``.
    """
    items = list(fusion.items)
    bound: list[BoundValue] = []
    issues: list[ProvenanceIssue] = []

    for field_name, fld in schema.fields.items():
        result = _pair_field(field_name, fld, items, fusion)
        if result is None:
            if fld.required:
                issues.append(
                    ProvenanceIssue(
                        field_name=field_name,
                        value="",
                        issue_type="missing_required",
                        severity="high",
                        detail="No label match found for this field in the document.",
                    )
                )
            continue
        bound.append(result)

    return bound, issues


# --------------------------------------------------------------------------- internals


def _pair_field(
    field_name: str,
    fld: Field,
    items: list[FusedItem],
    fusion: "FusionResult",
) -> BoundValue | None:
    labels = fld.labels if fld.labels else infer_labels_from_key(field_name)
    if not labels:
        return None

    label_idx = _find_label_item(field_name, labels, items)
    if label_idx is None:
        return None

    transformer_name = _transformer_name(fld.transformer)
    if transformer_name.startswith("checkbox_choice") or transformer_name.startswith(
        "checkbox_binary"
    ):
        return _pair_checkbox(field_name, fld, label_idx, items, fusion)

    return _pair_text_value(field_name, label_idx, items)


def _transformer_name(transformer: Any) -> str:
    return str(getattr(transformer, "name", getattr(transformer, "__name__", "")))


def _find_label_item(
    field_name: str,
    labels: tuple[str, ...],
    items: list[FusedItem],
) -> int | None:
    """Find the index in `items` whose text best matches one of the labels.

    Preference rules:
      1. Items inside an enclosing box whose section_title mentions the
         field path segment (e.g. ``"datos_titular.nif"`` prefers items in a
         box titled with ``"datos titular"`` / ``"datos personales"`` words).
      2. Earlier matches in reading order win on ties.
    """
    norm_labels = [_normalize_label(lbl) for lbl in labels if lbl]
    if not norm_labels:
        return None

    section_hint = _normalize_label(field_name.replace(".", " ").replace("_", " "))
    section_tokens = {tok for tok in section_hint.split() if len(tok) >= 4}

    preferred: int | None = None
    fallback: int | None = None

    for idx, item in enumerate(items):
        if not item.text:
            continue
        text_norm = _normalize_label(item.text)
        if not _label_matches(text_norm, norm_labels):
            continue
        if preferred is None and _section_matches(item, section_tokens):
            preferred = idx
        if fallback is None:
            fallback = idx
        if preferred is not None:
            break

    return preferred if preferred is not None else fallback


def _label_matches(text_norm: str, norm_labels: list[str]) -> bool:
    stripped = text_norm.rstrip(":").strip()
    return any(stripped == lbl for lbl in norm_labels)


def _section_matches(item: FusedItem, section_tokens: set[str]) -> bool:
    if not section_tokens:
        return False
    section = (item.section_title or "").lower()
    if not section:
        return False
    section_norm = _normalize_label(section)
    return any(tok in section_norm for tok in section_tokens)


def _normalize_label(text: str) -> str:
    """Lowercase + strip accents + collapse whitespace + drop trailing colon."""
    stripped = (text or "").strip().rstrip(":：").strip()
    decomposed = unicodedata.normalize("NFKD", stripped)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = ascii_only.lower()
    return " ".join(lowered.split())


def _pair_text_value(
    field_name: str,
    label_idx: int,
    items: list[FusedItem],
) -> BoundValue | None:
    label_item = items[label_idx]
    same_box = [
        (i, it)
        for i, it in enumerate(items)
        if i != label_idx and it.enclosing_box_id == label_item.enclosing_box_id
    ]

    value = _value_to_the_right(label_item, same_box)
    if value is None:
        value = _value_below(label_item, same_box)
    if value is None:
        return None

    value_idx, value_item = value
    return BoundValue(
        field_name=field_name,
        value=value_item.text.strip(),
        source_items=(str(value_idx),),
        bbox=value_item.bbox,
        section_title=value_item.section_title,
        docling_label=value_item.docling_label,
        match_method="deterministic_pair",
        match_score=1.0,
        page=value_item.page,
    )


def _value_to_the_right(
    label_item: FusedItem,
    candidates: list[tuple[int, FusedItem]],
) -> tuple[int, FusedItem] | None:
    label_cy = label_item.bbox.centroid[1]
    label_right = label_item.bbox.right
    best: tuple[int, FusedItem] | None = None
    best_dx = float("inf")
    for idx, it in candidates:
        if it.page != label_item.page:
            continue
        cy = it.bbox.centroid[1]
        if abs(cy - label_cy) > ROW_TOLERANCE_PT:
            continue
        if it.bbox.left < label_right:
            continue
        if _looks_like_label(it.text):
            continue
        dx = it.bbox.left - label_right
        if dx < best_dx:
            best, best_dx = (idx, it), dx
    return best


def _value_below(
    label_item: FusedItem,
    candidates: list[tuple[int, FusedItem]],
) -> tuple[int, FusedItem] | None:
    label_cx = label_item.bbox.centroid[0]
    label_bottom = label_item.bbox.bottom
    best: tuple[int, FusedItem] | None = None
    best_dy = float("inf")
    for idx, it in candidates:
        if it.page != label_item.page:
            continue
        if it.bbox.top < label_bottom:
            continue
        cx = it.bbox.centroid[0]
        if abs(cx - label_cx) > label_item.bbox.w + 12.0:
            continue
        if _looks_like_label(it.text):
            continue
        dy = it.bbox.top - label_bottom
        if dy < best_dy:
            best, best_dy = (idx, it), dy
    return best


def _looks_like_label(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and (t.endswith(":") or t.endswith("："))


# --------------------------------------------------------------------------- checkboxes


def _pair_checkbox(
    field_name: str,
    fld: Field,
    label_idx: int,
    items: list[FusedItem],
    fusion: "FusionResult",
) -> BoundValue | None:
    """Pair a checkbox field to its selected option label.

    Strategy: enumerate the transformer's declared options, find each option's
    label item within the same enclosing box, then for each option locate the
    nearest checkbox `VisualRect` and pick the one that is filled.
    """
    options = _transformer_options(fld.transformer)
    if not options:
        return None

    label_item = items[label_idx]
    same_box_idx = [
        i
        for i, it in enumerate(items)
        if it.enclosing_box_id == label_item.enclosing_box_id and i != label_idx
    ]

    rects = [
        r
        for r in getattr(fusion, "visual_rects", ())
        if _is_checkbox(r) and r.page == label_item.page
    ]

    selected: tuple[int, FusedItem] | None = None
    for opt in options:
        opt_idx = _find_option_label(opt, items, same_box_idx)
        if opt_idx is None:
            continue
        opt_item = items[opt_idx]
        rect = _closest_filled_rect(opt_item.bbox, rects)
        if rect is not None and getattr(rect, "is_filled", False):
            selected = (opt_idx, opt_item)
            break

    if selected is None:
        return None

    sel_idx, sel_item = selected
    return BoundValue(
        field_name=field_name,
        value=sel_item.text.strip(),
        source_items=(str(sel_idx),),
        bbox=sel_item.bbox,
        section_title=sel_item.section_title,
        docling_label=sel_item.docling_label,
        match_method="deterministic_pair",
        match_score=1.0,
        page=sel_item.page,
    )


def _transformer_options(transformer: Any) -> list[str]:
    name = _transformer_name(transformer)
    # Naming convention from forms.py:
    #   checkbox_choice(['propia','alquiler',...])
    #   checkbox_binary('V','H')
    if "(" not in name or ")" not in name:
        return []
    inner = name[name.index("(") + 1 : name.rindex(")")]
    try:
        # The repr is a Python literal list / tuple of strings — safe to eval
        # via ast.literal_eval to avoid the security pitfalls of eval().
        import ast

        parsed = ast.literal_eval(inner)
    except (SyntaxError, ValueError):
        return []
    if isinstance(parsed, tuple):
        return [str(p) for p in parsed]
    if isinstance(parsed, list):
        return [str(p) for p in parsed]
    if isinstance(parsed, str):
        return [parsed]
    return []


def _find_option_label(
    option: str,
    items: list[FusedItem],
    candidate_idx: list[int],
) -> int | None:
    target = _normalize_label(option)
    if not target:
        return None
    for idx in candidate_idx:
        if _normalize_label(items[idx].text) == target:
            return idx
    return None


def _closest_filled_rect(bbox: BBox, rects: list[Any]) -> Any | None:
    if not rects:
        return None
    lcx, lcy = bbox.centroid

    def _distance(rect: Any) -> float:
        rcx, rcy = rect.bbox.centroid
        return ((rcx - lcx) ** 2 + (rcy - lcy) ** 2) ** 0.5

    return min(rects, key=_distance)


def _is_checkbox(rect: Any) -> bool:
    rtype = getattr(rect, "rect_type", "box")
    if rtype == "checkbox":
        return True
    return bool(getattr(rect, "is_checkbox", False))


__all__ = ["extract_deterministic"]
