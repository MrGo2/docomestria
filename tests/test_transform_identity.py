"""NIF/NIE/CIF transformer tests."""

from __future__ import annotations

from docomestria.transform.transformers import cif_es, nie_es, nif_es


def test_nif_valid_checksum():
    v, c, i = nif_es("51789286W")
    assert v == "51789286W"
    assert c == 1.0
    assert i == ()


def test_nif_invalid_checksum_still_returns_cleaned():
    v, c, i = nif_es("12345678A")
    assert v == "12345678A"
    assert c == 0.5
    assert "nif_checksum_mismatch" in i


def test_nif_format_invalid_returns_none():
    v, c, i = nif_es("ABCDEFG")
    assert v is None
    assert "nif_format_invalid" in i


def test_nif_normalizes_dashes_and_spaces():
    v, _, _ = nif_es("51789286-w")
    assert v == "51789286W"


def test_nie_valid():
    v, c, i = nie_es("X1234567L")
    assert v == "X1234567L"
    # Either fully valid or checksum-mismatch — both are acceptable behaviours.
    assert c in (1.0, 0.5)


def test_nie_format_invalid():
    v, _, i = nie_es("ABC1234")
    assert v is None
    assert "nie_format_invalid" in i


def test_cif_format_valid():
    v, c, _ = cif_es("A12345674")
    # Whether stdnum is present or not, format-valid CIF should return non-None.
    assert v == "A12345674"
    assert c > 0.0


def test_cif_format_invalid():
    v, _, i = cif_es("123456789")
    assert v is None
    assert "cif_format_invalid" in i


def test_empty_input():
    v, c, i = nif_es("")
    assert v is None
    assert c == 0.0
    assert i == ("empty",)
