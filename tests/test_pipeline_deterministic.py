"""Tests for `Pipeline(llm=None)` — deterministic, no-LLM extraction."""

from __future__ import annotations

import pytest

from docomestria import BBox, FusedItem, VisualRect
from docomestria.result import FusionResult

pytest.importorskip("rapidfuzz")

from docomestria.pipeline import ExtractionResult, Pipeline  # noqa: E402
from docomestria.transform import Field, Schema  # noqa: E402
from docomestria.transform import transformers as tr  # noqa: E402
from docomestria.transform.models import infer_labels_from_key  # noqa: E402


def _fi(
    text: str,
    x: float = 100.0,
    y: float = 100.0,
    w: float = 80.0,
    h: float = 12.0,
    section: str | None = "DATOS PERSONALES",
    box_id: str | None = "box-a",
) -> FusedItem:
    return FusedItem(
        text=text,
        bbox=BBox(x=x, y=y, w=w, h=h),
        font_name="Helvetica",
        font_size=10.0,
        docling_label="text",
        docling_heading_level=None,
        enclosing_box_id=box_id,
        section_title=section,
        page=1,
        match_method="centroid",
        match_score=1.0,
    )


def _basic_fusion() -> FusionResult:
    # Layout (one row each): "NIF:" then "51789286W"; "Apellidos:" then "LORENZO"
    items = (
        _fi("NIF:", x=50, y=100, w=30),
        _fi("51789286W", x=90, y=100, w=80),
        _fi("Apellidos:", x=50, y=120, w=60),
        _fi("LORENZO", x=120, y=120, w=80),
    )
    return FusionResult(
        items=items,
        lite_items=(),
        docling_blocks=(),
        visual_rects=(),
        coverage=1.0,
        matched_to_docling=0,
        matched_to_box=0,
        total_items=len(items),
    )


def _pdf(tmp_path) -> str:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return pdf


def _pipeline(schema: Schema, fusion: FusionResult, **kwargs) -> Pipeline:
    return Pipeline(
        schema=schema,
        llm=None,
        cache_dir=None,
        fuse_fn=lambda _p: fusion,
        **kwargs,
    )


# --------------------------------------------------------------------------- API


def test_pipeline_accepts_llm_none(tmp_path):
    schema = Schema({"nif": Field(tr.nif_es, labels=("NIF",))})
    pipe = _pipeline(schema, _basic_fusion())
    result = pipe.run(_pdf(tmp_path))
    assert isinstance(result, ExtractionResult)


def test_deterministic_extracts_explicit_labels(tmp_path):
    schema = Schema(
        {
            "nif": Field(tr.nif_es, labels=("NIF", "DNI")),
            "apellidos": Field(tr.regex(r"^[A-ZÀ-Ú ]+$"), labels=("Apellidos",)),
        }
    )
    pipe = _pipeline(schema, _basic_fusion())
    result = pipe.run(_pdf(tmp_path))
    assert result.typed_fields["nif"].normalized == "51789286W"
    assert result.typed_fields["apellidos"].normalized == "LORENZO"


def test_deterministic_infers_labels_from_key(tmp_path):
    # No explicit `labels` — derive from key "nif"
    schema = Schema({"nif": Field(tr.nif_es)})
    fusion = FusionResult(
        items=(
            _fi("Nif:", x=50, y=100, w=30),
            _fi("51789286W", x=90, y=100, w=80),
        ),
        lite_items=(),
        docling_blocks=(),
        visual_rects=(),
        coverage=1.0,
        matched_to_docling=0,
        matched_to_box=0,
        total_items=2,
    )
    pipe = _pipeline(schema, fusion)
    result = pipe.run(_pdf(tmp_path))
    assert result.typed_fields["nif"].normalized == "51789286W"


def test_infer_labels_from_key_helper():
    assert infer_labels_from_key("nif") == ("Nif",)
    out = infer_labels_from_key("datos_titular.fecha_nacimiento")
    assert "Fecha de nacimiento" in out
    assert "Fecha nacimiento" in out


# --------------------------------------------------------------------------- checkbox


def test_deterministic_checkbox_choice(tmp_path):
    # Layout: "Vivienda:" label, then options "propia" "alquiler" "padres"
    # with a filled VisualRect near "alquiler".
    items = (
        _fi("Vivienda:", x=50, y=100, w=60),
        _fi("propia", x=120, y=100, w=40),
        _fi("alquiler", x=170, y=100, w=50),
        _fi("padres", x=230, y=100, w=40),
    )
    rects = (
        VisualRect(
            bbox=BBox(x=115, y=98, w=8, h=8),
            is_checkbox=True,
            is_filled=False,
            page=1,
            rect_id="cb1",
            rect_type="checkbox",
        ),
        VisualRect(
            bbox=BBox(x=165, y=98, w=8, h=8),
            is_checkbox=True,
            is_filled=True,
            page=1,
            rect_id="cb2",
            rect_type="checkbox",
        ),
        VisualRect(
            bbox=BBox(x=225, y=98, w=8, h=8),
            is_checkbox=True,
            is_filled=False,
            page=1,
            rect_id="cb3",
            rect_type="checkbox",
        ),
    )
    fusion = FusionResult(
        items=items,
        lite_items=(),
        docling_blocks=(),
        visual_rects=rects,
        coverage=1.0,
        matched_to_docling=0,
        matched_to_box=0,
        total_items=len(items),
    )
    schema = Schema(
        {
            "vivienda": Field(
                tr.checkbox_choice(["propia", "alquiler", "padres", "otros"]),
                labels=("Vivienda",),
            )
        }
    )
    pipe = _pipeline(schema, fusion)
    result = pipe.run(_pdf(tmp_path))
    assert result.typed_fields["vivienda"].normalized == "alquiler"


# --------------------------------------------------------------------------- issues


def test_deterministic_missing_required_emits_issue(tmp_path):
    fusion = FusionResult(
        items=(_fi("Nothing here", x=50, y=100, w=80),),
        lite_items=(),
        docling_blocks=(),
        visual_rects=(),
        coverage=1.0,
        matched_to_docling=0,
        matched_to_box=0,
        total_items=1,
    )
    schema = Schema(
        {
            "nif": Field(tr.nif_es, required=True, labels=("NIF",)),
        }
    )
    pipe = _pipeline(schema, fusion)
    result = pipe.run(_pdf(tmp_path))
    assert any(
        iss.issue_type == "missing_required" and iss.severity == "high" for iss in result.issues
    )


# --------------------------------------------------------------------------- stream


def test_stream_emits_pair_fields_step(tmp_path):
    schema = Schema({"nif": Field(tr.nif_es, labels=("NIF",))})
    pipe = _pipeline(schema, _basic_fusion())
    steps = list(pipe.stream(_pdf(tmp_path)))
    names = [s.name for s in steps]
    assert "pair_fields" in names
    assert "llm_call" not in names
    assert "build_context" not in names
    assert "bind_provenance" not in names
    assert "detect_issues" not in names


def test_stream_total_steps_in_deterministic_mode(tmp_path):
    schema = Schema({"nif": Field(tr.nif_es, labels=("NIF",))})
    pipe = _pipeline(schema, _basic_fusion())
    steps = list(pipe.stream(_pdf(tmp_path)))
    # With fuse_fn the extract steps collapse to a single `extract_all` step:
    # start → cache_check → extract_all → fuse → pair_fields → apply_schema → complete
    names = [s.name for s in steps]
    assert names == [
        "start",
        "cache_check",
        "extract_all",
        "fuse",
        "pair_fields",
        "apply_schema",
        "complete",
    ]
    assert len(steps) == 7


def test_stream_pair_fields_step_carries_engine(tmp_path):
    schema = Schema({"nif": Field(tr.nif_es, labels=("NIF",))})
    pipe = _pipeline(schema, _basic_fusion())
    steps = list(pipe.stream(_pdf(tmp_path)))
    pair = next(s for s in steps if s.name == "pair_fields")
    assert pair.engine == "pairing"


# --------------------------------------------------------------------------- cost


def test_deterministic_cost_is_zero(tmp_path):
    schema = Schema({"nif": Field(tr.nif_es, labels=("NIF",))})
    pipe = _pipeline(schema, _basic_fusion())
    result = pipe.run(_pdf(tmp_path))
    assert result.cost.usd == 0.0
    assert result.cost.tokens_in == 0
    assert result.cost.tokens_out == 0
    assert result.cost.model_used == "deterministic"
    assert result.llm_calls == 0
