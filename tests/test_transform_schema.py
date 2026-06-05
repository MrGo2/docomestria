"""End-to-end Schema.apply tests with synthetic BoundValues."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from docomestria import BBox
from docomestria.llm.models import BoundValue
from docomestria.transform import Field, Schema
from docomestria.transform import transformers as tr


def _bound(name: str, value: str) -> BoundValue:
    return BoundValue(
        field_name=name,
        value=value,
        source_items=("0",),
        bbox=BBox(x=10, y=10, w=50, h=12),
        section_title="DATOS PERSONALES",
        docling_label="text",
        match_method="exact",
        match_score=1.0,
        page=1,
    )


def test_schema_applies_each_transformer():
    bound = [
        _bound("fecha", "06/12/2026"),
        _bound("nif", "51789286W"),
        _bound("importe", "1.234,56 €"),
    ]
    schema = Schema(
        {
            "fecha": Field(tr.date_es),
            "nif": Field(tr.nif_es),
            "importe": Field(tr.amount_eur),
        }
    )

    typed = schema.apply(bound)

    assert typed["fecha"].normalized == date(2026, 12, 6)
    assert typed["nif"].normalized == "51789286W"
    assert typed["importe"].normalized.amount == Decimal("1234.56")


def test_typed_value_preserves_bbox_page_source_items():
    schema = Schema({"nif": Field(tr.nif_es)})
    typed = schema.apply([_bound("nif", "51789286W")])
    tv = typed["nif"]
    assert tv.bbox is not None and tv.bbox.x == 10
    assert tv.page == 1
    assert tv.source_items == ("0",)


def test_required_missing_field_flagged():
    schema = Schema({"nif": Field(tr.nif_es, required=True)})
    typed = schema.apply([])
    assert typed["nif"].normalized is None
    assert typed["nif"].issues == ("required_field_missing",)


def test_optional_missing_field_omitted():
    schema = Schema({"nif": Field(tr.nif_es)})
    typed = schema.apply([])
    assert "nif" not in typed


def test_confidence_combines_match_and_transform_scores():
    bv = BoundValue(
        field_name="nif",
        value="51789286W",
        source_items=("0",),
        bbox=BBox(x=0, y=0, w=10, h=10),
        section_title=None,
        docling_label=None,
        match_method="fuzzy",
        match_score=0.85,
        page=1,
    )
    schema = Schema({"nif": Field(tr.nif_es)})
    tv = schema.apply([bv])["nif"]
    # nif_es returns 1.0 for valid -> 1.0 * 0.85 = 0.85
    assert abs(tv.confidence - 0.85) < 1e-6


def test_transformer_returning_none_preserves_provenance():
    schema = Schema({"fecha": Field(tr.date_es)})
    typed = schema.apply([_bound("fecha", "30/02/2026")])
    tv = typed["fecha"]
    assert tv.normalized is None
    assert "invalid_date" in tv.issues
    # bbox still preserved
    assert tv.bbox is not None


def test_typed_value_ok_property():
    schema = Schema({"nif": Field(tr.nif_es)})
    typed = schema.apply([_bound("nif", "51789286W")])
    assert typed["nif"].ok


def test_nested_field_names_supported():
    schema = Schema({"a.b": Field(tr.regex(r"^x$"))})
    typed = schema.apply([_bound("a.b", "x")])
    assert typed["a.b"].normalized == "x"
