"""Date transformer tests."""

from __future__ import annotations

from datetime import date, datetime

from docomestria.transform.transformers import (
    date_es,
    date_es_long,
    date_es_short,
    date_iso,
    datetime_iso,
)


def test_date_es_numeric_short_year():
    v, c, i = date_es("06/12/26")
    assert v == date(2026, 12, 6)
    assert c == 1.0
    assert i == ()


def test_date_es_numeric_long_year():
    v, c, _ = date_es("06/12/2025")
    assert v == date(2025, 12, 6)
    assert c == 1.0


def test_date_es_long_form_with_year():
    v, c, _ = date_es("6 de diciembre de 2025")
    assert v == date(2025, 12, 6)
    assert c == 1.0


def test_date_es_long_form_without_year_infers_current():
    v, c, issues = date_es("06 de Diciembre")
    assert isinstance(v, date)
    assert v.month == 12 and v.day == 6
    assert "year_inferred" in issues
    assert c < 1.0


def test_date_es_invalid_returns_zero_confidence():
    v, c, issues = date_es("30/02/2026")
    assert v is None
    assert c == 0.0
    assert "invalid_date" in issues


def test_date_es_unknown_month():
    v, c, issues = date_es("06 de Foo de 2025")
    assert v is None
    assert "unknown_month" in issues


def test_date_es_short_rejects_long_form():
    v, c, _ = date_es_short("6 de diciembre de 2025")
    assert v is None
    assert c == 0.0


def test_date_es_long_rejects_numeric():
    v, c, _ = date_es_long("06/12/2025")
    assert v is None
    assert c == 0.0


def test_date_iso_ok():
    v, c, _ = date_iso("2026-06-05")
    assert v == date(2026, 6, 5)
    assert c == 1.0


def test_date_iso_rejects_bad_format():
    v, _, _ = date_iso("06/05/2026")
    assert v is None


def test_datetime_iso_with_time():
    v, c, _ = datetime_iso("2026-06-05T10:30:00Z")
    assert isinstance(v, datetime)
    assert c == 1.0


def test_empty_returns_empty_issue():
    v, c, i = date_es("")
    assert v is None
    assert i == ("empty",)
