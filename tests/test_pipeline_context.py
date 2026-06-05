"""Tests for build_llm_context — verifies furniture dropping and grouping."""

from __future__ import annotations

from docomestria import BBox, FusedItem
from docomestria.pipeline.context import FURNITURE_LABELS, build_llm_context


def _fi(text: str, *, label: str = "text", section: str | None = "S1") -> FusedItem:
    return FusedItem(
        text=text,
        bbox=BBox(x=0, y=0, w=10, h=10),
        font_name="Helvetica",
        font_size=10.0,
        docling_label=label,
        docling_heading_level=None,
        enclosing_box_id=None,
        section_title=section,
        page=1,
        match_method="centroid",
        match_score=1.0,
    )


def test_furniture_labels_are_dropped():
    items = [
        _fi("PAGE 1 OF 3", label="page_header"),
        _fi("real datum"),
        _fi("footer text", label="page_footer"),
    ]
    ctx = build_llm_context(items)
    flat = [item["t"] for sec in ctx["sections"] for item in sec["items"]]
    assert "PAGE 1 OF 3" not in flat
    assert "footer text" not in flat
    assert "real datum" in flat


def test_items_grouped_by_section_title_preserves_order():
    items = [
        _fi("A1", section="ALPHA"),
        _fi("B1", section="BETA"),
        _fi("A2", section="ALPHA"),
        _fi("B2", section="BETA"),
    ]
    ctx = build_llm_context(items)
    titles = [sec["title"] for sec in ctx["sections"]]
    # First-seen-order preserved.
    assert titles == ["ALPHA", "BETA"]
    alpha = next(sec for sec in ctx["sections"] if sec["title"] == "ALPHA")
    assert [it["t"] for it in alpha["items"]] == ["A1", "A2"]


def test_item_indices_are_preserved():
    items = [_fi("first"), _fi("second"), _fi("third")]
    ctx = build_llm_context(items)
    all_items = [item for sec in ctx["sections"] for item in sec["items"]]
    assert {it["i"] for it in all_items} == {0, 1, 2}


def test_furniture_label_set_includes_expected_labels():
    assert "page_header" in FURNITURE_LABELS
    assert "page_footer" in FURNITURE_LABELS
    assert "picture" in FURNITURE_LABELS
