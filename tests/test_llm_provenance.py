"""Tests for the optional `docomestria.llm` sub-package."""

from __future__ import annotations

import pytest

from docomestria import BBox, FusedItem

pytest.importorskip("rapidfuzz")

from docomestria.llm import (  # noqa: E402
    BoundValue,
    ProvenanceIssue,
    bind_provenance,
    detect_hallucinations,
    detect_role_mismatches,
)

# --- fixtures --------------------------------------------------------------


def _fi(
    text: str,
    x: float = 100.0,
    y: float = 100.0,
    w: float = 80.0,
    h: float = 12.0,
    label: str | None = "text",
    section: str | None = "DATOS PERSONALES",
    page: int = 1,
) -> FusedItem:
    return FusedItem(
        text=text,
        bbox=BBox(x=x, y=y, w=w, h=h),
        font_name="Helvetica",
        font_size=10.0,
        docling_label=label,
        docling_heading_level=None,
        enclosing_box_id="box-a",
        section_title=section,
        page=page,
        match_method="centroid",
        match_score=1.0,
    )


def _items() -> list[FusedItem]:
    return [
        _fi("APELLIDOS", x=100, y=100, label="section_header", section=None),
        _fi("ZAIDAN HASSAN", x=100, y=120),
        _fi("NOMBRE", x=300, y=100, label="section_header", section=None),
        _fi("CLAUDIO ALEJANDRO", x=300, y=120),
        _fi("NIF", x=100, y=200, label="section_header", section=None),
        _fi("51789286W", x=100, y=220),
    ]


# --- exact / substring / fuzzy --------------------------------------------


def test_exact_match_single_item():
    bound = bind_provenance({"nif": "51789286W"}, _items())
    assert len(bound) == 1
    bv = bound[0]
    assert bv.field_name == "nif"
    assert bv.match_method in ("exact", "substring")
    assert bv.match_score >= 0.95
    assert bv.page == 1
    assert bv.bbox is not None


def test_substring_match_spans_adjacent_items():
    bound = bind_provenance({"nombre_completo": "CLAUDIO ALEJANDRO"}, _items())
    bv = bound[0]
    assert bv.match_method in ("exact", "substring")
    assert bv.match_score >= 0.9
    # The single item already contains the full phrase, so 1 source index suffices.
    assert len(bv.source_items) >= 1


def test_fuzzy_match_tolerates_typo():
    # "ZAIDAN HASSAM" with a typo on the last letter (N -> M).
    bound = bind_provenance({"apellidos": "ZAIDAN HASSAM"}, _items())
    bv = bound[0]
    assert bv.match_method == "fuzzy"
    assert 0.85 <= bv.match_score <= 1.0


def test_hallucination_when_value_not_in_items():
    bound = bind_provenance({"telefono": "+34 600 999 888"}, _items())
    issues = detect_hallucinations(bound)
    assert len(issues) == 1
    assert issues[0].issue_type == "hallucination"
    assert issues[0].severity == "high"


def test_role_mismatch_when_bound_to_section_header():
    # "APELLIDOS" is itself a section_header in our fixture; if the LLM
    # mistakenly returned the heading text as a value, we should flag it.
    bound = bind_provenance({"apellidos": "APELLIDOS"}, _items())
    issues = detect_role_mismatches(bound)
    assert len(issues) == 1
    assert issues[0].issue_type == "role_mismatch"


def test_nested_dict_is_walked_recursively():
    payload = {
        "datos_titular": {
            "apellidos": "ZAIDAN HASSAN",
            "nombre": "CLAUDIO ALEJANDRO",
        },
        "documento": {"nif": "51789286W"},
    }
    bound = bind_provenance(payload, _items())
    fields = {bv.field_name for bv in bound}
    assert "datos_titular.apellidos" in fields
    assert "datos_titular.nombre" in fields
    assert "documento.nif" in fields
    # All three should match cleanly.
    assert all(bv.match_score >= 0.9 for bv in bound)


def test_not_found_returns_bound_value_with_zero_score():
    bound = bind_provenance({"missing": "DOES NOT APPEAR ANYWHERE"}, _items())
    bv = bound[0]
    assert bv.match_method == "not_found"
    assert bv.match_score == 0.0
    assert bv.bbox is None
    assert bv.source_items == ()


def test_bound_value_is_frozen():
    bv = BoundValue(
        field_name="x",
        value="y",
        source_items=(),
        bbox=None,
        section_title=None,
        docling_label=None,
        match_method="not_found",
        match_score=0.0,
        page=None,
    )
    with pytest.raises(Exception):  # dataclass FrozenInstanceError
        bv.value = "z"  # type: ignore[misc]


def test_provenance_issue_is_frozen():
    issue = ProvenanceIssue(
        field_name="x", value="y", issue_type="hallucination", severity="high", detail="d"
    )
    with pytest.raises(Exception):
        issue.severity = "low"  # type: ignore[misc]


def test_low_confidence_flagged_when_under_threshold():
    # Force a fuzzy-borderline match; raise the require_score to provoke flag.
    bound = bind_provenance({"apellidos": "ZAIDAN HASSAM"}, _items())
    issues = detect_hallucinations(bound, require_score=0.99)
    # The fuzzy match scores under 0.99, so it should be flagged low_confidence.
    assert any(i.issue_type == "low_confidence" for i in issues)


def test_empty_llm_output_returns_empty_list():
    assert bind_provenance({}, _items()) == []


def test_none_values_are_skipped():
    bound = bind_provenance({"nif": "51789286W", "missing": None}, _items())
    assert len(bound) == 1
    assert bound[0].field_name == "nif"
