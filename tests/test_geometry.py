"""Pure unit tests for the geometry layer — no PDFs required."""

from __future__ import annotations

from docomestria import BBox
from docomestria.geometry import (
    area,
    centroid,
    contains_box,
    contains_point,
    iou,
    normalize_tl,
)


def test_normalize_tl_swaps_inverted_coords():
    assert normalize_tl((10.0, 20.0, 5.0, 5.0)) == (5.0, 5.0, 10.0, 20.0)


def test_area_is_zero_for_degenerate_box():
    assert area((10.0, 10.0, 10.0, 20.0)) == 0.0
    assert area((10.0, 10.0, 20.0, 20.0)) == 100.0


def test_centroid():
    assert centroid((0.0, 0.0, 10.0, 20.0)) == (5.0, 10.0)


def test_contains_point_includes_borders():
    box = (0.0, 0.0, 10.0, 10.0)
    assert contains_point(box, 0.0, 0.0)
    assert contains_point(box, 10.0, 10.0)
    assert contains_point(box, 5.0, 5.0)
    assert not contains_point(box, 11.0, 5.0)


def test_iou_disjoint_is_zero():
    assert iou((0.0, 0.0, 1.0, 1.0), (2.0, 2.0, 3.0, 3.0)) == 0.0


def test_iou_identical_is_one():
    box = (0.0, 0.0, 10.0, 10.0)
    assert iou(box, box) == 1.0


def test_iou_partial_overlap():
    a = (0.0, 0.0, 10.0, 10.0)
    b = (5.0, 5.0, 15.0, 15.0)
    # intersection area = 25, union = 100 + 100 - 25 = 175
    assert abs(iou(a, b) - (25.0 / 175.0)) < 1e-9


def test_contains_box_with_tolerance():
    outer = (0.0, 0.0, 100.0, 100.0)
    inner = (10.0, 10.0, 90.0, 90.0)
    assert contains_box(outer, inner)
    assert not contains_box(outer, (-1.0, 0.0, 50.0, 50.0))
    # within default tolerance
    assert contains_box(outer, (-0.2, -0.2, 50.0, 50.0))


def test_bbox_roundtrip():
    bb = BBox.from_ltrb(10, 20, 30, 50)
    assert bb.left == 10 and bb.top == 20
    assert bb.right == 30 and bb.bottom == 50
    assert bb.area == 20 * 30
    assert bb.centroid == (20.0, 35.0)


def test_bbox_contains_other():
    outer = BBox.from_ltrb(0, 0, 100, 100)
    inner = BBox.from_ltrb(10, 10, 50, 50)
    assert outer.contains(inner)
    assert not inner.contains(outer)


def test_bbox_iou_self_is_one():
    bb = BBox(x=0, y=0, w=10, h=10)
    assert bb.iou(bb) == 1.0
