"""Table detection tests — fusion logic with synthetic data (no real PDFs)."""

from __future__ import annotations

from docomestria import BBox, LiteItem, VisualRect, fuse_from_engines


def _li(text: str, x: float, y: float, page: int = 1) -> LiteItem:
    return LiteItem(
        text=text,
        bbox=BBox(x=x, y=y, w=20, h=10),
        font_name="Helvetica",
        font_size=10.0,
        page=page,
    )


def _table(bbox: BBox, grid: tuple[tuple[BBox, ...], ...], rid: str = "p1-t0") -> VisualRect:
    return VisualRect(
        bbox=bbox,
        is_checkbox=False,
        is_filled=False,
        page=1,
        rect_id=rid,
        rect_type="table",
        table_grid=grid,
    )


def _build_2x2_grid() -> VisualRect:
    # Outer table from (0,0) to (200, 100), four cells.
    cells = (
        (BBox(0, 0, 100, 50), BBox(100, 0, 100, 50)),
        (BBox(0, 50, 100, 50), BBox(100, 50, 100, 50)),
    )
    return _table(BBox(0, 0, 200, 100), cells)


def test_item_inside_top_left_cell_gets_table_metadata():
    item = _li("Header A", x=10, y=10)
    table = _build_2x2_grid()
    result = fuse_from_engines([item], [], [table])
    fi = result.items[0]
    assert fi.table_id == "p1-t0"
    assert fi.table_row == 0
    assert fi.table_col == 0
    assert fi.cell_bbox is not None
    assert fi.cell_bbox.left == 0


def test_item_in_bottom_right_cell():
    item = _li("v", x=150, y=70)
    table = _build_2x2_grid()
    result = fuse_from_engines([item], [], [table])
    fi = result.items[0]
    assert fi.table_row == 1
    assert fi.table_col == 1


def test_item_outside_table_has_no_table_metadata():
    item = _li("loose", x=300, y=300)
    table = _build_2x2_grid()
    result = fuse_from_engines([item], [], [table])
    fi = result.items[0]
    assert fi.table_id is None
    assert fi.table_row is None
    assert fi.table_col is None


def test_table_rect_serves_as_enclosing_box():
    item = _li("cell text", x=10, y=10)
    table = _build_2x2_grid()
    result = fuse_from_engines([item], [], [table])
    assert result.items[0].enclosing_box_id == "p1-t0"


def test_pdfplumber_classification_helpers():
    """Verify the small geometry helpers in the pdfplumber wrapper."""
    from docomestria.engines.pdfplumber import (
        _is_checkbox,
        _is_signature,
    )

    assert _is_checkbox(10, 10) is True
    assert _is_checkbox(50, 50) is False
    assert _is_checkbox(10, 50) is False
    # Signature: wide, thin, near bottom of page (page height 800, top=700).
    assert _is_signature(150, 10, 700, 800) is True
    assert _is_signature(150, 10, 100, 800) is False
    assert _is_signature(10, 10, 700, 800) is False
