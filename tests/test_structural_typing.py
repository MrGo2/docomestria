"""Tests for capa 3.7 — value typing (typing.py)."""

from __future__ import annotations

from datetime import date

import pytest

from docomestria.structural.typing import (
    TypedValue,
    coerce_value,
    try_amount,
    try_bool,
    try_date,
    try_nif,
    try_percent,
)


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


def test_date_dd_dot_mm_dot_yyyy():
    tv = try_date("29.03.2021")
    assert tv is not None
    assert tv.kind == "date"
    assert tv.value == date(2021, 3, 29)
    assert tv.confidence >= 0.9


def test_date_dd_slash_mm_slash_yyyy():
    tv = try_date("29/03/2021")
    assert tv is not None
    assert tv.value == date(2021, 3, 29)


def test_date_dd_dash_mm_dash_yyyy():
    tv = try_date("29-03-2021")
    assert tv is not None
    assert tv.value == date(2021, 3, 29)


def test_date_spanish_prose():
    tv = try_date("29 de marzo de 2021")
    assert tv is not None
    assert tv.value == date(2021, 3, 29)
    assert tv.confidence >= 0.9


def test_date_spanish_prose_with_accent():
    tv = try_date("3 de septiembre de 1979")
    assert tv is not None
    assert tv.value == date(1979, 9, 3)


def test_date_with_trailing_time():
    tv = try_date("29/03/2021 14:30")
    assert tv is not None
    assert tv.value == date(2021, 3, 29)


def test_date_malformed_returns_none():
    assert try_date("not a date") is None
    assert try_date("32/13/2021") is None  # invalid calendar
    assert try_date("") is None


def test_date_two_digit_year_lower_confidence():
    tv = try_date("29-03-21")
    assert tv is not None
    assert tv.value == date(2021, 3, 29)
    assert tv.confidence < 0.9


# ---------------------------------------------------------------------------
# Amounts
# ---------------------------------------------------------------------------


def test_amount_with_euro_symbol():
    tv = try_amount("1.234,56 €")
    assert tv is not None
    assert tv.kind == "amount"
    assert tv.value == {"amount": 1234.56, "currency": "EUR"}
    assert tv.confidence >= 0.9


def test_amount_without_symbol():
    tv = try_amount("1.234,56")
    assert tv is not None
    assert tv.value == {"amount": 1234.56, "currency": "EUR"}


def test_amount_large_with_thousands():
    tv = try_amount("12.345.678,90 €")
    assert tv is not None
    assert tv.value["amount"] == pytest.approx(12345678.90)


def test_amount_small_no_thousands():
    tv = try_amount("50,00 EUR")
    assert tv is not None
    assert tv.value["amount"] == 50.00


def test_amount_negative():
    tv = try_amount("-1.234,56 €")
    assert tv is not None
    assert tv.value["amount"] == -1234.56


def test_amount_integer_returns_none():
    # No decimals → not an amount (could be an ID).
    assert try_amount("1234") is None


def test_amount_rejects_bad_input():
    assert try_amount("not money") is None
    assert try_amount("") is None


# ---------------------------------------------------------------------------
# Percent
# ---------------------------------------------------------------------------


def test_percent_integer():
    tv = try_percent("5%")
    assert tv is not None
    assert tv.kind == "percent"
    assert tv.value == pytest.approx(0.05)


def test_percent_decimal_spanish():
    tv = try_percent("5,25%")
    assert tv is not None
    assert tv.value == pytest.approx(0.0525)


def test_percent_decimal_english():
    tv = try_percent("12.6020%")
    assert tv is not None
    assert tv.value == pytest.approx(0.126020)


def test_percent_with_space():
    tv = try_percent("12,60 %")
    assert tv is not None
    assert tv.value == pytest.approx(0.1260)


def test_percent_rejects_non_percent():
    assert try_percent("12,60") is None
    assert try_percent("") is None


# ---------------------------------------------------------------------------
# NIF / CIF / NIE
# ---------------------------------------------------------------------------


def test_nif_valid_dni():
    # 12345678Z is the canonical example DNI.
    tv = try_nif("12345678Z")
    assert tv is not None
    assert tv.kind == "nif"
    assert tv.value == "12345678Z"


def test_nif_valid_nie():
    # X6573514E — X→0, then 06573514 % 23 = 4 → 'E'? Let's verify.
    tv = try_nif("X6573514E")
    assert tv is not None
    assert tv.kind == "nif"
    assert tv.value == "X6573514E"


def test_nif_valid_cif():
    # B78640570 is a known-valid CIF (Spanish org id).
    tv = try_nif("B78640570")
    assert tv is not None
    assert tv.kind == "nif"


def test_nif_invalid_letter():
    # Same number, wrong check letter.
    assert try_nif("12345678A") is None


def test_nif_partial_string():
    assert try_nif("1234") is None
    assert try_nif("") is None
    assert try_nif("12345678") is None  # no letter


def test_nif_lowercase_normalised():
    tv = try_nif("12345678z")
    assert tv is not None
    assert tv.value == "12345678Z"


# ---------------------------------------------------------------------------
# Bool
# ---------------------------------------------------------------------------


def test_bool_si_no():
    assert try_bool("Sí").value is True
    assert try_bool("Si").value is True
    assert try_bool("No").value is False


def test_bool_yes_no():
    assert try_bool("Yes").value is True
    assert try_bool("no").value is False


def test_bool_true_false_strings():
    assert try_bool("true").value is True
    assert try_bool("False").value is False


def test_bool_zero_one():
    assert try_bool("1").value is True
    assert try_bool("0").value is False


def test_bool_rejects_arbitrary():
    assert try_bool("maybe") is None
    assert try_bool("") is None
    assert try_bool("   ") is None


# ---------------------------------------------------------------------------
# coerce_value dispatcher
# ---------------------------------------------------------------------------


def test_coerce_value_dispatches_to_date():
    tv = coerce_value("29-03-2021")
    assert tv.kind == "date"
    assert tv.value == date(2021, 3, 29)


def test_coerce_value_dispatches_to_amount():
    tv = coerce_value("1.234,56 €")
    assert tv.kind == "amount"
    assert tv.value == {"amount": 1234.56, "currency": "EUR"}


def test_coerce_value_dispatches_to_percent():
    tv = coerce_value("5,25%")
    assert tv.kind == "percent"
    assert tv.value == pytest.approx(0.0525)


def test_coerce_value_dispatches_to_nif():
    tv = coerce_value("X6573514E")
    assert tv.kind == "nif"
    assert tv.value == "X6573514E"


def test_coerce_value_dispatches_to_bool():
    tv = coerce_value("Sí")
    assert tv.kind == "bool"
    assert tv.value is True


def test_coerce_value_falls_through_to_string():
    tv = coerce_value("Carlos Lorenzo")
    assert tv.kind == "string"
    assert tv.value == "Carlos Lorenzo"
    assert tv.confidence == 1.0


def test_coerce_value_none_safe():
    tv = coerce_value("")
    assert tv.kind == "string"


def test_typed_value_is_frozen():
    tv = TypedValue(raw="x", kind="string", value="x", confidence=1.0)
    with pytest.raises(Exception):
        tv.kind = "amount"  # type: ignore[misc]
