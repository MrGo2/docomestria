"""Structural pair scoring and dedup regression tests."""

from __future__ import annotations

import pytest

from docomestria.models import BBox
from docomestria.structural import PairCandidate, resolve_pairs, score_one
from docomestria.structural.ds import (
    VACUOUS,
    MassFunction,
    belief,
    combine_dempster,
    combined_mass,
    docling_mass,
    liteparse_mass,
    pdfplumber_mass,
    plausibility,
)


def test_dedup_preserves_same_label_value_in_different_columns():
    bbox = BBox(x=0, y=0, w=10, h=10)
    pairs = resolve_pairs(
        (
            PairCandidate(
                label_text="N.I.F.",
                value_text="-",
                label_bbox=bbox,
                value_bbox=bbox,
                page=1,
                rule="L-twocol-form",
                column_index=1,
            ),
            PairCandidate(
                label_text="N.I.F.",
                value_text="-",
                label_bbox=bbox,
                value_bbox=bbox,
                page=1,
                rule="L-twocol-form",
                column_index=2,
            ),
        )
    )

    assert [(p.label_text, p.value_text, p.column_index) for p in pairs] == [
        ("N.I.F.", "-", 1),
        ("N.I.F.", "-", 2),
    ]


# --------------------------------------------------------------------------
# Dempster-Shafer evidence combination (capa 3.6 — voto cruzado)
# --------------------------------------------------------------------------


def test_mass_function_components_must_sum_to_one():
    with pytest.raises(ValueError):
        MassFunction(support=0.5, refute=0.5, ignorance=0.5)


def test_combine_dempster_both_support_yields_high_combined_support():
    """When two engines both support a pair, combined belief > either input."""
    m1 = MassFunction(support=0.6, refute=0.0, ignorance=0.4)
    m2 = MassFunction(support=0.5, refute=0.0, ignorance=0.5)
    combined = combine_dempster(m1, m2)

    assert combined.support > m1.support
    assert combined.support > m2.support
    assert combined.refute == 0.0
    # support + refute + ignorance must still sum to ~1
    assert abs(combined.support + combined.refute + combined.ignorance - 1.0) < 1e-6


def test_combine_dempster_with_ignorant_engine_preserves_signal():
    """A fully ignorant engine should not erase the other engine's evidence."""
    informed = MassFunction(support=0.6, refute=0.0, ignorance=0.4)
    combined = combine_dempster(informed, VACUOUS)

    assert combined.support == pytest.approx(informed.support)
    assert combined.refute == pytest.approx(informed.refute)
    assert combined.ignorance == pytest.approx(informed.ignorance)


def test_belief_and_plausibility_bracket_probability():
    m = MassFunction(support=0.3, refute=0.1, ignorance=0.6)
    assert belief(m) == pytest.approx(0.3)
    assert plausibility(m) == pytest.approx(0.9)
    assert belief(m) <= plausibility(m)


def test_docling_mass_on_d_2col_candidate_gives_high_support():
    bbox = BBox(x=0, y=0, w=10, h=10)
    c = PairCandidate(
        label_text="Importe",
        value_text="100,00",
        label_bbox=bbox,
        value_bbox=bbox,
        page=1,
        rule="D-2col",
        features={"table_source": "fused", "label_ends_with_colon": False},
    )
    m = docling_mass(c)
    assert m.support >= 0.6
    assert m.refute == 0.0


def test_docling_mass_on_lite_only_candidate_is_ignorant():
    bbox = BBox(x=0, y=0, w=10, h=10)
    c = PairCandidate(
        label_text="N.I.F.",
        value_text="123",
        label_bbox=bbox,
        value_bbox=bbox,
        page=1,
        rule="L-horizontal",
        features={"label_ends_with_colon": True, "x_gap": 20},
    )
    m = docling_mass(c)
    assert m.ignorance == 1.0
    assert m.support == 0.0


def test_liteparse_mass_on_l_horizontal_candidate_gives_high_support():
    bbox = BBox(x=0, y=0, w=10, h=10)
    c = PairCandidate(
        label_text="Saldo:",
        value_text="1.234,56",
        label_bbox=bbox,
        value_bbox=bbox,
        page=1,
        rule="L-horizontal",
        features={"label_ends_with_colon": True, "x_gap": 15},
    )
    m = liteparse_mass(c)
    # Baseline 0.40 + 0.15 (colon) + 0.10 (tight x_gap) → capped 0.55
    assert m.support >= 0.5
    assert m.refute == 0.0


def test_pdfplumber_mass_only_speaks_through_table_source():
    bbox = BBox(x=0, y=0, w=10, h=10)
    c_fused = PairCandidate(
        label_text="x", value_text="y", label_bbox=bbox, value_bbox=bbox,
        page=1, rule="D-2col", features={"table_source": "fused"},
    )
    c_no_source = PairCandidate(
        label_text="x", value_text="y", label_bbox=bbox, value_bbox=bbox,
        page=1, rule="L-horizontal", features={},
    )
    assert pdfplumber_mass(c_fused).support >= 0.5
    assert pdfplumber_mass(c_no_source).ignorance == 1.0


def test_combined_mass_d2col_fused_with_colon_label_gives_strong_belief():
    """A D-2col candidate from a fused table is supported by 2 engines."""
    bbox = BBox(x=0, y=0, w=10, h=10)
    c = PairCandidate(
        label_text="Importe",
        value_text="100,00",
        label_bbox=bbox,
        value_bbox=bbox,
        page=1,
        rule="D-2col",
        features={"table_source": "fused", "label_ends_with_colon": False},
    )
    m = combined_mass(c)
    # Docling support 0.6 + pdfplumber support 0.5 → belief well above 0.6
    assert belief(m) >= 0.7


def test_score_one_with_three_engine_agreement_via_resolve_pairs():
    """When 3 emitters confirm the same logical pair, score is HIGH and the
    cross-vote bonus (+0.15) lifts confidence to the HIGH band."""
    bbox = BBox(x=0, y=0, w=10, h=10)
    candidates = (
        PairCandidate(
            label_text="Importe",
            value_text="100,00",
            label_bbox=bbox,
            value_bbox=bbox,
            page=1,
            rule="D-2col",
            features={"table_source": "fused"},
        ),
        PairCandidate(
            label_text="Importe",
            value_text="100,00",
            label_bbox=bbox,
            value_bbox=bbox,
            page=1,
            rule="L-horizontal",
            features={"label_ends_with_colon": True, "x_gap": 15},
        ),
        PairCandidate(
            label_text="Importe",
            value_text="100,00",
            label_bbox=bbox,
            value_bbox=bbox,
            page=1,
            rule="L-inline-split",
            features={"label_ends_with_colon": True},
        ),
    )
    pairs = resolve_pairs(candidates)
    assert len(pairs) == 1
    pair = pairs[0]
    assert len(pair.evidence) == 3
    # D-2col base 0.80 + DS lift + 0.15 cross-vote bump → clamped at 1.0
    assert pair.score >= 0.95
    assert pair.confidence.value == "high"


def test_score_one_ds_nudge_is_bounded():
    """DS belief must lift the additive score by at most DS_MAX_NUDGE."""
    bbox = BBox(x=0, y=0, w=10, h=10)
    # Same rule (L-horizontal) with and without DS-supporting features.
    with_signals = PairCandidate(
        label_text="Saldo:",
        value_text="1.234,56",
        label_bbox=bbox,
        value_bbox=bbox,
        page=1,
        rule="L-horizontal",
        features={"label_ends_with_colon": True, "x_gap": 15},
    )
    without_signals = PairCandidate(
        label_text="Saldo",
        value_text="1.234,56",
        label_bbox=bbox,
        value_bbox=bbox,
        page=1,
        rule="L-horizontal",
        features={"label_ends_with_colon": False, "x_gap": 200},
    )
    delta = score_one(with_signals) - score_one(without_signals)
    # The difference comes from BONUS_COLON (+0.10) + BONUS_TIGHT_X_GAP (+0.05)
    # + a small DS lift (≤ 0.02).  Confirm the DS lift never dominates the
    # calibrated bonuses by checking the delta stays close to 0.15.
    assert delta == pytest.approx(0.15, abs=0.025)
