"""Fusion logic tests using fake engine outputs (no real PDFs)."""

from __future__ import annotations

import pytest

from docomestria import BBox, DoclingBlock, LiteItem, VisualRect, fuse_from_engines


def _li(
    text: str,
    x: float,
    y: float,
    w: float = 40.0,
    h: float = 12.0,
    size: float = 10.0,
    page: int = 1,
) -> LiteItem:
    return LiteItem(
        text=text,
        bbox=BBox(x=x, y=y, w=w, h=h),
        font_name="Helvetica",
        font_size=size,
        page=page,
    )


def _blk(
    label: str, x: float, y: float, w: float, h: float, level: int | None = None, page: int = 1
) -> DoclingBlock:
    return DoclingBlock(
        bbox=BBox(x=x, y=y, w=w, h=h),
        label=label,
        heading_level=level,
        content_layer="body",
        page=page,
    )


def _rect(
    x: float, y: float, w: float, h: float, rid: str, checkbox: bool = False, page: int = 1
) -> VisualRect:
    return VisualRect(
        bbox=BBox(x=x, y=y, w=w, h=h),
        is_checkbox=checkbox,
        is_filled=False,
        page=page,
        rect_id=rid,
    )


def test_centroid_match_picks_smallest_block():
    item = _li("Hello", x=100, y=100)
    big_block = _blk("body", 0, 0, 500, 500)
    small_block = _blk("section_header", 90, 90, 100, 30, level=1)

    result = fuse_from_engines([item], [big_block, small_block], [])
    fi = result.items[0]
    assert fi.docling_label == "section_header"
    assert fi.docling_heading_level == 1
    assert fi.match_method == "centroid"
    assert fi.match_score == 1.0


def test_iou_fallback_when_no_centroid_match():
    # Item centroid is at (210, 210). Block starts at (215, 215) so the
    # centroid is NOT inside, but the boxes still overlap → IoU fallback.
    item = _li("near", x=200, y=200, w=20, h=20)
    block = _blk("text", 215, 215, 100, 100)
    result = fuse_from_engines([item], [block], [])
    fi = result.items[0]
    assert fi.docling_label == "text"
    assert fi.match_method == "iou"
    assert 0.0 < fi.match_score < 1.0


def test_no_match_when_block_disjoint():
    item = _li("x", x=10, y=10)
    block = _blk("text", 500, 500, 50, 50)
    result = fuse_from_engines([item], [block], [])
    fi = result.items[0]
    assert fi.docling_label is None
    assert fi.match_method == "none"
    assert fi.match_score == 0.0


def test_enclosing_box_and_section_title_inferred():
    title = _li("DATOS PERSONALES", x=110, y=110, size=14.0)
    name = _li("Carlos", x=110, y=140, size=10.0)
    age = _li("46", x=160, y=140, size=10.0)
    box = _rect(100, 100, 300, 200, rid="box-a")

    result = fuse_from_engines([title, name, age], [], [box])
    assert all(it.enclosing_box_id == "box-a" for it in result.items)

    title_item = result.items[0]
    name_item = result.items[1]
    # Title item should not be tagged as its own section_title.
    assert title_item.section_title is None
    assert name_item.section_title == "DATOS PERSONALES"


def test_checkbox_rect_does_not_become_enclosing_box():
    item = _li("Casado", x=120, y=120)
    box = _rect(100, 100, 400, 400, rid="form")
    cb = _rect(118, 118, 10, 10, rid="cb-1", checkbox=True)

    result = fuse_from_engines([item], [], [box, cb])
    assert result.items[0].enclosing_box_id == "form"


def test_coverage_stat():
    a = _li("a", x=10, y=10)
    b = _li("b", x=500, y=500)
    block = _blk("text", 0, 0, 100, 100)
    result = fuse_from_engines([a, b], [block], [])
    assert result.total_items == 2
    assert result.matched_to_docling == 1
    assert result.coverage == 0.5


@pytest.mark.integration
def test_fuse_on_real_pdf():
    pytest.skip("Requires LiteParse and Docling — opt in with `pytest -m integration`.")
