"""Verify frozen-dataclass behaviour and basic invariants."""

from __future__ import annotations

import pytest

from docomestria import BBox, DoclingBlock, FusedItem, LiteItem, VisualRect


def test_models_are_frozen():
    bb = BBox(x=0, y=0, w=10, h=10)
    with pytest.raises(Exception):
        bb.x = 5  # type: ignore[misc]

    li = LiteItem(text="x", bbox=bb, font_name=None, font_size=None, page=1)
    with pytest.raises(Exception):
        li.text = "y"  # type: ignore[misc]


def test_docling_block_holds_label_and_layer():
    bb = BBox(x=0, y=0, w=10, h=10)
    blk = DoclingBlock(
        bbox=bb,
        label="section_header",
        heading_level=1,
        content_layer="body",
        page=1,
    )
    assert blk.label == "section_header"
    assert blk.heading_level == 1
    assert blk.content_layer == "body"


def test_visual_rect_defaults():
    bb = BBox(x=0, y=0, w=12, h=12)
    rect = VisualRect(bbox=bb, is_checkbox=True, is_filled=False, page=1)
    assert rect.rect_id == ""
    assert rect.is_checkbox is True


def test_fused_item_shape():
    bb = BBox(x=0, y=0, w=10, h=10)
    fi = FusedItem(
        text="hi",
        bbox=bb,
        font_name="Helvetica",
        font_size=10.0,
        docling_label="text",
        docling_heading_level=None,
        enclosing_box_id=None,
        section_title=None,
        page=1,
        match_method="centroid",
        match_score=1.0,
    )
    assert fi.match_method == "centroid"
    assert fi.match_score == 1.0
