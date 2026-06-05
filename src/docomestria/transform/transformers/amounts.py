"""Monetary amount transformers — EU and US conventions, with currency."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from ..models import TransformContext


@dataclass(frozen=True)
class Money:
    """A monetary amount with an optional ISO 4217 currency code."""

    amount: Decimal
    currency: str | None  # "EUR" | "USD" | "GBP" | None when ambiguous

    def __str__(self) -> str:
        if self.currency:
            return f"{self.amount} {self.currency}"
        return str(self.amount)


_CURRENCY_SYMBOL = {
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
    "¥": "JPY",
}

_CURRENCY_CODE_RE = re.compile(r"\b(EUR|USD|GBP|JPY|CHF|CAD|AUD)\b", re.IGNORECASE)


def _strip_currency(text: str) -> tuple[str, str | None]:
    """Strip currency symbols/codes from `text`. Returns (clean, currency|None)."""
    text = text.strip()
    currency: str | None = None
    for sym, code in _CURRENCY_SYMBOL.items():
        if sym in text:
            currency = code
            text = text.replace(sym, "")
            break
    m = _CURRENCY_CODE_RE.search(text)
    if m:
        currency = m.group(1).upper()
        text = _CURRENCY_CODE_RE.sub("", text)
    return text.strip(), currency


def _parse_eu_number(text: str) -> Decimal | None:
    """EU convention: '.' as thousands sep, ',' as decimal sep."""
    text = text.replace(" ", "").replace(" ", "")
    if not text:
        return None
    # Allow trailing currency residue
    # Convert: drop '.', replace ',' with '.'
    cleaned = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_us_number(text: str) -> Decimal | None:
    """US convention: ',' as thousands sep, '.' as decimal sep."""
    text = text.replace(" ", "").replace(" ", "")
    cleaned = text.replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def amount_eu(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse an EU-format amount. Returns Money with detected currency (or None)."""
    if not raw or not raw.strip():
        return None, 0.0, ("empty",)
    body, currency = _strip_currency(raw)
    val = _parse_eu_number(body)
    if val is None:
        return None, 0.0, ("amount_unparseable",)
    issues: tuple[str, ...] = ()
    if currency is None:
        issues = ("currency_ambiguous",)
    return Money(amount=val, currency=currency), 1.0 if currency else 0.7, issues


amount_eu.name = "amount_eu"  # type: ignore[attr-defined]


def amount_us(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse a US-format amount."""
    if not raw or not raw.strip():
        return None, 0.0, ("empty",)
    body, currency = _strip_currency(raw)
    val = _parse_us_number(body)
    if val is None:
        return None, 0.0, ("amount_unparseable",)
    issues: tuple[str, ...] = ()
    if currency is None:
        issues = ("currency_ambiguous",)
    return Money(amount=val, currency=currency), 1.0 if currency else 0.7, issues


amount_us.name = "amount_us"  # type: ignore[attr-defined]


def amount_eur(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse EU-format and force currency to EUR."""
    if not raw or not raw.strip():
        return None, 0.0, ("empty",)
    body, _ = _strip_currency(raw)
    val = _parse_eu_number(body)
    if val is None:
        return None, 0.0, ("amount_unparseable",)
    return Money(amount=val, currency="EUR"), 1.0, ()


amount_eur.name = "amount_eur"  # type: ignore[attr-defined]


def amount_usd(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse US-format and force currency to USD."""
    if not raw or not raw.strip():
        return None, 0.0, ("empty",)
    body, _ = _strip_currency(raw)
    val = _parse_us_number(body)
    if val is None:
        return None, 0.0, ("amount_unparseable",)
    return Money(amount=val, currency="USD"), 1.0, ()


amount_usd.name = "amount_usd"  # type: ignore[attr-defined]


def amount_currency(currency: str) -> Any:
    """Parameterised: parse amount, force a specific currency code."""

    def _tr(
        raw: str, *, context: TransformContext | None = None
    ) -> tuple[Any, float, tuple[str, ...]]:
        if not raw or not raw.strip():
            return None, 0.0, ("empty",)
        body, _ = _strip_currency(raw)
        val = _parse_eu_number(body) if currency.upper() == "EUR" else _parse_us_number(body)
        if val is None:
            val = _parse_us_number(body) if currency.upper() == "EUR" else _parse_eu_number(body)
        if val is None:
            return None, 0.0, ("amount_unparseable",)
        return Money(amount=val, currency=currency.upper()), 1.0, ()

    _tr.name = f"amount_currency({currency!r})"  # type: ignore[attr-defined]
    return _tr


def amount_auto(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Auto-detect EU vs US by separator pattern, then parse."""
    if not raw or not raw.strip():
        return None, 0.0, ("empty",)
    body, currency = _strip_currency(raw)
    # Heuristic: if last separator is ',' → EU; if '.' → US; if only one
    # separator and 3-digit group → thousands; else decimal.
    last_comma = body.rfind(",")
    last_dot = body.rfind(".")
    val: Decimal | None
    if last_comma > last_dot:
        val = _parse_eu_number(body)
    elif last_dot > last_comma:
        val = _parse_us_number(body)
    else:
        try:
            val = Decimal(body.replace(" ", ""))
        except InvalidOperation:
            val = None
    if val is None:
        return None, 0.0, ("amount_unparseable",)
    issues: tuple[str, ...] = ()
    if currency is None:
        issues = ("currency_ambiguous",)
    return Money(amount=val, currency=currency), 1.0 if currency else 0.7, issues


amount_auto.name = "amount_auto"  # type: ignore[attr-defined]
