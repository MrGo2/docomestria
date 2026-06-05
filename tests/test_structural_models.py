"""Tests for structural model serialisation + hierarchical grouping (v0.7.2)."""

from __future__ import annotations

import json

from docomestria.models import BBox
from docomestria.structural.models import (
    SCHEMA_VERSION,
    Confidence,
    Pair,
    StructuralExtraction,
)


def _pair(
    label: str,
    value: str,
    page: int = 1,
    y: float = 0.0,
    section: str | None = None,
    subsection: str | None = None,
    column_index: int | None = None,
    evidence: tuple[str, ...] = ("D-2col",),
    score: float = 0.85,
    confidence: Confidence = Confidence.HIGH,
) -> Pair:
    bb = BBox(x=10.0, y=y, w=80.0, h=12.0)
    return Pair(
        label_text=label,
        value_text=value,
        label_bbox=bb,
        value_bbox=BBox(x=200.0, y=y, w=80.0, h=12.0),
        page=page,
        score=score,
        confidence=confidence,
        evidence=evidence,
        section_title=section,
        subsection_title=subsection,
        column_index=column_index,
    )


def test_pair_to_dict_canonical_schema():
    p = _pair("TAE", "12,6020%", page=3, y=450.0, subsection="Condiciones económicas")
    d = p.to_dict()
    assert d["label"] == "TAE"
    assert d["value"] == "12,6020%"
    assert d["page"] == 3
    assert d["bbox"] == {"x": 10.0, "y": 450.0, "w": 80.0, "h": 12.0}
    assert d["rule"] == "D-2col"
    assert d["score"] == 0.85
    assert d["confidence"] == "HIGH"
    assert d["sub_section"] == "Condiciones económicas"
    # column_index omitted when None
    assert "column_index" not in d


def test_pair_to_dict_includes_column_index_when_present():
    p = _pair("Nombre", "Carlos", column_index=2)
    d = p.to_dict()
    assert d["column_index"] == 2


def test_pair_to_dict_confidence_levels_upper_cased():
    for c in (Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW):
        d = _pair("L", "V", confidence=c).to_dict()
        assert d["confidence"] == c.value.upper()
        assert d["confidence"] in {"HIGH", "MEDIUM", "LOW"}


def test_pair_to_dict_empty_evidence_yields_empty_rule():
    p = _pair("L", "V", evidence=())
    assert p.to_dict()["rule"] == ""


def test_iter_grouped_sections_only():
    p1 = _pair("A", "1", page=1, y=10.0, section="Sec1")
    p2 = _pair("B", "2", page=1, y=20.0, section="Sec1")
    p3 = _pair("C", "3", page=1, y=30.0, section="Sec2")
    ext = StructuralExtraction(pages=(), pairs=(p1, p2, p3))
    grouped = list(ext.iter_grouped())
    assert len(grouped) == 2
    assert grouped[0][0] == "Sec1" and grouped[0][1] is None
    assert tuple(x.label_text for x in grouped[0][2]) == ("A", "B")
    assert grouped[1][0] == "Sec2" and grouped[1][1] is None
    assert tuple(x.label_text for x in grouped[1][2]) == ("C",)


def test_iter_grouped_with_subsections():
    p1 = _pair("A", "1", page=1, y=10.0, section="Sec1", subsection="Sub1")
    p2 = _pair("B", "2", page=1, y=20.0, section="Sec1", subsection="Sub2")
    p3 = _pair("C", "3", page=1, y=30.0, section="Sec1", subsection="Sub1")
    p4 = _pair("D", "4", page=2, y=10.0, section="Sec2")
    ext = StructuralExtraction(pages=(), pairs=(p1, p2, p3, p4))
    grouped = list(ext.iter_grouped())
    # Sec1/Sub1 (first p1 y=10) before Sec1/Sub2 (first p2 y=20)
    assert grouped[0] == ("Sec1", "Sub1", (p1, p3))
    assert grouped[1] == ("Sec1", "Sub2", (p2,))
    assert grouped[2] == ("Sec2", None, (p4,))


def test_iter_grouped_with_no_section():
    p1 = _pair("A", "1", page=1, y=5.0)
    p2 = _pair("B", "2", page=1, y=15.0, section="S")
    ext = StructuralExtraction(pages=(), pairs=(p1, p2))
    grouped = list(ext.iter_grouped())
    assert grouped[0][0] is None
    assert grouped[1][0] == "S"


def test_to_json_full_structure():
    p1 = _pair("TAE", "12%", page=3, y=450.0, section="Datos", subsection="Cond")
    p2 = _pair("TIN", "10%", page=3, y=460.0, section="Datos", subsection="Cond")
    p3 = _pair("Otro", "X", page=3, y=470.0, section="Datos")
    ext = StructuralExtraction(pages=(), pairs=(p1, p2, p3))
    payload = ext.to_json()
    assert payload["schema_version"] == SCHEMA_VERSION == 1
    assert payload["page_count"] == 0
    assert payload["pair_count"] == 3
    assert len(payload["sections"]) == 1
    sec = payload["sections"][0]
    assert sec["title"] == "Datos"
    assert len(sec["subsections"]) == 2
    assert sec["subsections"][0]["title"] == "Cond"
    assert len(sec["subsections"][0]["pairs"]) == 2
    assert sec["subsections"][0]["pairs"][0]["label"] == "TAE"
    assert sec["subsections"][1]["title"] is None
    assert sec["subsections"][1]["pairs"][0]["label"] == "Otro"


def test_to_json_empty_extraction():
    ext = StructuralExtraction(pages=(), pairs=())
    payload = ext.to_json()
    assert payload == {
        "schema_version": 1,
        "page_count": 0,
        "pair_count": 0,
        "sections": [],
    }


def test_to_json_round_trip_via_json_dumps():
    p = _pair("L", "V", section="S", subsection="Sub", column_index=1)
    ext = StructuralExtraction(pages=(), pairs=(p,))
    payload = ext.to_json()
    s = json.dumps(payload)
    decoded = json.loads(s)
    assert decoded["pair_count"] == 1
    assert decoded["sections"][0]["title"] == "S"
    assert decoded["sections"][0]["subsections"][0]["pairs"][0]["column_index"] == 1
    assert decoded["sections"][0]["subsections"][0]["pairs"][0]["sub_section"] == "Sub"


def test_to_json_sorts_by_page_then_y():
    # Out-of-order pairs in tuple → output sections sorted by first-pair (page, y)
    later = _pair("Later", "x", page=2, y=10.0, section="SecB")
    earlier = _pair("Earlier", "y", page=1, y=50.0, section="SecA")
    ext = StructuralExtraction(pages=(), pairs=(later, earlier))
    payload = ext.to_json()
    titles = [s["title"] for s in payload["sections"]]
    assert titles == ["SecA", "SecB"]
