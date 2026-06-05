"""Form transformer tests — checkboxes with VisualRect fixtures."""

from __future__ import annotations

from docomestria import BBox, FusionResult, VisualRect
from docomestria.llm.models import BoundValue
from docomestria.transform.models import TransformContext
from docomestria.transform.transformers import (
    checkbox_binary,
    checkbox_choice,
    multi_checkbox,
)


def _bound(value: str, bbox: BBox, page: int = 1) -> BoundValue:
    return BoundValue(
        field_name="x",
        value=value,
        source_items=("0",),
        bbox=bbox,
        section_title=None,
        docling_label=None,
        match_method="exact",
        match_score=1.0,
        page=page,
    )


def _checkbox(x: float, y: float, filled: bool, rid: str) -> VisualRect:
    return VisualRect(
        bbox=BBox(x=x, y=y, w=10, h=10),
        is_checkbox=True,
        is_filled=filled,
        page=1,
        rect_id=rid,
        rect_type="checkbox",
    )


def _ctx_with_checkbox(filled: bool) -> TransformContext:
    cb = _checkbox(100, 100, filled, "cb-1")
    bv = _bound("alquiler", BBox(x=95, y=95, w=20, h=20))
    fr = FusionResult(
        items=(),
        lite_items=(),
        docling_blocks=(),
        visual_rects=(cb,),
    )
    return TransformContext(bound_value=bv, fusion_result=fr, field_name="x")


def test_checkbox_choice_valid_value():
    fn = checkbox_choice(["propia", "alquiler", "padres", "otros"])
    ctx = _ctx_with_checkbox(filled=True)
    v, c, i = fn("alquiler", context=ctx)
    assert v == "alquiler"
    assert c == 1.0
    assert i == ()


def test_checkbox_choice_unfilled_lowers_confidence():
    fn = checkbox_choice(["propia", "alquiler"])
    ctx = _ctx_with_checkbox(filled=False)
    v, c, i = fn("alquiler", context=ctx)
    assert v == "alquiler"
    assert c < 1.0
    assert "no_filled_checkbox_nearby" in i


def test_checkbox_choice_not_in_choices():
    fn = checkbox_choice(["propia", "alquiler"])
    v, _, i = fn("foo")
    assert v is None
    assert "not_in_choices" in i


def test_checkbox_binary_true():
    fn = checkbox_binary("V", "H")
    v, c, _ = fn("V")
    assert v is True
    assert c == 1.0


def test_checkbox_binary_false():
    fn = checkbox_binary("V", "H")
    v, _, _ = fn("H")
    assert v is False


def test_checkbox_binary_unknown_label():
    fn = checkbox_binary("V", "H")
    v, _, i = fn("X")
    assert v is None
    assert "not_binary_label" in i


def test_multi_checkbox_valid():
    fn = multi_checkbox(["a", "b", "c"])
    v, c, i = fn("a, b")
    assert v == ["a", "b"]
    assert c == 1.0
    assert i == ()


def test_multi_checkbox_unknown_lowers_confidence():
    fn = multi_checkbox(["a", "b"])
    v, c, i = fn("a, z")
    assert v == ["a"]
    assert c < 1.0
    assert "unknown_choice" in i
