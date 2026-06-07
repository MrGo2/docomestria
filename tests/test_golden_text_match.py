"""Whitespace-insensitive text matching in the golden builder.

Regression guard for the linker fix: engines fuse a value with its unit or a
neighbouring cell ("7,99%anual" in LiteParse, "Tipo deudor 7,99 %anual" in
Docling), so the spaced golden text ("7,99% anual") must still match.
"""

from __future__ import annotations

from docomestria.golden.engine_data import _contains, _norm


def test_contains_exact_spaced():
    assert _contains(_norm("7,99% anual"), _norm("7,99% anual"))


def test_contains_fused_no_space():
    # LiteParse returns the value glued to its unit + trailing comma.
    assert _contains(_norm("7,99% anual"), _norm("7,99%anual ,"))


def test_contains_fused_with_neighbour():
    # Docling fuses the value into the label block.
    assert _contains(_norm("7,99% anual"), _norm("Variable Tipo deudor 7,99 %anual ,"))


def test_contains_space_before_percent():
    assert _contains(_norm("9,82%"), _norm("TAE/ TAEVariable 9,82 %"))


def test_contains_rejects_unrelated():
    assert not _contains(_norm("7,99% anual"), _norm("Importe Total adeudado"))


def test_contains_empty_target_is_false():
    assert not _contains(_norm(""), _norm("anything"))
