"""Reconstruct the document from Docling structure + LiteParse formatting.

Given a `FusionResult`, walk Docling blocks in reading order and attach the
LiteParse text items that fall inside each block. Non-table blocks become a
list of formatted spans (text + font + bold/italic flags). Table blocks
group their spans into the cells of `block.cells_grid` (or fall back to
spatial grouping by `table_grid` if available on a matching VisualRect).

The output is a JSON-safe dict consumed by docomestria-studio to render a
"reconstructed document" view that demonstrates the value of the fusion:
Docling supplies the semantic structure, LiteParse supplies the character
formatting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ..models import BBox, DoclingBlock, LiteItem
    from ..result import FusionResult


_BOLD_TOKENS = ("bold", "black", "heavy", "extrabold", "semibold")
_ITALIC_TOKENS = ("italic", "oblique")


def is_bold(font_name: str | None) -> bool:
    """Heuristic: font name contains a known bold-weight token."""
    if not font_name:
        return False
    fn = font_name.lower()
    return any(token in fn for token in _BOLD_TOKENS)


def is_italic(font_name: str | None) -> bool:
    """Heuristic: font name contains an italic/oblique token."""
    if not font_name:
        return False
    fn = font_name.lower()
    return any(token in fn for token in _ITALIC_TOKENS)


def _bbox_quad(bbox: Any) -> list[float]:
    return [float(bbox.x), float(bbox.y), float(bbox.w), float(bbox.h)]


def _span_from_lite(item: Any) -> dict[str, Any]:
    font_name = getattr(item, "font_name", None)
    return {
        "text": getattr(item, "text", "") or "",
        "font_name": font_name,
        "font_size": getattr(item, "font_size", None),
        "is_bold": is_bold(font_name),
        "is_italic": is_italic(font_name),
        "bbox": _bbox_quad(item.bbox),
    }


def _items_in_bbox(
    bbox: "BBox", page: int, lite_items: list["LiteItem"]
) -> list["LiteItem"]:
    inside: list[LiteItem] = []
    for li in lite_items:
        if int(getattr(li, "page", 1) or 1) != page:
            continue
        libbox = getattr(li, "bbox", None)
        if libbox is None:
            continue
        cx, cy = libbox.centroid
        if bbox.contains_point(cx, cy):
            inside.append(li)
    return inside


def _sort_reading_order(items: list["LiteItem"]) -> list["LiteItem"]:
    """Top-to-bottom, then left-to-right."""
    return sorted(items, key=lambda it: (it.bbox.y, it.bbox.x))


def _cell_index(
    cx: float,
    cy: float,
    cells_grid: Any,
) -> tuple[int, int] | None:
    """Find (row, col) of the cell whose bbox contains the point (cx, cy)."""
    if not cells_grid:
        return None
    for r, row in enumerate(cells_grid):
        for c, cell_bbox in enumerate(row):
            if cell_bbox is None:
                continue
            if cell_bbox.contains_point(cx, cy):
                return (r, c)
    return None


def _table_cells_payload(
    block: "DoclingBlock",
    lite_in_block: list["LiteItem"],
    fusion: "FusionResult",
) -> list[list[list[dict[str, Any]]]]:
    """Build a rows x cols matrix of cell-span lists.

    Strategy: find a matching `VisualRect` (rect_type=table) overlapping the
    block on the same page and use its `table_grid` (per-cell bboxes) for
    spatial assignment. If no grid is available, fall back to placing all
    spans in the (0, 0) cell so the UI still shows the content.
    """
    grid = _find_table_grid(block, fusion)
    if not grid:
        # Fallback: single-cell table with all spans, preserves data.
        spans = [_span_from_lite(li) for li in _sort_reading_order(lite_in_block)]
        rows_cells = getattr(block, "cells", None)
        if rows_cells:
            rows = len(rows_cells)
            cols = max((len(row) for row in rows_cells), default=1)
            out: list[list[list[dict[str, Any]]]] = [
                [[] for _ in range(cols)] for _ in range(rows)
            ]
            out[0][0] = spans
            return out
        return [[spans]]

    rows = len(grid)
    cols = max((len(row) for row in grid), default=0)
    matrix: list[list[list[dict[str, Any]]]] = [
        [[] for _ in range(cols)] for _ in range(rows)
    ]
    for li in _sort_reading_order(lite_in_block):
        cx, cy = li.bbox.centroid
        idx = _cell_index(cx, cy, grid)
        if idx is None:
            continue
        r, c = idx
        if r >= rows or c >= cols:
            continue
        matrix[r][c].append(_span_from_lite(li))
    return matrix


def _find_table_grid(block: "DoclingBlock", fusion: "FusionResult") -> Any:
    """Locate a pdfplumber VisualRect table whose bbox overlaps `block.bbox`."""
    best = None
    best_iou = 0.0
    for r in fusion.visual_rects:
        if r.page != block.page or r.rect_type != "table":
            continue
        if r.table_grid is None or not r.table_grid:
            continue
        iou = block.bbox.iou(r.bbox)
        if iou > best_iou:
            best_iou = iou
            best = r
    if best is None or best_iou < 0.3:
        return None
    return best.table_grid


def _sort_blocks(blocks: list["DoclingBlock"]) -> list["DoclingBlock"]:
    """Sort by page, then top-to-bottom, then left-to-right."""
    return sorted(
        blocks,
        key=lambda b: (int(b.page or 1), b.bbox.y, b.bbox.x),
    )


def build_merged_document(fusion: "FusionResult") -> dict[str, Any]:
    """Build the reconstructed-document payload from a FusionResult.

    See module docstring for the output shape.
    """
    lite_items = list(fusion.lite_items)
    blocks_sorted = _sort_blocks(list(fusion.docling_blocks))

    out_blocks: list[dict[str, Any]] = []
    pages: set[int] = set()
    for block in blocks_sorted:
        page = int(getattr(block, "page", 1) or 1)
        pages.add(page)
        label = getattr(block, "label", "") or ""
        entry: dict[str, Any] = {
            "label": label,
            "level": getattr(block, "heading_level", None),
            "layer": getattr(block, "content_layer", "body") or "body",
            "page": page,
            "bbox": _bbox_quad(block.bbox),
        }
        lite_in_block = _items_in_bbox(block.bbox, page, lite_items)
        if label == "table":
            entry["cells"] = _table_cells_payload(block, lite_in_block, fusion)
        else:
            spans_sorted = _sort_reading_order(lite_in_block)
            entry["spans"] = [_span_from_lite(li) for li in spans_sorted]
        out_blocks.append(entry)

    page_count = max(pages) if pages else 0
    return {"blocks": out_blocks, "page_count": page_count}


__all__ = [
    "build_merged_document",
    "is_bold",
    "is_italic",
]
