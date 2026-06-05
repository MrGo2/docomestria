"""Wrapper around pdfplumber for visual rectangles, tables, and checkboxes.

v0.3.0:
  - Detects tables via `page.find_tables()` and emits one VisualRect per
    table with `rect_type="table"` and a `table_grid` of cell bboxes.
  - Classifies each non-table rect as "checkbox" (square, small),
    "signature_field" (tall thin rect at bottom of page), or "box" (default).
"""

from __future__ import annotations

from pathlib import Path

from ..models import BBox, VisualRect

# Checkbox dimensions in PDF points.
CHECKBOX_MIN_SIDE = 5.0
CHECKBOX_MAX_SIDE = 22.0
CHECKBOX_ASPECT_TOL = 0.35

# Signature-field heuristic.
SIG_MIN_WIDTH = 80.0
SIG_MAX_HEIGHT = 25.0
SIG_BOTTOM_RATIO = 0.75  # rect must sit in the bottom 25% of the page


def _is_checkbox(w: float, h: float) -> bool:
    if w <= 0 or h <= 0:
        return False
    if not (CHECKBOX_MIN_SIDE <= w <= CHECKBOX_MAX_SIDE):
        return False
    if not (CHECKBOX_MIN_SIDE <= h <= CHECKBOX_MAX_SIDE):
        return False
    return abs(w - h) / max(w, h) <= CHECKBOX_ASPECT_TOL


def _is_signature(w: float, h: float, top: float, page_h: float) -> bool:
    if w < SIG_MIN_WIDTH or h > SIG_MAX_HEIGHT:
        return False
    if page_h <= 0:
        return False
    return top / page_h >= SIG_BOTTOM_RATIO


def _looks_filled(rect: dict) -> bool:
    fill = rect.get("non_stroking_color") or rect.get("fill")
    if fill is None or fill is False:
        return False
    return not (isinstance(fill, (list, tuple)) and len(fill) == 0)


def _checkbox_filled_by_overlap(cb_bbox: BBox, other_rects: list[dict]) -> bool:
    """Heuristic: a checkbox is filled if another small rect lies inside it."""
    for r in other_rects:
        ox = float(r["x0"])
        ot = float(r["top"])
        ox1 = float(r["x1"])
        ob = float(r["bottom"])
        if (
            ox >= cb_bbox.left
            and ot >= cb_bbox.top
            and ox1 <= cb_bbox.right
            and ob <= cb_bbox.bottom
            and (ox1 - ox) * (ob - ot) >= 0.25 * cb_bbox.area
        ):
            return True
    return False


def _table_cell_bbox(cell: tuple[float, float, float, float] | None) -> BBox | None:
    if cell is None:
        return None
    x0, top, x1, bottom = cell
    return BBox(x=float(x0), y=float(top), w=float(x1 - x0), h=float(bottom - top))


def _table_cells_from(table_obj: object) -> tuple[tuple[str, ...], ...] | None:
    """Extract a row x col matrix of cell text via the pdfplumber Table API.

    Returns None when the table has no extractable text. Cells that are missing
    are coerced to empty strings so the matrix stays rectangular.
    """
    try:
        extracted = table_obj.extract()  # type: ignore[attr-defined]
    except Exception:
        return None
    if not extracted:
        return None
    rows: list[tuple[str, ...]] = []
    for row in extracted:
        rows.append(tuple((cell or "") for cell in row))
    return tuple(rows) if rows else None


def _table_grid_from(table_obj: object) -> tuple[tuple[BBox, ...], ...]:
    """Build a row x col grid of BBoxes from a pdfplumber Table object."""
    rows = getattr(table_obj, "rows", None) or []
    grid: list[tuple[BBox, ...]] = []
    for row in rows:
        cells = getattr(row, "cells", None) or []
        bboxes = tuple(b for b in (_table_cell_bbox(c) for c in cells) if b is not None)
        if bboxes:
            grid.append(bboxes)
    return tuple(grid)


def extract_visual_rects(pdf_path: str | Path) -> list[VisualRect]:
    """Extract every vector rectangle plus detected tables from a PDF."""
    import pdfplumber  # type: ignore[import-not-found]

    rects: list[VisualRect] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            page_h = float(getattr(page, "height", 0.0))
            page_rects = list(page.rects or [])

            # 1. Tables — one VisualRect per detected table, plus a grid.
            tables_bboxes: list[tuple[float, float, float, float]] = []
            try:
                tables = page.find_tables() or []
            except Exception:
                tables = []
            for tidx, table in enumerate(tables):
                bbox = getattr(table, "bbox", None)
                if bbox is None:
                    continue
                x0, top, x1, bottom = bbox
                tbb = BBox(x=float(x0), y=float(top), w=float(x1 - x0), h=float(bottom - top))
                grid = _table_grid_from(table)
                cells = _table_cells_from(table)
                rid = f"p{page_idx}-t{tidx}"
                rects.append(
                    VisualRect(
                        bbox=tbb,
                        is_checkbox=False,
                        is_filled=False,
                        page=page_idx,
                        rect_id=rid,
                        rect_type="table",
                        table_grid=grid if grid else None,
                        cells=cells,
                    )
                )
                tables_bboxes.append((float(x0), float(top), float(x1), float(bottom)))

            # 2. Raw rects — classify each one.
            for ridx, r in enumerate(page_rects):
                x0 = float(r["x0"])
                top = float(r["top"])
                x1 = float(r["x1"])
                bottom = float(r["bottom"])
                w = x1 - x0
                h = bottom - top
                bbox = BBox(x=x0, y=top, w=w, h=h)

                if _is_checkbox(w, h):
                    rect_type = "checkbox"
                    is_cb = True
                elif _is_signature(w, h, top, page_h):
                    rect_type = "signature_field"
                    is_cb = False
                else:
                    rect_type = "box"
                    is_cb = False

                # Filled detection: explicit fill colour OR inner-rect overlap for checkboxes.
                filled = _looks_filled(r)
                if rect_type == "checkbox" and not filled:
                    filled = _checkbox_filled_by_overlap(bbox, page_rects)

                rects.append(
                    VisualRect(
                        bbox=bbox,
                        is_checkbox=is_cb,
                        is_filled=filled,
                        page=page_idx,
                        rect_id=f"p{page_idx}-r{ridx}",
                        rect_type=rect_type,
                        table_grid=None,
                    )
                )
    return rects
