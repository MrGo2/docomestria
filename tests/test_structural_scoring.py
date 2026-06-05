"""Structural pair scoring and dedup regression tests."""

from __future__ import annotations

from docomestria.models import BBox
from docomestria.structural import PairCandidate, resolve_pairs


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
