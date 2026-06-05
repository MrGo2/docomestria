"""FusionResult resolver tests."""

from __future__ import annotations

from docomestria import (
    BBox,
    FusedItem,
    FusionResult,
    LiteItem,
    VisualRect,
)


def _fi(text: str, x: float, y: float, **kw) -> FusedItem:
    defaults = dict(
        text=text,
        bbox=BBox(x=x, y=y, w=20, h=10),
        font_name="Helvetica",
        font_size=10.0,
        docling_label=None,
        docling_heading_level=None,
        enclosing_box_id=None,
        section_title=None,
        page=1,
        match_method="none",
        match_score=0.0,
        table_id=None,
        table_row=None,
        table_col=None,
        cell_bbox=None,
    )
    defaults.update(kw)
    return FusedItem(**defaults)


def _li(text: str, x: float, y: float) -> LiteItem:
    return LiteItem(
        text=text,
        bbox=BBox(x=x, y=y, w=20, h=10),
        font_name="Helvetica",
        font_size=10.0,
        page=1,
    )


def _build_result() -> FusionResult:
    items = (
        _fi("a", 10, 10, enclosing_box_id="box-1"),
        _fi("b", 20, 20, enclosing_box_id="box-1"),
        _fi(
            "c",
            100,
            100,
            table_id="t-0",
            table_row=0,
            table_col=0,
            cell_bbox=BBox(95, 95, 30, 30),
            enclosing_box_id="t-0",
        ),
    )
    rects = (
        VisualRect(
            bbox=BBox(0, 0, 50, 50),
            is_checkbox=False,
            is_filled=False,
            page=1,
            rect_id="box-1",
            rect_type="box",
        ),
        VisualRect(
            bbox=BBox(90, 90, 200, 200),
            is_checkbox=False,
            is_filled=False,
            page=1,
            rect_id="t-0",
            rect_type="table",
            table_grid=((BBox(95, 95, 30, 30),),),
        ),
    )
    return FusionResult(
        items=items,
        lite_items=(_li("a", 10, 10), _li("c", 100, 100)),
        docling_blocks=(),
        visual_rects=rects,
        total_items=3,
    )


def test_get_item_by_string_index():
    fr = _build_result()
    assert fr.get_item("0").text == "a"
    assert fr.get_item("2").text == "c"


def test_get_box_by_rect_id():
    fr = _build_result()
    assert fr.get_box("box-1").rect_id == "box-1"


def test_get_box_missing_raises():
    fr = _build_result()
    try:
        fr.get_box("nope")
    except KeyError:
        return
    raise AssertionError("KeyError not raised")


def test_get_table_only_returns_tables():
    fr = _build_result()
    assert fr.get_table("t-0").rect_type == "table"


def test_items_in_box():
    fr = _build_result()
    inside = fr.items_in_box("box-1")
    assert len(inside) == 2
    assert {it.text for it in inside} == {"a", "b"}


def test_items_in_table_cell():
    fr = _build_result()
    cell_items = fr.items_in_table_cell("t-0", 0, 0)
    assert len(cell_items) == 1
    assert cell_items[0].text == "c"


def test_resolve_returns_provenance_chain():
    fr = _build_result()
    chain = fr.resolve(fr.get_item("0"))
    assert chain.fused_item.text == "a"
    assert chain.visual_box is not None
    assert chain.visual_box.rect_id == "box-1"
    assert any(li.text == "a" for li in chain.lite_items)


def test_resolve_table_cell_populated_for_table_item():
    fr = _build_result()
    chain = fr.resolve(fr.get_item("2"))
    assert chain.table_cell is not None
    assert chain.table_cell.table_id == "t-0"
    assert chain.table_cell.row == 0
    assert chain.table_cell.col == 0
