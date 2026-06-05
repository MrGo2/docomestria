"""Unit tests for the LiteParse structural pyramid — lite_layout.py.

Tests cover every aggregation function plus the high-level build_layout
entry point.  No PDF I/O — all fixtures are hand-built LiteItems.
"""

from __future__ import annotations

import pytest

from docomestria.models import BBox, LiteItem
from docomestria.structural.lite_layout import (
    Block,
    Column,
    Line,
    PageLayout,
    Region,
    Run,
    blocks_to_columns,
    blocks_to_regions,
    build_layout,
    items_to_lines,
    line_to_runs,
    lines_to_blocks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item(
    text: str,
    x: float,
    y: float,
    *,
    w: float = 60.0,
    h: float = 10.0,
    page: int = 1,
    font: str | None = "Helvetica",
    size: float | None = 10.0,
) -> LiteItem:
    return LiteItem(
        text=text,
        bbox=BBox(x=x, y=y, w=w, h=h),
        font_name=font,
        font_size=size,
        page=page,
    )


# ---------------------------------------------------------------------------
# items_to_lines
# ---------------------------------------------------------------------------


class TestItemsToLines:
    def test_three_items_same_y_produce_one_line(self):
        items = [
            _item("A", x=10, y=100),
            _item("B", x=80, y=100),
            _item("C", x=150, y=100),
        ]
        lines = items_to_lines(items)
        assert len(lines) == 1
        assert lines[0].text == "A B C"

    def test_three_items_different_y_produce_three_lines(self):
        items = [
            _item("A", x=10, y=100),
            _item("B", x=10, y=120),
            _item("C", x=10, y=140),
        ]
        lines = items_to_lines(items)
        assert len(lines) == 3

    def test_y_tolerance_groups_nearby_items(self):
        # Two items within 3 pt → same line
        items = [
            _item("A", x=10, y=100.0),
            _item("B", x=80, y=102.5),  # within default 3.0 pt tolerance
        ]
        lines = items_to_lines(items, y_tolerance_pt=3.0)
        assert len(lines) == 1

    def test_y_tolerance_splits_distant_items(self):
        # Items 4 pt apart → different lines
        items = [
            _item("A", x=10, y=100.0),
            _item("B", x=80, y=104.1),  # just beyond 3.0 pt tolerance
        ]
        lines = items_to_lines(items, y_tolerance_pt=3.0)
        assert len(lines) == 2

    def test_items_sorted_left_to_right_within_line(self):
        items = [
            _item("C", x=200, y=100),
            _item("A", x=10, y=100),
            _item("B", x=100, y=100),
        ]
        lines = items_to_lines(items)
        assert len(lines) == 1
        texts = [it.text for it in lines[0].items]
        assert texts == ["A", "B", "C"]

    def test_items_on_different_pages_split_into_separate_lines(self):
        items = [
            _item("A", x=10, y=100, page=1),
            _item("B", x=10, y=100, page=2),  # same Y but different page
        ]
        lines = items_to_lines(items)
        assert len(lines) == 2
        assert lines[0].page == 1
        assert lines[1].page == 2

    def test_empty_input_returns_empty_tuple(self):
        assert items_to_lines([]) == ()

    def test_line_bbox_spans_all_items(self):
        items = [
            _item("A", x=10, y=100, w=40, h=10),
            _item("B", x=80, y=100, w=60, h=12),
        ]
        lines = items_to_lines(items)
        bbox = lines[0].bbox
        assert bbox.x == pytest.approx(10.0)
        assert bbox.right == pytest.approx(140.0)


# ---------------------------------------------------------------------------
# line_to_runs
# ---------------------------------------------------------------------------


class TestLineToRuns:
    def test_two_items_same_font_produce_one_run(self):
        line = Line(
            bbox=BBox(x=0, y=0, w=200, h=10),
            items=(
                _item("Hello", x=0, y=0, font="Helvetica-Bold", size=10.0),
                _item("World", x=70, y=0, font="Helvetica-Bold", size=10.0),
            ),
            page=1,
        )
        runs = line_to_runs(line)
        assert len(runs) == 1
        assert runs[0].font_name == "Helvetica-Bold"
        assert runs[0].font_size == 10.0
        assert runs[0].text == "Hello World"

    def test_two_items_different_fonts_produce_two_runs(self):
        line = Line(
            bbox=BBox(x=0, y=0, w=200, h=10),
            items=(
                _item("Label", x=0, y=0, font="Helvetica-Bold", size=10.0),
                _item("Value", x=70, y=0, font="Helvetica", size=10.0),
            ),
            page=1,
        )
        runs = line_to_runs(line)
        assert len(runs) == 2
        assert runs[0].font_name == "Helvetica-Bold"
        assert runs[1].font_name == "Helvetica"

    def test_different_sizes_same_font_produce_two_runs(self):
        line = Line(
            bbox=BBox(x=0, y=0, w=200, h=10),
            items=(
                _item("Big", x=0, y=0, font="Helvetica", size=14.0),
                _item("Small", x=70, y=0, font="Helvetica", size=10.0),
            ),
            page=1,
        )
        runs = line_to_runs(line)
        assert len(runs) == 2

    def test_none_fonts_each_form_own_run(self):
        line = Line(
            bbox=BBox(x=0, y=0, w=200, h=10),
            items=(
                _item("A", x=0, y=0, font=None, size=None),
                _item("B", x=70, y=0, font=None, size=None),
            ),
            page=1,
        )
        # Both items have (None, None) → they DO match → 1 run
        runs = line_to_runs(line)
        assert len(runs) == 1

    def test_mixed_none_and_named_font(self):
        line = Line(
            bbox=BBox(x=0, y=0, w=200, h=10),
            items=(
                _item("A", x=0, y=0, font=None, size=None),
                _item("B", x=70, y=0, font="Helvetica", size=10.0),
            ),
            page=1,
        )
        runs = line_to_runs(line)
        assert len(runs) == 2

    def test_empty_line_returns_empty_tuple(self):
        line = Line(bbox=BBox(x=0, y=0, w=0, h=0), items=(), page=1)
        assert line_to_runs(line) == ()

    def test_run_bbox_is_tight_union(self):
        line = Line(
            bbox=BBox(x=0, y=0, w=200, h=10),
            items=(
                _item("A", x=10, y=0, w=40, h=10, font="Helvetica-Bold", size=10.0),
                _item("B", x=60, y=0, w=50, h=10, font="Helvetica-Bold", size=10.0),
            ),
            page=1,
        )
        runs = line_to_runs(line)
        assert runs[0].bbox.x == pytest.approx(10.0)
        assert runs[0].bbox.right == pytest.approx(110.0)


# ---------------------------------------------------------------------------
# lines_to_blocks
# ---------------------------------------------------------------------------


class TestLinesToBlocks:
    def _make_line(self, y: float, left: float, right: float, page: int = 1) -> Line:
        w = right - left
        return Line(
            bbox=BBox(x=left, y=y, w=w, h=10.0),
            items=(_item("x", x=left, y=y, w=w),),
            page=page,
        )

    def test_three_consecutive_lines_same_x_produce_one_block(self):
        lines = [
            self._make_line(y=100, left=50, right=300),
            self._make_line(y=115, left=50, right=300),
            self._make_line(y=130, left=50, right=300),
        ]
        blocks = lines_to_blocks(lines)
        assert len(blocks) == 1
        assert len(blocks[0].lines) == 3

    def test_gap_in_x_produces_two_blocks(self):
        lines = [
            self._make_line(y=100, left=50, right=300),
            self._make_line(y=115, left=50, right=300),
            # This line starts 50 pt to the right — outside x_tolerance_pt=5
            self._make_line(y=130, left=100, right=350),
            self._make_line(y=145, left=100, right=350),
        ]
        blocks = lines_to_blocks(lines, x_tolerance_pt=5.0)
        assert len(blocks) == 2

    def test_different_pages_always_split(self):
        lines = [
            self._make_line(y=100, left=50, right=300, page=1),
            self._make_line(y=115, left=50, right=300, page=2),
        ]
        blocks = lines_to_blocks(lines)
        assert len(blocks) == 2
        assert blocks[0].page == 1
        assert blocks[1].page == 2

    def test_empty_returns_empty_tuple(self):
        assert lines_to_blocks([]) == ()

    def test_block_bbox_spans_all_lines(self):
        lines = [
            self._make_line(y=100, left=50, right=300),
            self._make_line(y=115, left=50, right=300),
        ]
        blocks = lines_to_blocks(lines)
        assert blocks[0].bbox.y == pytest.approx(100.0)
        assert blocks[0].bbox.bottom == pytest.approx(125.0)  # y=115 + h=10


# ---------------------------------------------------------------------------
# blocks_to_columns
# ---------------------------------------------------------------------------


class TestBlocksToColumns:
    def _make_block(self, left: float, top: float, page: int = 1) -> Block:
        line = Line(
            bbox=BBox(x=left, y=top, w=150.0, h=10.0),
            items=(_item("x", x=left, y=top, w=150.0),),
            page=page,
        )
        return Block(bbox=BBox(x=left, y=top, w=150.0, h=10.0), lines=(line,), page=page)

    def test_four_blocks_two_columns_separated_50pt(self):
        # Column A at x=50, Column B at x=300 (gap = 250 > 30 pt default)
        blocks = [
            self._make_block(left=50, top=100),
            self._make_block(left=50, top=120),
            self._make_block(left=300, top=100),
            self._make_block(left=300, top=120),
        ]
        cols = blocks_to_columns(blocks, min_gap_pt=30.0)
        assert len(cols) == 2
        # First column is leftmost
        assert cols[0].x_start < cols[1].x_start

    def test_all_blocks_at_same_x_produce_one_column(self):
        blocks = [
            self._make_block(left=50, top=100),
            self._make_block(left=50, top=120),
            self._make_block(left=55, top=140),  # within 30 pt gap
        ]
        cols = blocks_to_columns(blocks, min_gap_pt=30.0)
        assert len(cols) == 1

    def test_different_pages_produce_independent_columns(self):
        blocks = [
            self._make_block(left=50, top=100, page=1),
            self._make_block(left=300, top=100, page=1),
            self._make_block(left=50, top=100, page=2),
        ]
        cols = blocks_to_columns(blocks, min_gap_pt=30.0)
        # Page 1 → 2 columns; page 2 → 1 column = 3 total
        assert len(cols) == 3

    def test_empty_returns_empty_tuple(self):
        assert blocks_to_columns([]) == ()

    def test_column_blocks_ordered_top_to_bottom(self):
        blocks = [
            self._make_block(left=50, top=200),
            self._make_block(left=50, top=100),
            self._make_block(left=50, top=150),
        ]
        cols = blocks_to_columns(blocks)
        assert len(cols) == 1
        tops = [b.top for b in cols[0].blocks]
        assert tops == sorted(tops)


# ---------------------------------------------------------------------------
# blocks_to_regions
# ---------------------------------------------------------------------------


class TestBlocksToRegions:
    def _make_block(
        self, top: float, height: float = 10.0, page: int = 1
    ) -> Block:
        line = Line(
            bbox=BBox(x=50, y=top, w=200.0, h=height),
            items=(_item("x", x=50, y=top, w=200.0, h=height),),
            page=page,
        )
        return Block(bbox=BBox(x=50, y=top, w=200.0, h=height), lines=(line,), page=page)

    def test_close_blocks_form_one_region(self):
        # line_height ≈ 10, threshold = 1.5 × 10 = 15; gap = 5 → same region
        blocks = [
            self._make_block(top=100, height=10),
            self._make_block(top=115, height=10),  # gap = 115 - 110 = 5
        ]
        regions = blocks_to_regions(blocks, line_height_multiplier=1.5)
        assert len(regions) == 1

    def test_large_gap_produces_two_regions(self):
        # line_height ≈ 10, threshold = 15; gap = 30 → new region
        blocks = [
            self._make_block(top=100, height=10),
            self._make_block(top=140, height=10),  # gap = 140 - 110 = 30 > 15
        ]
        regions = blocks_to_regions(blocks, line_height_multiplier=1.5)
        assert len(regions) == 2

    def test_different_pages_always_split(self):
        blocks = [
            self._make_block(top=100, page=1),
            self._make_block(top=115, page=2),
        ]
        regions = blocks_to_regions(blocks)
        assert len(regions) == 2

    def test_empty_returns_empty_tuple(self):
        assert blocks_to_regions([]) == ()

    def test_region_bbox_spans_all_blocks(self):
        blocks = [
            self._make_block(top=100, height=10),
            self._make_block(top=112, height=10),  # close enough → same region
        ]
        regions = blocks_to_regions(blocks, line_height_multiplier=1.5)
        assert regions[0].bbox.y == pytest.approx(100.0)
        assert regions[0].bbox.bottom == pytest.approx(122.0)  # 112 + 10


# ---------------------------------------------------------------------------
# build_layout — integration test using LABORAL-like items
# ---------------------------------------------------------------------------


class TestBuildLayout:
    """Integration test using a representative subset of LABORAL page-1 data."""

    # A small set of items drawn from the cached azuredemo__LABORAL.json:
    # - Left column header block: x≈88 (logo text)
    # - Right column main block: x≈180-267 (content)
    # The gap between x=88..148 and x=180 is ~32 pt → should produce 2 columns.
    LABORAL_ITEMS = [
        # Left block — logo area
        LiteItem(text="PLATAFORMA DE",  bbox=BBox(x=88.0,  y=36.3,  w=60.7, h=7.8),  font_name="Helvetica-Bold", font_size=7.0,  page=1),
        LiteItem(text="SERVICIOS DEL", bbox=BBox(x=88.0,  y=44.5,  w=54.1, h=7.8),  font_name="Helvetica-Bold", font_size=7.0,  page=1),
        LiteItem(text="PUNTO NEUTRO",  bbox=BBox(x=88.0,  y=52.6,  w=56.0, h=7.8),  font_name="Helvetica-Bold", font_size=7.0,  page=1),
        LiteItem(text="JUDICIAL",      bbox=BBox(x=88.0,  y=60.8,  w=32.3, h=7.8),  font_name="Helvetica-Bold", font_size=7.0,  page=1),
        # Right block — title + content
        LiteItem(text="Consulta TGSS situacion", bbox=BBox(x=229.9, y=51.5, w=167.3, h=15.6), font_name="Helvetica-Bold", font_size=14.0, page=1),
        LiteItem(text="Datos Petición",           bbox=BBox(x=255.8, y=112.6, w=83.4,  h=13.4), font_name="Helvetica-Bold", font_size=12.0, page=1),
        LiteItem(text="Nº Procedimiento: 987-15", bbox=BBox(x=180.0, y=133.7, w=119.8, h=11.2), font_name="Helvetica-Bold", font_size=10.0, page=1),
        LiteItem(text="Nº Documento: X6573514E", bbox=BBox(x=180.0, y=153.7, w=126.5, h=11.2), font_name="Helvetica-Bold", font_size=10.0, page=1),
    ]

    def test_build_layout_returns_page_1(self):
        layout = build_layout(self.LABORAL_ITEMS)
        assert 1 in layout

    def test_build_layout_returns_page_layout_namedtuple(self):
        layout = build_layout(self.LABORAL_ITEMS)
        page1 = layout[1]
        assert isinstance(page1, PageLayout)
        assert page1.page == 1

    def test_laboral_p1_has_two_columns(self):
        """Left block (x≈88) and right block (x≈180+) are > 30 pt apart."""
        layout = build_layout(self.LABORAL_ITEMS)
        page1 = layout[1]
        # At least 2 columns: logo area (x≈88) and content area (x≈180+)
        assert len(page1.columns) >= 2

    def test_laboral_p1_lines_count(self):
        layout = build_layout(self.LABORAL_ITEMS)
        page1 = layout[1]
        # 8 items, most on distinct Y values — expect at least 6 lines
        # (some may cluster within 3 pt tolerance)
        assert len(page1.lines) >= 6

    def test_laboral_p1_has_blocks(self):
        layout = build_layout(self.LABORAL_ITEMS)
        assert len(layout[1].blocks) >= 1

    def test_laboral_p1_has_regions(self):
        layout = build_layout(self.LABORAL_ITEMS)
        assert len(layout[1].regions) >= 1

    def test_empty_items_returns_empty_dict(self):
        assert build_layout([]) == {}

    def test_multi_page_produces_separate_page_entries(self):
        items = [
            _item("A", x=50, y=100, page=1),
            _item("B", x=50, y=100, page=2),
        ]
        layout = build_layout(items)
        assert set(layout.keys()) == {1, 2}
