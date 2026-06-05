"""Amount transformer tests."""

from __future__ import annotations

from decimal import Decimal

from docomestria.transform.transformers import (
    Money,
    amount_auto,
    amount_currency,
    amount_eu,
    amount_eur,
    amount_us,
    amount_usd,
)


def test_amount_eu_with_euro_symbol():
    v, c, i = amount_eu("1.234,56 €")
    assert isinstance(v, Money)
    assert v.amount == Decimal("1234.56")
    assert v.currency == "EUR"
    assert i == ()
    assert c == 1.0


def test_amount_eu_without_currency_is_ambiguous():
    v, _, i = amount_eu("1.234,56")
    assert v.amount == Decimal("1234.56")
    assert v.currency is None
    assert "currency_ambiguous" in i


def test_amount_us_with_dollar():
    v, c, _ = amount_us("$1,234.56")
    assert v.amount == Decimal("1234.56")
    assert v.currency == "USD"
    assert c == 1.0


def test_amount_eur_forces_currency():
    v, _, _ = amount_eur("1.234,56")
    assert v.currency == "EUR"


def test_amount_usd_forces_currency():
    v, _, _ = amount_usd("1,234.56")
    assert v.currency == "USD"


def test_amount_currency_parametric():
    fn = amount_currency("GBP")
    v, _, _ = fn("1,234.56")
    assert v.currency == "GBP"


def test_amount_auto_eu():
    v, _, _ = amount_auto("1.234,56 €")
    assert v.amount == Decimal("1234.56")
    assert v.currency == "EUR"


def test_amount_auto_us():
    v, _, _ = amount_auto("1,234.56 USD")
    assert v.amount == Decimal("1234.56")
    assert v.currency == "USD"


def test_amount_unparseable():
    v, c, i = amount_eu("not a number")
    assert v is None
    assert c == 0.0
    assert "amount_unparseable" in i


def test_money_str():
    m = Money(amount=Decimal("100.00"), currency="EUR")
    assert "EUR" in str(m)


def test_money_str_ambiguous():
    m = Money(amount=Decimal("100"), currency=None)
    assert str(m) == "100"
