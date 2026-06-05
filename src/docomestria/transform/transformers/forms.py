"""Form transformers — read VisualRect.is_filled via FusionResult."""

from __future__ import annotations

from typing import Any

from ..models import TransformContext


def _filled_rects_in_bbox(context: TransformContext | None) -> list[Any]:
    """Return VisualRect objects (checkbox-like) overlapping the bound bbox."""
    if context is None or context.bound_value is None or context.fusion_result is None:
        return []
    bv = context.bound_value
    fr = context.fusion_result
    if bv.bbox is None:
        return []
    rects: list[Any] = []
    for rect in getattr(fr, "visual_rects", ()):
        if rect.page != bv.page:
            continue
        rtype = getattr(rect, "rect_type", "box")
        # Backward-compat — older VisualRects use is_checkbox.
        if rtype != "checkbox" and not getattr(rect, "is_checkbox", False):
            continue
        # Overlap test — keep the rect if its centroid lies inside bv.bbox,
        # else if bv.bbox centroid lies inside the rect.
        rcx, rcy = rect.bbox.centroid
        if bv.bbox.contains_point(rcx, rcy):
            rects.append(rect)
            continue
        vcx, vcy = bv.bbox.centroid
        if rect.bbox.contains_point(vcx, vcy):
            rects.append(rect)
    return rects


def checkbox_choice(choices: list[str]) -> Any:
    """Return the choice whose label matches the raw text (case-insensitive).

    When fusion_result is available, also checks which rect is filled and
    boosts confidence when the label matches a filled checkbox nearby.
    """
    norm_choices = {c.lower(): c for c in choices}

    def _tr(
        raw: str, *, context: TransformContext | None = None
    ) -> tuple[Any, float, tuple[str, ...]]:
        text = (raw or "").strip()
        if not text:
            return None, 0.0, ("empty",)
        key = text.lower()
        if key not in norm_choices:
            return None, 0.0, ("not_in_choices",)
        picked = norm_choices[key]
        rects = _filled_rects_in_bbox(context)
        if rects:
            any_filled = any(getattr(r, "is_filled", False) for r in rects)
            if any_filled:
                return picked, 1.0, ()
            return picked, 0.7, ("no_filled_checkbox_nearby",)
        return picked, 0.9, ()

    _tr.name = f"checkbox_choice({choices!r})"  # type: ignore[attr-defined]
    return _tr


def checkbox_binary(true_label: str, false_label: str) -> Any:
    """Map one of two labels to True / False."""

    def _tr(
        raw: str, *, context: TransformContext | None = None
    ) -> tuple[Any, float, tuple[str, ...]]:
        text = (raw or "").strip()
        if not text:
            return None, 0.0, ("empty",)
        if text.lower() == true_label.lower():
            return True, 1.0, ()
        if text.lower() == false_label.lower():
            return False, 1.0, ()
        return None, 0.0, ("not_binary_label",)

    _tr.name = f"checkbox_binary({true_label!r},{false_label!r})"  # type: ignore[attr-defined]
    return _tr


def multi_checkbox(choices: list[str], sep: str = ",") -> Any:
    """Parse a comma-separated list of selected checkbox labels."""
    norm = {c.lower(): c for c in choices}

    def _tr(
        raw: str, *, context: TransformContext | None = None
    ) -> tuple[Any, float, tuple[str, ...]]:
        text = (raw or "").strip()
        if not text:
            return [], 0.0, ("empty",)
        parts = [p.strip() for p in text.split(sep) if p.strip()]
        selected: list[str] = []
        unknown: list[str] = []
        for p in parts:
            key = p.lower()
            if key in norm:
                selected.append(norm[key])
            else:
                unknown.append(p)
        issues = ("unknown_choice",) if unknown else ()
        conf = 1.0 if not unknown else 0.6
        return selected, conf, issues

    _tr.name = f"multi_checkbox({choices!r})"  # type: ignore[attr-defined]
    return _tr
