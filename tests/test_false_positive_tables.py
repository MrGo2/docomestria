"""Unit tests for `_is_false_positive_plumber_table` in structure.py.

Covers the suppression of pdfplumber-only false positives (prose boxes and
signature furniture) while ensuring genuine fused/docling tables and real
pdfplumber-only 2-col tables survive.
"""

from __future__ import annotations

from docomestria.models import BBox
from docomestria.structural.structure import (
    _is_false_positive_plumber_table,
    _TableLike,
)

_BB = BBox(x=10.0, y=10.0, w=200.0, h=200.0)


def _tl(cells, source="pdfplumber"):
    return _TableLike(bbox=_BB, page=1, rect_id="r", cells=cells, source=source)


def test_one_column_prose_box_suppressed():
    cells = (
        ("long clause text describing the policy in detail",),
        ("more explanatory prose that runs on across the box",),
        ("a final sentence closing the clause text region",),
    )
    assert _is_false_positive_plumber_table(_tl(cells)) is True


def test_firmatag_block_suppressed():
    cells = (
        ("Firma del titular", "@$FIRMATAG_01"),
        ("Lugar y fecha", "Madrid"),
    )
    assert _is_false_positive_plumber_table(_tl(cells)) is True


def test_high_empty_ratio_two_col_suppressed():
    # 3x2 = 6 cells, 4 blank -> empty_ratio = 0.666 >= 0.45
    cells = (
        ("Label", ""),
        ("", ""),
        ("", "Value"),
    )
    assert _is_false_positive_plumber_table(_tl(cells)) is True


def test_genuine_fused_table_survives():
    # 14x2, ~0.11 empty ratio; returns False immediately on source check.
    rows = tuple((f"k{i}", f"v{i}") for i in range(14))
    # blank a couple of value cells to land near 0.11 empty ratio
    rows = (("k0", ""), ("k1", ""), *rows[2:])
    cells = rows
    assert _is_false_positive_plumber_table(_tl(cells, source="fused")) is False


def test_genuine_docling_table_survives():
    cells = tuple(tuple(f"c{r}_{c}" for c in range(6)) for r in range(38))
    assert _is_false_positive_plumber_table(_tl(cells, source="docling")) is False


def test_real_pdfplumber_two_col_not_oversuppressed():
    # cols > 1, empty_ratio < 0.45, no FIRMATAG -> must survive.
    cells = (
        ("Nombre", "Juan Perez"),
        ("DNI", "12345678Z"),
        ("Importe", "1.000,00"),
        ("Fecha", "01/01/2026"),
    )
    assert _is_false_positive_plumber_table(_tl(cells)) is False


def test_empty_cells_container_no_crash():
    assert _is_false_positive_plumber_table(_tl(None)) is False
    assert _is_false_positive_plumber_table(_tl(())) is False
