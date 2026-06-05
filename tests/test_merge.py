"""Tests for `docomestria.pipeline.merge.build_merged_document`."""

from __future__ import annotations

from docomestria import BBox, DoclingBlock, FusionResult, LiteItem, VisualRect
from docomestria.pipeline.merge import (
    build_merged_document,
    is_bold,
    is_italic,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lite(
    text: str,
    x: float,
    y: float,
    w: float = 20,
    h: float = 10,
    font_name: str = "Helvetica",
    font_size: float = 10.0,
    page: int = 1,
) -> LiteItem:
    return LiteItem(
        text=text,
        bbox=BBox(x=x, y=y, w=w, h=h),
        font_name=font_name,
        font_size=font_size,
        page=page,
    )


def _block(
    label: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    page: int = 1,
    level: int | None = None,
    layer: str = "body",
    cells: tuple[tuple[str, ...], ...] | None = None,
) -> DoclingBlock:
    return DoclingBlock(
        bbox=BBox(x=x, y=y, w=w, h=h),
        label=label,
        heading_level=level,
        content_layer=layer,
        page=page,
        text="",
        self_ref=None,
        cells=cells,
    )


def _fusion(
    lite: tuple[LiteItem, ...] = (),
    docling: tuple[DoclingBlock, ...] = (),
    rects: tuple[VisualRect, ...] = (),
) -> FusionResult:
    return FusionResult(
        items=(),
        lite_items=lite,
        docling_blocks=docling,
        visual_rects=rects,
    )


# ---------------------------------------------------------------------------
# Font heuristics
# ---------------------------------------------------------------------------


def test_is_bold_detects_known_tokens():
    assert is_bold("Helvetica-Bold") is True
    assert is_bold("ArialBlack") is True
    assert is_bold("Roboto-Heavy") is True
    assert is_bold("Inter-ExtraBold") is True
    assert is_bold("Inter-SemiBold") is True


def test_is_bold_negative_cases():
    assert is_bold(None) is False
    assert is_bold("") is False
    assert is_bold("Helvetica") is False
    assert is_bold("Times-Roman") is False


def test_is_italic_detects_known_tokens():
    assert is_italic("Helvetica-Italic") is True
    assert is_italic("Arial-Oblique") is True
    assert is_italic("Helvetica-BoldItalic") is True


def test_is_italic_negative_cases():
    assert is_italic(None) is False
    assert is_italic("Helvetica-Bold") is False


# ---------------------------------------------------------------------------
# Section-header / paragraph blocks
# ---------------------------------------------------------------------------


def test_section_header_with_inside_items_becomes_spans():
    header = _block("section_header", 10, 10, 200, 20, level=1)
    inside = (
        _lite("Datos", 12, 12, font_name="Helvetica-Bold", font_size=12.0),
        _lite("Peticion", 50, 12, font_name="Helvetica-Bold", font_size=12.0),
    )
    fr = _fusion(lite=inside, docling=(header,))

    doc = build_merged_document(fr)

    assert doc["page_count"] == 1
    assert len(doc["blocks"]) == 1
    block = doc["blocks"][0]
    assert block["label"] == "section_header"
    assert block["level"] == 1
    assert block["layer"] == "body"
    assert block["page"] == 1
    assert block["bbox"] == [10.0, 10.0, 200.0, 20.0]
    assert "spans" in block
    assert len(block["spans"]) == 2
    first = block["spans"][0]
    assert first["text"] == "Datos"
    assert first["font_name"] == "Helvetica-Bold"
    assert first["font_size"] == 12.0
    assert first["is_bold"] is True
    assert first["is_italic"] is False
    assert first["bbox"] == [12.0, 12.0, 20.0, 10.0]


def test_items_outside_block_are_skipped():
    para = _block("paragraph", 0, 0, 100, 100)
    inside = _lite("inside", 50, 50)
    outside = _lite("outside", 500, 500)
    fr = _fusion(lite=(inside, outside), docling=(para,))

    doc = build_merged_document(fr)

    spans = doc["blocks"][0]["spans"]
    assert [s["text"] for s in spans] == ["inside"]


def test_spans_sorted_in_reading_order_top_to_bottom():
    para = _block("paragraph", 0, 0, 200, 200)
    # Add in deliberately wrong order — should be re-sorted top-down.
    bottom = _lite("bottom", 10, 100)
    top = _lite("top", 10, 10)
    middle_right = _lite("middle-right", 100, 50)
    middle_left = _lite("middle-left", 10, 50)
    fr = _fusion(
        lite=(bottom, top, middle_right, middle_left),
        docling=(para,),
    )

    doc = build_merged_document(fr)

    texts = [s["text"] for s in doc["blocks"][0]["spans"]]
    assert texts == ["top", "middle-left", "middle-right", "bottom"]


def test_blocks_sorted_by_page_then_top_to_bottom():
    p1_b = _block("paragraph", 10, 100, 100, 20, page=1)
    p1_a = _block("paragraph", 10, 10, 100, 20, page=1)
    p2 = _block("paragraph", 10, 10, 100, 20, page=2)
    fr = _fusion(docling=(p2, p1_b, p1_a))

    doc = build_merged_document(fr)

    pages = [(b["page"], b["bbox"][1]) for b in doc["blocks"]]
    assert pages == [(1, 10.0), (1, 100.0), (2, 10.0)]
    assert doc["page_count"] == 2


# ---------------------------------------------------------------------------
# Table blocks
# ---------------------------------------------------------------------------


def test_table_groups_items_into_cells():
    # 2x2 table; cells at (95,95)+30x30, (125,95)+30x30, (95,125)+30x30, (125,125)+30x30
    table_block = _block("table", 90, 90, 70, 70)
    grid = (
        (BBox(95, 95, 30, 30), BBox(125, 95, 30, 30)),
        (BBox(95, 125, 30, 30), BBox(125, 125, 30, 30)),
    )
    table_rect = VisualRect(
        bbox=BBox(90, 90, 70, 70),
        is_checkbox=False,
        is_filled=False,
        page=1,
        rect_id="t-0",
        rect_type="table",
        table_grid=grid,
    )
    items = (
        _lite("Header A", 100, 100, font_name="Helvetica-Bold"),
        _lite("Header B", 130, 100, font_name="Helvetica-Bold"),
        _lite("987-15", 100, 130, font_name="Helvetica"),
        _lite("xyz", 130, 130, font_name="Helvetica"),
    )
    fr = _fusion(lite=items, docling=(table_block,), rects=(table_rect,))

    doc = build_merged_document(fr)

    block = doc["blocks"][0]
    assert block["label"] == "table"
    assert "cells" in block
    cells = block["cells"]
    assert len(cells) == 2
    assert len(cells[0]) == 2
    # row 0: headers, bold
    assert cells[0][0][0]["text"] == "Header A"
    assert cells[0][0][0]["is_bold"] is True
    assert cells[0][1][0]["text"] == "Header B"
    # row 1: values
    assert cells[1][0][0]["text"] == "987-15"
    assert cells[1][0][0]["is_bold"] is False
    assert cells[1][1][0]["text"] == "xyz"


def test_table_without_matching_visual_rect_falls_back():
    cells_grid = (("Header A", "Header B"), ("987-15", "xyz"))
    table_block = _block("table", 90, 90, 70, 70, cells=cells_grid)
    items = (_lite("Header A", 100, 100, font_name="Helvetica-Bold"),)
    fr = _fusion(lite=items, docling=(table_block,))

    doc = build_merged_document(fr)

    block = doc["blocks"][0]
    assert block["label"] == "table"
    assert "cells" in block
    # Fallback: 2x2 matrix shape preserved from block.cells, all spans dumped
    # in (0, 0) since we have no spatial grid.
    assert len(block["cells"]) == 2
    assert len(block["cells"][0]) == 2
    assert block["cells"][0][0][0]["text"] == "Header A"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_fusion_returns_empty_document():
    doc = build_merged_document(_fusion())

    assert doc == {"blocks": [], "page_count": 0}


def test_furniture_layer_preserved_on_block():
    footer = _block("page_footer", 10, 800, 100, 20, layer="furniture")
    inside = _lite("page 1", 12, 802)
    fr = _fusion(lite=(inside,), docling=(footer,))

    doc = build_merged_document(fr)

    assert doc["blocks"][0]["layer"] == "furniture"
    assert doc["blocks"][0]["spans"][0]["text"] == "page 1"
