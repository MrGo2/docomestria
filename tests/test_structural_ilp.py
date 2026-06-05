"""ILP / global conflict resolution (sección 6.5)."""

from __future__ import annotations

from docomestria.models import BBox
from docomestria.structural.ilp import resolve_conflicts, resolve_conflicts_lp
from docomestria.structural.models import Confidence, Pair


def _pair(
    label: str,
    value: str,
    *,
    page: int = 1,
    score: float = 0.85,
    column_index: int | None = None,
) -> Pair:
    return Pair(
        label_text=label,
        value_text=value,
        label_bbox=BBox(x=0.0, y=0.0, w=10.0, h=10.0),
        value_bbox=BBox(x=20.0, y=0.0, w=10.0, h=10.0),
        page=page,
        score=score,
        confidence=Confidence.HIGH,
        evidence=("D-2col",),
        section_title=None,
        subsection_title=None,
        column_index=column_index,
    )


def test_no_conflicts_returns_all_pairs():
    pairs = (
        _pair("TAE", "12,60%"),
        _pair("Cuota", "443€"),
        _pair("DNI", "X6573514E"),
    )
    out = resolve_conflicts(pairs)
    assert len(out) == 3


def test_label_conflict_keeps_highest_score():
    """Two pairs with same (page, label) and no column_index → keep best."""
    pairs = (
        _pair("TAE", "12,60%", score=0.85),
        _pair("TAE", "wrong", score=0.55),
    )
    out = resolve_conflicts(pairs)
    assert [p.value_text for p in out] == ["12,60%"]


def test_column_index_variants_never_conflict():
    """Same label across distinct column_index values must all survive
    (parallel-column extraction — BBVA5 TAE Sin/Con)."""
    pairs = (
        _pair("TAE", "12,60%", score=0.85, column_index=1),
        _pair("TAE", "11,48%", score=0.85, column_index=2),
    )
    out = resolve_conflicts(pairs)
    assert len(out) == 2
    assert {p.column_index for p in out} == {1, 2}


def test_column_indexed_pair_conflicts_within_same_column():
    """Two pairs at the same column_index conflict — keep the higher-scoring."""
    pairs = (
        _pair("TAE", "12,60%", score=0.85, column_index=1),
        _pair("TAE", "wrong", score=0.55, column_index=1),
    )
    out = resolve_conflicts(pairs)
    assert [p.value_text for p in out] == ["12,60%"]


def test_different_pages_never_conflict():
    """Same label on different pages = different conflict keys."""
    pairs = (
        _pair("TAE", "12,60%", page=1),
        _pair("TAE", "11,48%", page=2),
    )
    out = resolve_conflicts(pairs)
    assert len(out) == 2


def test_normalisation_is_case_insensitive():
    """'TAE' and 'tae' share the same conflict key."""
    pairs = (
        _pair("TAE", "12,60%", score=0.85),
        _pair("tae", "wrong", score=0.55),
    )
    out = resolve_conflicts(pairs)
    assert len(out) == 1


def test_empty_label_pair_skips_conflict_resolution():
    """A pair with an empty label has no conflict key and always passes."""
    pairs = (
        _pair("", "lone-value"),
        _pair("Real", "x"),
    )
    out = resolve_conflicts(pairs)
    assert len(out) == 2


def test_resolve_conflicts_preserves_input_order():
    """Survivors come back in their original input order (stable selection)."""
    pairs = (
        _pair("Z", "z"),
        _pair("A", "a"),
        _pair("M", "m"),
    )
    out = resolve_conflicts(pairs)
    assert [p.label_text for p in out] == ["Z", "A", "M"]


def test_resolve_conflicts_lp_matches_greedy_on_small_graph():
    """LP solver and greedy produce the same survivors on simple cases."""
    pairs = (
        _pair("TAE", "12,60%", score=0.85),
        _pair("TAE", "wrong", score=0.55),
        _pair("Cuota", "443€", score=0.80),
    )
    greedy = resolve_conflicts(pairs)
    lp = resolve_conflicts_lp(pairs)
    assert {p.value_text for p in greedy} == {p.value_text for p in lp}
