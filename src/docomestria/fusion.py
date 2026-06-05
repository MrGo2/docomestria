"""Three-way fusion of LiteParse, Docling and pdfplumber per page.

v0.3.0 breaking change: `fuse()` now returns a `FusionResult` from
`docomestria.result` carrying the items plus every engine input. The legacy
list-of-items can be obtained via `fuse(pdf).items`.

`fuse_from_engines()` keeps a stats-bearing return type for advanced users.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import BBox, DoclingBlock, FusedItem, LiteItem, VisualRect
from .result import FusionResult


@dataclass(frozen=True)
class FusionStats:
    """Stats returned by `fuse_from_engines` for callers that want them.

    For backward compatibility we keep an `items` attribute mirroring
    `FusionResult.items`.
    """

    items: tuple[FusedItem, ...]
    coverage: float
    matched_to_docling: int
    matched_to_box: int
    total_items: int


# --- block / box selection -------------------------------------------------


def _best_docling_block(
    item: LiteItem, blocks: list[DoclingBlock]
) -> tuple[DoclingBlock | None, str, float]:
    if not blocks:
        return None, "none", 0.0
    cx, cy = item.bbox.centroid
    for blk in blocks:
        if blk.bbox.contains_point(cx, cy):
            return blk, "centroid", 1.0
    best: DoclingBlock | None = None
    best_score = 0.0
    for blk in blocks:
        score = item.bbox.iou(blk.bbox)
        if score > best_score:
            best, best_score = blk, score
    if best is None or best_score <= 0.0:
        return None, "none", 0.0
    return best, "iou", best_score


def _smallest_containing_rect(item: LiteItem, rects: list[VisualRect]) -> VisualRect | None:
    cx, cy = item.bbox.centroid
    for rect in rects:
        if rect.bbox.contains_point(cx, cy):
            return rect
    return None


# --- table cell resolution ------------------------------------------------


def _find_cell(item: LiteItem, tables: list[VisualRect]) -> tuple[str, int, int, BBox] | None:
    """Return (table_id, row, col, cell_bbox) for the cell containing `item`."""
    cx, cy = item.bbox.centroid
    for table in tables:
        if not table.bbox.contains_point(cx, cy):
            continue
        if table.table_grid is None:
            continue
        for r_idx, row in enumerate(table.table_grid):
            for c_idx, cell in enumerate(row):
                if cell.contains_point(cx, cy):
                    return table.rect_id, r_idx, c_idx, cell
    return None


# --- section-title inference ----------------------------------------------


def _infer_section_titles(
    items_by_box: dict[str, list[LiteItem]],
) -> dict[str, str]:
    titles: dict[str, str] = {}
    for box_id, group in items_by_box.items():
        if not group:
            continue

        def _score(it: LiteItem) -> tuple[float, float]:
            size = it.font_size or 0.0
            return (size, -it.bbox.top)

        best = max(group, key=_score)
        text = (best.text or "").strip()
        if text:
            titles[box_id] = text
    return titles


# --- public API -----------------------------------------------------------


def fuse_from_engines(
    lite_items: list[LiteItem],
    docling_blocks: list[DoclingBlock],
    visual_rects: list[VisualRect],
) -> FusionStats:
    """Combine pre-extracted outputs from the three engines into FusionStats."""
    blocks_by_page: dict[int, list[DoclingBlock]] = defaultdict(list)
    for blk in docling_blocks:
        blocks_by_page[blk.page].append(blk)
    for blocks in blocks_by_page.values():
        blocks.sort(key=lambda b: b.bbox.area)

    rects_by_page: dict[int, list[VisualRect]] = defaultdict(list)
    tables_by_page: dict[int, list[VisualRect]] = defaultdict(list)
    for r in visual_rects:
        if r.bbox.area <= 0:
            continue
        rects_by_page[r.page].append(r)
        if r.rect_type == "table":
            tables_by_page[r.page].append(r)
    for rects in rects_by_page.values():
        rects.sort(key=lambda r: r.bbox.area)
    for tables in tables_by_page.values():
        tables.sort(key=lambda r: r.bbox.area)

    enriched: list[
        tuple[
            LiteItem,
            DoclingBlock | None,
            str,
            float,
            VisualRect | None,
            tuple[str, int, int, BBox] | None,
        ]
    ] = []
    items_per_box: dict[str, list[LiteItem]] = defaultdict(list)
    matched_docling = 0
    matched_box = 0

    for item in lite_items:
        blocks = blocks_by_page.get(item.page, [])
        block, method, score = _best_docling_block(item, blocks)
        if block is not None:
            matched_docling += 1

        # Non-checkbox, non-table rects for enclosing-box detection (tables
        # become enclosing boxes via `enclosing_box_id` too, but tables get
        # special cell handling).
        candidate_rects = [
            r for r in rects_by_page.get(item.page, []) if r.rect_type not in ("checkbox",)
        ]
        rect = _smallest_containing_rect(item, candidate_rects)
        if rect is not None:
            matched_box += 1
            items_per_box[rect.rect_id].append(item)

        cell = _find_cell(item, tables_by_page.get(item.page, []))
        enriched.append((item, block, method, score, rect, cell))

    titles = _infer_section_titles(items_per_box)

    out: list[FusedItem] = []
    for item, block, method, score, rect, cell in enriched:
        box_id = rect.rect_id if rect is not None else None
        section_title: str | None = None
        if box_id is not None:
            title = titles.get(box_id)
            if title and title != (item.text or "").strip():
                section_title = title
        table_id = cell[0] if cell else None
        table_row = cell[1] if cell else None
        table_col = cell[2] if cell else None
        cell_bbox = cell[3] if cell else None
        out.append(
            FusedItem(
                text=item.text,
                bbox=item.bbox,
                font_name=item.font_name,
                font_size=item.font_size,
                docling_label=block.label if block else None,
                docling_heading_level=block.heading_level if block else None,
                enclosing_box_id=box_id,
                section_title=section_title,
                page=item.page,
                match_method=method,
                match_score=round(score, 4),
                table_id=table_id,
                table_row=table_row,
                table_col=table_col,
                cell_bbox=cell_bbox,
            )
        )

    total = len(lite_items)
    coverage = matched_docling / total if total else 0.0
    return FusionStats(
        items=tuple(out),
        coverage=round(coverage, 4),
        matched_to_docling=matched_docling,
        matched_to_box=matched_box,
        total_items=total,
    )


def fuse(pdf_path: str | Path) -> FusionResult:
    """Run all three engines on `pdf_path` and return a FusionResult.

    Breaking change in v0.3.0 — previously returned `list[FusedItem]`. Use
    `fuse(pdf).items` to recover the old shape.
    """
    from .engines import extract_docling_blocks, extract_lite_items, extract_visual_rects

    lite = extract_lite_items(pdf_path)
    docling = extract_docling_blocks(pdf_path)
    rects = extract_visual_rects(pdf_path)
    stats = fuse_from_engines(lite, docling, rects)
    return FusionResult(
        items=stats.items,
        lite_items=tuple(lite),
        docling_blocks=tuple(docling),
        visual_rects=tuple(rects),
        coverage=stats.coverage,
        matched_to_docling=stats.matched_to_docling,
        matched_to_box=stats.matched_to_box,
        total_items=stats.total_items,
    )


__all__ = ["FusionStats", "fuse", "fuse_from_engines"]
_ = (BBox, LiteItem, DoclingBlock, VisualRect)
