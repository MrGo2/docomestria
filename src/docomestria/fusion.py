"""Three-way fusion of LiteParse, Docling and pdfplumber per page."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import BBox, DoclingBlock, FusedItem, LiteItem, VisualRect


@dataclass(frozen=True)
class FusionResult:
    """Bundle returned by `fuse_from_engines` when the caller wants stats too."""

    items: list[FusedItem]
    coverage: float  # fraction of LiteItems matched to a Docling block
    matched_to_docling: int
    matched_to_box: int
    total_items: int


# --- block / box selection -------------------------------------------------


def _best_docling_block(
    item: LiteItem, blocks: list[DoclingBlock]
) -> tuple[DoclingBlock | None, str, float]:
    """Smallest containing block by centroid; else best-IoU; else None."""
    if not blocks:
        return None, "none", 0.0
    cx, cy = item.bbox.centroid
    for blk in blocks:  # already sorted by ascending area
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
    for rect in rects:  # sorted by ascending area
        if rect.bbox.contains_point(cx, cy):
            return rect
    return None


# --- section-title inference ----------------------------------------------


def _infer_section_titles(
    items_by_box: dict[str, list[LiteItem]],
) -> dict[str, str]:
    """For each enclosing box, pick a likely title.

    Heuristic: prefer the topmost item with the largest font size. If no font
    size is known, just take the topmost item.
    """
    titles: dict[str, str] = {}
    for box_id, group in items_by_box.items():
        if not group:
            continue

        def _score(it: LiteItem) -> tuple[float, float]:
            # Larger font wins; for ties prefer the topmost (smallest y).
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
) -> FusionResult:
    """Combine pre-extracted outputs from the three engines.

    Useful when callers want to run engines themselves (e.g. with custom
    options) and only need the fusion logic.
    """
    blocks_by_page: dict[int, list[DoclingBlock]] = defaultdict(list)
    for blk in docling_blocks:
        blocks_by_page[blk.page].append(blk)
    for blocks in blocks_by_page.values():
        blocks.sort(key=lambda b: b.bbox.area)

    rects_by_page: dict[int, list[VisualRect]] = defaultdict(list)
    for r in visual_rects:
        # Tiny rectangles are usually borders or grid lines — keep checkbox-sized
        # ones but drop rectangles with zero area.
        if r.bbox.area > 0:
            rects_by_page[r.page].append(r)
    for rects in rects_by_page.values():
        # Skip checkbox-sized rectangles when searching for enclosing boxes —
        # they would always win as "smallest". Sort the rest ascending.
        rects.sort(key=lambda r: r.bbox.area)

    # First pass: match each LiteItem and remember its enclosing box.
    enriched: list[tuple[LiteItem, DoclingBlock | None, str, float, VisualRect | None]] = []
    items_per_box: dict[str, list[LiteItem]] = defaultdict(list)
    matched_docling = 0
    matched_box = 0

    for item in lite_items:
        blocks = blocks_by_page.get(item.page, [])
        block, method, score = _best_docling_block(item, blocks)
        if block is not None:
            matched_docling += 1

        # Exclude checkbox-shaped rectangles when looking for an enclosing box,
        # otherwise small overlays would always win.
        non_checkbox_rects = [r for r in rects_by_page.get(item.page, []) if not r.is_checkbox]
        rect = _smallest_containing_rect(item, non_checkbox_rects)
        if rect is not None:
            matched_box += 1
            items_per_box[rect.rect_id].append(item)

        enriched.append((item, block, method, score, rect))

    titles = _infer_section_titles(items_per_box)

    # Second pass: emit FusedItems with section_title resolved.
    out: list[FusedItem] = []
    for item, block, method, score, rect in enriched:
        box_id = rect.rect_id if rect is not None else None
        section_title: str | None = None
        if box_id is not None:
            title = titles.get(box_id)
            # Don't tag an item as the title of its own box.
            if title and title != (item.text or "").strip():
                section_title = title
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
            )
        )

    total = len(lite_items)
    coverage = matched_docling / total if total else 0.0
    return FusionResult(
        items=out,
        coverage=round(coverage, 4),
        matched_to_docling=matched_docling,
        matched_to_box=matched_box,
        total_items=total,
    )


def fuse(pdf_path: str | Path) -> list[FusedItem]:
    """Run all three engines on `pdf_path` and return the fused items."""
    from .engines import extract_docling_blocks, extract_lite_items, extract_visual_rects

    lite = extract_lite_items(pdf_path)
    docling = extract_docling_blocks(pdf_path)
    rects = extract_visual_rects(pdf_path)
    return fuse_from_engines(lite, docling, rects).items


# Convenience aliases for advanced users.
__all__ = ["FusionResult", "fuse", "fuse_from_engines"]
# Re-export the input types for type-checking convenience.
_ = (BBox, LiteItem, DoclingBlock, VisualRect)
