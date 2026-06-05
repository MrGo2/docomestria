"""TypedValue.trace() integration tests."""

from __future__ import annotations

from docomestria import (
    BBox,
    DoclingBlock,
    FusedItem,
    FusionResult,
    LiteItem,
    VisualRect,
)
from docomestria.llm.models import BoundValue
from docomestria.transform import Field, Schema
from docomestria.transform import transformers as tr


def _build_fr_with_nif() -> tuple[FusionResult, BoundValue]:
    # One FusedItem with text "51789286W" inside a visual box, with a
    # matching LiteItem and a Docling block.
    nif_bbox = BBox(x=100, y=100, w=80, h=12)
    item = FusedItem(
        text="51789286W",
        bbox=nif_bbox,
        font_name="Helvetica",
        font_size=11.0,
        docling_label="text",
        docling_heading_level=None,
        enclosing_box_id="box-titular",
        section_title="DATOS DEL TITULAR",
        page=1,
        match_method="centroid",
        match_score=1.0,
    )
    li = LiteItem(
        text="51789286W",
        bbox=nif_bbox,
        font_name="Helvetica",
        font_size=11.0,
        page=1,
    )
    blk = DoclingBlock(
        bbox=BBox(x=90, y=90, w=200, h=30),
        label="text",
        heading_level=None,
        content_layer="body",
        page=1,
        text="51789286W",
    )
    box = VisualRect(
        bbox=BBox(x=80, y=80, w=400, h=60),
        is_checkbox=False,
        is_filled=False,
        page=1,
        rect_id="box-titular",
        rect_type="box",
    )
    fr = FusionResult(
        items=(item,),
        lite_items=(li,),
        docling_blocks=(blk,),
        visual_rects=(box,),
    )
    bv = BoundValue(
        field_name="nif",
        value="51789286W",
        source_items=("0",),
        bbox=nif_bbox,
        section_title="DATOS DEL TITULAR",
        docling_label="text",
        match_method="exact",
        match_score=1.0,
        page=1,
    )
    return fr, bv


def test_trace_walks_back_to_lite_item():
    fr, bv = _build_fr_with_nif()
    typed = Schema({"nif": Field(tr.nif_es)}).apply([bv])["nif"]
    trace = typed.trace(fr)
    assert len(trace.chains) == 1
    chain = trace.chains[0]
    assert len(chain.lite_items) == 1
    assert chain.lite_items[0].font_name == "Helvetica"


def test_trace_includes_docling_block():
    fr, bv = _build_fr_with_nif()
    typed = Schema({"nif": Field(tr.nif_es)}).apply([bv])["nif"]
    chain = typed.trace(fr).chains[0]
    assert chain.docling_block is not None
    assert chain.docling_block.label == "text"


def test_trace_includes_visual_box():
    fr, bv = _build_fr_with_nif()
    typed = Schema({"nif": Field(tr.nif_es)}).apply([bv])["nif"]
    chain = typed.trace(fr).chains[0]
    assert chain.visual_box is not None
    assert chain.visual_box.rect_id == "box-titular"


def test_trace_section_path_includes_section_title():
    fr, bv = _build_fr_with_nif()
    typed = Schema({"nif": Field(tr.nif_es)}).apply([bv])["nif"]
    chain = typed.trace(fr).chains[0]
    assert "DATOS DEL TITULAR" in chain.section_path


def test_trace_page_matches_typed_value():
    fr, bv = _build_fr_with_nif()
    typed = Schema({"nif": Field(tr.nif_es)}).apply([bv])["nif"]
    trace = typed.trace(fr)
    assert trace.page == 1


def test_typed_value_preserves_bbox_across_trace():
    fr, bv = _build_fr_with_nif()
    typed = Schema({"nif": Field(tr.nif_es)}).apply([bv])["nif"]
    assert typed.bbox is not None
    assert typed.bbox.x == 100
