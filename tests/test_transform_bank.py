"""IBAN/BIC transformer tests."""

from __future__ import annotations

from docomestria.transform.transformers import bic, iban

# A known valid Spanish IBAN (Wikipedia example).
VALID_IBAN = "ES9121000418450200051332"


def test_iban_valid():
    v, c, i = iban(VALID_IBAN)
    assert v == VALID_IBAN
    assert c == 1.0
    assert i == ()


def test_iban_valid_with_spaces():
    spaced = "ES91 2100 0418 4502 0005 1332"
    v, c, _ = iban(spaced)
    assert v == VALID_IBAN
    assert c == 1.0


def test_iban_bad_checksum():
    v, c, i = iban("ES0000000000000000000000")
    assert v == "ES0000000000000000000000"
    assert c == 0.5
    assert "iban_checksum_mismatch" in i


def test_iban_format_invalid():
    v, _, i = iban("ES12 ABC")
    assert v is None
    assert "iban_format_invalid" in i


def test_bic_8_char():
    v, c, _ = bic("BBVAESMM")
    assert v == "BBVAESMM"
    assert c > 0.0


def test_bic_11_char():
    v, c, _ = bic("BBVAESMMXXX")
    assert v == "BBVAESMMXXX"
    assert c > 0.0


def test_bic_format_invalid():
    v, _, i = bic("BAD")
    assert v is None
    assert "bic_format_invalid" in i


def test_iban_empty():
    v, _, i = iban("")
    assert v is None
    assert i == ("empty",)
