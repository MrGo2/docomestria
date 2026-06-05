"""Tests for label-value pairing within enclosing boxes."""

from __future__ import annotations

from docomestria import BBox, FusedItem, pair_labels_to_values


def _fi(
    text: str, x: float, y: float, box_id: str | None = "box-a", w: float = 50.0, h: float = 12.0
) -> FusedItem:
    return FusedItem(
        text=text,
        bbox=BBox(x=x, y=y, w=w, h=h),
        font_name="Helvetica",
        font_size=10.0,
        docling_label=None,
        docling_heading_level=None,
        enclosing_box_id=box_id,
        section_title=None,
        page=1,
        match_method="none",
        match_score=0.0,
    )


def test_simple_label_value_pair():
    items = [
        _fi("Nombre:", x=100, y=100, w=40, h=12),
        _fi("Carlos", x=150, y=100, w=40, h=12),
    ]
    pairs = pair_labels_to_values(items)
    assert pairs == {"Nombre": "Carlos"}


def test_only_matches_within_same_box():
    items = [
        _fi("Nombre:", x=100, y=100, w=40, h=12, box_id="box-a"),
        _fi("Carlos", x=150, y=100, w=40, h=12, box_id="box-b"),
    ]
    pairs = pair_labels_to_values(items)
    assert pairs == {}


def test_picks_nearest_value_on_same_row():
    items = [
        _fi("Apellido:", x=100, y=100, w=40, h=12),
        _fi("Lorenzo", x=150, y=100, w=40, h=12),
        _fi("Solano", x=250, y=100, w=40, h=12),
    ]
    pairs = pair_labels_to_values(items)
    assert pairs == {"Apellido": "Lorenzo"}


def test_skips_label_without_value():
    items = [
        _fi("Nombre:", x=100, y=100, w=40, h=12),
        _fi("Apellido:", x=100, y=200, w=40, h=12),
        _fi("Lorenzo", x=150, y=200, w=40, h=12),
    ]
    pairs = pair_labels_to_values(items)
    assert pairs == {"Apellido": "Lorenzo"}
