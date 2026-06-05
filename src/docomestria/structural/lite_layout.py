"""LiteParse structural pyramid — Nivel 0..6.

Aggregates raw LiteItem words into a geometric hierarchy:

    Level 0  LiteItem   — word + bbox + font_name + font_size (INPUT)
    Level 1  Line       — items sharing the same Y (± y_tolerance_pt)
    Level 2  Run        — consecutive same-font/size items in a Line
    Level 3  Block      — consecutive Lines with similar left/right extent
    Level 4  Column     — vertical group of Blocks at similar X start
    Level 5  Region     — Blocks separated by a large vertical gap
    Level 6  PageLayout — all levels for one page (NamedTuple)

This module is **pure geometry** — no semantics, no scoring, no mutations.
All public types are frozen dataclasses. Only stdlib + numpy are used.

Entry point::

    from docomestria.structural.lite_layout import build_layout

    layout_by_page = build_layout(lite_items)   # dict[int, PageLayout]
    cols = layout_by_page[1].columns            # Column objects for page 1
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np

from ..models import BBox, LiteItem

# ---------------------------------------------------------------------------
# Helper — tight bbox around a sequence of bboxes
# ---------------------------------------------------------------------------


def _union_bbox(bboxes: Iterable[BBox]) -> BBox:
    """Return the smallest BBox containing all *bboxes*."""
    # Materialise — generators can only be iterated once.
    bl = list(bboxes)
    x = min(b.x for b in bl)
    y = min(b.y for b in bl)
    right = max(b.right for b in bl)
    bottom = max(b.bottom for b in bl)
    return BBox(x=x, y=y, w=right - x, h=bottom - y)


# ---------------------------------------------------------------------------
# Level 1 — Line
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """A horizontal run of LiteItems sharing approximately the same Y.

    ``bbox`` is the tight union of all item bboxes.
    ``items`` is ordered by ``item.bbox.x`` (left to right).
    """

    bbox: BBox
    items: tuple[LiteItem, ...]
    page: int

    @property
    def left(self) -> float:
        return self.bbox.x

    @property
    def right(self) -> float:
        return self.bbox.right

    @property
    def top(self) -> float:
        return self.bbox.y

    @property
    def bottom(self) -> float:
        return self.bbox.bottom

    @property
    def height(self) -> float:
        return self.bbox.h

    @property
    def text(self) -> str:
        return " ".join(it.text for it in self.items)


# ---------------------------------------------------------------------------
# Level 2 — Run
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Run:
    """Consecutive LiteItems in a Line that share the same font_name + font_size.

    ``font_name`` and ``font_size`` may be ``None`` when the engine could not
    determine them (embedded subsetted fonts).  In that case each word is its
    own Run (exact match on ``None`` pairs).
    """

    bbox: BBox
    items: tuple[LiteItem, ...]
    font_name: str | None
    font_size: float | None

    @property
    def text(self) -> str:
        return " ".join(it.text for it in self.items)


# ---------------------------------------------------------------------------
# Level 3 — Block
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Block:
    """Consecutive Lines that share a similar left/right X extent.

    ``bbox`` spans the union of all constituent line bboxes.
    ``lines`` is ordered top-to-bottom.
    """

    bbox: BBox
    lines: tuple[Line, ...]
    page: int

    @property
    def top(self) -> float:
        return self.bbox.y

    @property
    def bottom(self) -> float:
        return self.bbox.bottom

    @property
    def left(self) -> float:
        return self.bbox.x

    @property
    def right(self) -> float:
        return self.bbox.right

    @property
    def avg_line_height(self) -> float:
        if not self.lines:
            return 0.0
        return sum(ln.height for ln in self.lines) / len(self.lines)


# ---------------------------------------------------------------------------
# Level 4 — Column
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Column:
    """A vertical group of Blocks whose left edges cluster at a similar X.

    ``bbox`` is the tight union of all block bboxes.
    ``blocks`` is ordered top-to-bottom.
    """

    bbox: BBox
    blocks: tuple[Block, ...]
    page: int

    @property
    def x_start(self) -> float:
        """Median left-edge X of the constituent blocks."""
        if not self.blocks:
            return self.bbox.x
        lefts = sorted(b.left for b in self.blocks)
        mid = len(lefts) // 2
        return lefts[mid]


# ---------------------------------------------------------------------------
# Level 5 — Region
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Region:
    """A group of Blocks separated from neighbours by a large vertical gap.

    The gap threshold is ``line_height_multiplier × median_line_height``.
    ``bbox`` is the tight union of all block bboxes.
    ``blocks`` is ordered top-to-bottom.
    """

    bbox: BBox
    blocks: tuple[Block, ...]
    page: int


# ---------------------------------------------------------------------------
# Level 6 — PageLayout
# ---------------------------------------------------------------------------


class PageLayout(NamedTuple):
    """Full geometric pyramid for one page."""

    page: int
    lines: tuple[Line, ...]
    blocks: tuple[Block, ...]
    columns: tuple[Column, ...]
    regions: tuple[Region, ...]


# ---------------------------------------------------------------------------
# Aggregation functions
# ---------------------------------------------------------------------------


def items_to_lines(
    items: Iterable[LiteItem],
    y_tolerance_pt: float = 3.0,
) -> tuple[Line, ...]:
    """Group LiteItems into Lines by shared Y coordinate (± *y_tolerance_pt*).

    Items are first sorted by ``(page, y, x)``.  Items whose Y centroid differs
    by more than *y_tolerance_pt* from the running group's reference Y start a
    new Line.  The reference Y for a group is the Y of the **first** item added
    (i.e., the topmost item in PDF coordinates — smallest Y value after sort).

    Returns Lines sorted by ``(page, line.top, line.left)``.
    """
    sorted_items = sorted(items, key=lambda it: (it.page, it.bbox.y, it.bbox.x))

    groups: list[list[LiteItem]] = []
    current: list[LiteItem] = []
    ref_y: float | None = None
    ref_page: int | None = None

    for it in sorted_items:
        item_y = it.bbox.y
        if (
            ref_y is None
            or ref_page != it.page
            or abs(item_y - ref_y) > y_tolerance_pt
        ):
            if current:
                groups.append(current)
            current = [it]
            ref_y = item_y
            ref_page = it.page
        else:
            current.append(it)

    if current:
        groups.append(current)

    lines: list[Line] = []
    for grp in groups:
        # Sort left-to-right within the line
        grp_sorted = sorted(grp, key=lambda it: it.bbox.x)
        bbox = _union_bbox(it.bbox for it in grp_sorted)
        lines.append(Line(bbox=bbox, items=tuple(grp_sorted), page=grp_sorted[0].page))

    return tuple(lines)


def line_to_runs(line: Line) -> tuple[Run, ...]:
    """Split a Line into Runs of consecutive items with the same font/size.

    Matching is **exact** on ``(font_name, font_size)`` — ``None`` values are
    treated as a distinct key, so two ``None``-font items are consecutive only
    if they are adjacent.
    """
    if not line.items:
        return ()

    runs: list[Run] = []
    current: list[LiteItem] = [line.items[0]]
    ref_key = (line.items[0].font_name, line.items[0].font_size)

    for it in line.items[1:]:
        key = (it.font_name, it.font_size)
        if key == ref_key:
            current.append(it)
        else:
            bbox = _union_bbox(i.bbox for i in current)
            runs.append(Run(bbox=bbox, items=tuple(current), font_name=ref_key[0], font_size=ref_key[1]))
            current = [it]
            ref_key = key

    bbox = _union_bbox(i.bbox for i in current)
    runs.append(Run(bbox=bbox, items=tuple(current), font_name=ref_key[0], font_size=ref_key[1]))
    return tuple(runs)


def lines_to_blocks(
    lines: Iterable[Line],
    x_tolerance_pt: float = 5.0,
) -> tuple[Block, ...]:
    """Group consecutive Lines into Blocks when their X extents are similar.

    Two lines belong to the same block when *both* of the following hold:
    - ``abs(line.left - current_block_left) <= x_tolerance_pt``
    - ``abs(line.right - current_block_right) <= x_tolerance_pt``

    Lines must also belong to the same page.  The block reference left/right is
    the extent of the **first line** added to it.

    Returns Blocks in top-to-bottom order (matching input order, which must
    already be sorted by Y — ``items_to_lines`` guarantees this).
    """
    line_list = list(lines)
    if not line_list:
        return ()

    blocks: list[Block] = []
    current: list[Line] = [line_list[0]]
    ref_left = line_list[0].left
    ref_right = line_list[0].right
    ref_page = line_list[0].page

    for ln in line_list[1:]:
        same_page = ln.page == ref_page
        left_ok = abs(ln.left - ref_left) <= x_tolerance_pt
        right_ok = abs(ln.right - ref_right) <= x_tolerance_pt
        if same_page and left_ok and right_ok:
            current.append(ln)
        else:
            bbox = _union_bbox(l.bbox for l in current)
            blocks.append(Block(bbox=bbox, lines=tuple(current), page=ref_page))
            current = [ln]
            ref_left = ln.left
            ref_right = ln.right
            ref_page = ln.page

    bbox = _union_bbox(l.bbox for l in current)
    blocks.append(Block(bbox=bbox, lines=tuple(current), page=ref_page))
    return tuple(blocks)


def blocks_to_columns(
    blocks: Iterable[Block],
    min_gap_pt: float = 30.0,
) -> tuple[Column, ...]:
    """Cluster Blocks into Columns by their left-edge X coordinate.

    Uses a simple 1-D sort + gap-detection approach (no sklearn).  A new column
    starts whenever the gap between consecutive sorted left-edge values exceeds
    *min_gap_pt*.  Only blocks on the same page are clustered together.

    Blocks on different pages produce independent column sets (pages are never
    merged).  Returned Columns are ordered left-to-right within each page, then
    by page number.
    """
    block_list = list(blocks)
    if not block_list:
        return ()

    # Group by page first
    pages: dict[int, list[Block]] = {}
    for b in block_list:
        pages.setdefault(b.page, []).append(b)

    columns: list[Column] = []
    for page_num in sorted(pages):
        page_blocks = pages[page_num]
        # Sort by left-edge X to enable gap detection
        sorted_blocks = sorted(page_blocks, key=lambda b: b.left)
        lefts = np.array([b.left for b in sorted_blocks], dtype=float)

        # Find split points where gap > min_gap_pt
        gaps = np.diff(lefts)
        split_indices = np.where(gaps > min_gap_pt)[0] + 1  # +1: index of first block in new col

        # Build column groups
        group_starts = [0, *split_indices.tolist()]
        group_ends = [*split_indices.tolist(), len(sorted_blocks)]

        for start, end in zip(group_starts, group_ends):
            col_blocks = sorted_blocks[start:end]
            # Sort each column's blocks top-to-bottom
            col_blocks_sorted = sorted(col_blocks, key=lambda b: b.top)
            bbox = _union_bbox(b.bbox for b in col_blocks_sorted)
            columns.append(Column(bbox=bbox, blocks=tuple(col_blocks_sorted), page=page_num))

    return tuple(columns)


def blocks_to_regions(
    blocks: Iterable[Block],
    line_height_multiplier: float = 1.5,
) -> tuple[Region, ...]:
    """Group Blocks into Regions separated by large vertical gaps.

    A new Region starts when the vertical gap between the bottom of the last
    block and the top of the next block exceeds
    ``line_height_multiplier × median_line_height`` of the current region's
    blocks.

    ``median_line_height`` is the median avg_line_height across all blocks seen
    so far in the current region (updated incrementally).  Falls back to ``10.0``
    when no lines exist.

    Blocks on different pages always start a new Region.

    Returns Regions in top-to-bottom order per page.
    """
    block_list = sorted(blocks, key=lambda b: (b.page, b.top))
    if not block_list:
        return ()

    regions: list[Region] = []
    current: list[Block] = [block_list[0]]

    def _median_lh(bl: list[Block]) -> float:
        heights = [b.avg_line_height for b in bl if b.avg_line_height > 0]
        if not heights:
            return 10.0
        arr = np.array(heights, dtype=float)
        return float(np.median(arr))

    for blk in block_list[1:]:
        prev = current[-1]
        different_page = blk.page != prev.page
        gap = blk.top - prev.bottom
        threshold = line_height_multiplier * _median_lh(current)

        if different_page or gap > threshold:
            bbox = _union_bbox(b.bbox for b in current)
            regions.append(Region(bbox=bbox, blocks=tuple(current), page=current[0].page))
            current = [blk]
        else:
            current.append(blk)

    bbox = _union_bbox(b.bbox for b in current)
    regions.append(Region(bbox=bbox, blocks=tuple(current), page=current[0].page))
    return tuple(regions)


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------


def build_layout(items: Iterable[LiteItem]) -> dict[int, PageLayout]:
    """Build the full geometric pyramid from a flat sequence of LiteItems.

    Returns a dict keyed by 1-based page number.  Items from multiple pages
    are handled correctly — each pyramid level is computed per-page where that
    matters (Lines, Blocks, Columns, Regions never cross page boundaries).

    Usage::

        from docomestria.structural.lite_layout import build_layout

        layout = build_layout(lite_items)
        page1 = layout[1]
        print(len(page1.columns), "columns on page 1")
    """
    item_list = list(items)
    if not item_list:
        return {}

    # Level 1 — Lines (items_to_lines handles multi-page natively)
    all_lines = items_to_lines(item_list)

    # Level 3 — Blocks (lines_to_blocks handles multi-page natively)
    all_blocks = lines_to_blocks(all_lines)

    # Level 4 — Columns (per-page internally)
    all_columns = blocks_to_columns(all_blocks)

    # Level 5 — Regions (per-page internally)
    all_regions = blocks_to_regions(all_blocks)

    # Collect all page numbers
    pages_seen: set[int] = {it.page for it in item_list}

    def _filter_page(seq: tuple, pno: int) -> tuple:  # type: ignore[type-arg]
        return tuple(x for x in seq if x.page == pno)

    result: dict[int, PageLayout] = {}
    for pno in sorted(pages_seen):
        page_lines = _filter_page(all_lines, pno)
        page_blocks = _filter_page(all_blocks, pno)
        page_cols = _filter_page(all_columns, pno)
        page_regions = _filter_page(all_regions, pno)
        result[pno] = PageLayout(
            page=pno,
            lines=page_lines,
            blocks=page_blocks,
            columns=page_cols,
            regions=page_regions,
        )

    return result
