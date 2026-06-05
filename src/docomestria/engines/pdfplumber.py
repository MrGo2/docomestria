"""Wrapper around pdfplumber for visual rectangles and checkbox detection."""

from __future__ import annotations

from pathlib import Path

from ..models import BBox, VisualRect

# A rectangle is considered checkbox-like when both sides are within this range
# (in PDF points) and roughly square.
CHECKBOX_MIN_SIDE = 5.0
CHECKBOX_MAX_SIDE = 22.0
CHECKBOX_ASPECT_TOL = 0.35  # |w - h| / max(w, h)


def _is_checkbox(w: float, h: float) -> bool:
    if w <= 0 or h <= 0:
        return False
    if not (CHECKBOX_MIN_SIDE <= w <= CHECKBOX_MAX_SIDE):
        return False
    if not (CHECKBOX_MIN_SIDE <= h <= CHECKBOX_MAX_SIDE):
        return False
    return abs(w - h) / max(w, h) <= CHECKBOX_ASPECT_TOL


def _looks_filled(rect: dict) -> bool:
    """Best-effort: a rectangle with a non-stroke fill colour is treated as filled."""
    fill = rect.get("non_stroking_color") or rect.get("fill")
    if fill is None or fill is False:
        return False
    return not (isinstance(fill, (list, tuple)) and len(fill) == 0)


def extract_visual_rects(pdf_path: str | Path) -> list[VisualRect]:
    """Return all vector rectangles found by pdfplumber, top-left origin.

    pdfplumber already exposes top-left coordinates via the `top`/`bottom`
    attributes, so no flip is needed.
    """
    import pdfplumber  # type: ignore[import-not-found]

    rects: list[VisualRect] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            for ridx, r in enumerate(page.rects or []):
                x0 = float(r["x0"])
                top = float(r["top"])
                x1 = float(r["x1"])
                bottom = float(r["bottom"])
                w = x1 - x0
                h = bottom - top
                bbox = BBox(x=x0, y=top, w=w, h=h)
                rects.append(
                    VisualRect(
                        bbox=bbox,
                        is_checkbox=_is_checkbox(w, h),
                        is_filled=_looks_filled(r),
                        page=page_idx,
                        rect_id=f"p{page_idx}-r{ridx}",
                    )
                )
    return rects
