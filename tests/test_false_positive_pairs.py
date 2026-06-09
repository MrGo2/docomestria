"""Unit tests for `_is_false_positive_pair` in extractor.py.

Covers suppression of three junk-pair classes seen in real output
(`16815699P_CONTRATO.pdf`) while ensuring genuine pairs survive:

  A. control-char value/label   (e.g. ``\\x9f (*) Comisión Estudio``)
  B. vertical-margin sliver      (rotated form metadata: ``Date``/``Guid``)
  C. header-on-header glue        (``No Financiadas → Comisión apertura``) — gated
"""

from __future__ import annotations

from docomestria.models import BBox
from docomestria.structural.extractor import (
    _has_control_chars,
    _is_false_positive_pair,
    _is_header_glue,
    _is_vertical_sliver,
)
from docomestria.structural.models import Confidence, Pair

# A normal horizontal text line: wide and short (w >> h).
_H = BBox(x=40.0, y=590.0, w=70.0, h=11.0)
# A rotated margin sliver: narrow and tall (h >> w).
_V = BBox(x=582.0, y=498.0, w=1.4, h=24.0)


def _pair(
    label,
    value,
    *,
    lbbox=_H,
    vbbox=_H,
    evidence=("L-horizontal",),
    score=0.86,
    confidence=Confidence.HIGH,
    column_index=None,
):
    return Pair(
        label_text=label,
        value_text=value,
        label_bbox=lbbox,
        value_bbox=vbbox,
        page=1,
        score=score,
        confidence=confidence,
        evidence=evidence,
        column_index=column_index,
    )


# --- Discriminator A: control characters -----------------------------------


def test_control_char_in_value_killed():
    assert _has_control_chars("\x9f (*) Comisión Estudio") is True
    p = _pair("No Financiadas: Comisión apertura", "\x9f (*) Comisión Estudio")
    assert _is_false_positive_pair(p) is True


def test_control_char_in_label_killed():
    assert _has_control_chars("Importe\x07") is True
    assert _is_false_positive_pair(_pair("Importe\x07", "1.000,00")) is True


def test_euro_and_tabs_are_not_control_chars():
    # € (U+20AC) and ordinary whitespace (\t\n\r) must NOT count as control.
    assert _has_control_chars("273,23€") is False
    assert _has_control_chars("line1\n\tline2") is False


# --- Discriminator B: vertical-margin sliver -------------------------------


def test_vertical_sliver_value_killed():
    assert _is_vertical_sliver("2024/05/09", _V) is True
    p = _pair("Date", "2024/05/09", lbbox=_V, vbbox=_V)
    assert _is_false_positive_pair(p) is True


def test_vertical_sliver_label_killed():
    # Guid metadata stamp — the label side is also a sliver.
    p = _pair("Guid", "001001-0001-000000124609130.par", lbbox=_V, vbbox=_V)
    assert _is_false_positive_pair(p) is True


def test_horizontal_amount_not_a_sliver():
    wide = BBox(x=25.0, y=242.0, w=130.0, h=11.0)
    assert _is_vertical_sliver("273,23€", wide) is False
    # A genuine Docling amortization row must survive.
    p = _pair("05-06-2024", "273,23€", lbbox=wide, vbbox=wide, evidence=("D-2col",))
    assert _is_false_positive_pair(p) is False


def test_single_char_sliver_not_killed():
    # Too short to judge orientation reliably; do not suppress.
    assert _is_vertical_sliver("A", _V) is False


def test_zero_width_bbox_no_crash():
    assert _is_vertical_sliver("text", BBox(x=0.0, y=0.0, w=0.0, h=10.0)) is False


# --- Discriminator C: header-on-header glue (gated) -------------------------


def test_header_glue_killed():
    assert _is_header_glue("No Financiadas", "Comisión apertura") is True
    p = _pair("No Financiadas", "Comisión apertura", evidence=("L-inline-split",))
    assert _is_false_positive_pair(p) is True


def test_all_caps_value_survives():
    # `Lugar → LAS PALMAS` — a genuine form field; value is all-caps, not a
    # Title-Case header phrase.
    assert _is_header_glue("Lugar", "LAS PALMAS") is False
    p = _pair("Lugar", "LAS PALMAS", evidence=("L-inline-split",))
    assert _is_false_positive_pair(p) is False


def test_typed_value_survives():
    # `05-06-2024 → 273,23€` — value coerces to an amount (kind != "string").
    assert _is_header_glue("05-06-2024", "273,23€") is False


def test_terminal_punctuation_survives():
    # A sentence-like value is not a header phrase.
    assert _is_header_glue("Donde", "IT =Intereses totales de la operación.") is False


def test_single_word_title_value_survives():
    # One Title-Case word (e.g. a city) is not multi-word header glue.
    assert _is_header_glue("Provincia", "Madrid") is False


def test_header_glue_only_for_single_rule_evidence():
    # Cross-engine agreement (2+ rules) means the pair is corroborated; the
    # gated C discriminator must not touch it even if the text looks header-like.
    p = _pair(
        "No Financiadas",
        "Comisión apertura",
        evidence=("L-inline-split", "D-2col"),
    )
    assert _is_false_positive_pair(p) is False


# --- Genuine pairs survive end-to-end --------------------------------------


def test_plain_genuine_pair_survives():
    assert _is_false_positive_pair(_pair("Nombre", "Juan Pérez")) is False


def test_empty_value_pair_no_crash():
    assert _is_false_positive_pair(_pair("Casilla", "")) is False
