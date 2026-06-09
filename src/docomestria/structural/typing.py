"""Capa 3.7 — value typing.

Post-extraction transform that coerces a raw string value into a typed
representation. Each typer is a pure function that returns either a
``TypedValue`` (on match) or ``None`` (no match). ``coerce_value`` tries
the typers in order and falls back to ``kind='string'``.

This module is intentionally LLM-free and dependency-free — all rules are
expressed as regex + small validators (Spanish NIF check letter, month
name lookup, etc.).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any

__all__ = [
    "TypedValue",
    "coerce_value",
    "try_amount",
    "try_bool",
    "try_date",
    "try_nif",
    "try_percent",
]


@dataclass(frozen=True)
class TypedValue:
    """A typed coercion of a raw string value.

    ``raw`` is the original input. ``kind`` names the typer that matched
    (``date`` | ``amount`` | ``percent`` | ``nif`` | ``bool`` | ``string``).
    ``value`` is the typed payload: ``date`` for dates, a ``{amount, currency}``
    dict for amounts, ``float`` for percents (already in decimal form,
    e.g. ``0.0525`` for ``5,25%``), ``str`` (canonicalised) for NIF/CIF/NIE,
    ``bool`` for booleans, and the original string for the fallback.

    ``confidence`` is in ``[0, 1]`` — how sure the typer is. Strong signals
    (full date with year, well-formed amount with euro symbol, valid NIF
    check letter) score ``>= 0.9``; weaker matches (year-less date, bare
    integer percent) sit around ``0.7``.
    """

    raw: str
    kind: str
    value: Any
    confidence: float


# ---------------------------------------------------------------------------
# Date typer
# ---------------------------------------------------------------------------

_DATE_NUMERIC_RE = re.compile(
    r"""
    ^\s*
    (?P<d>\d{1,2})           # day
    [.\-/]
    (?P<m>\d{1,2})           # month
    [.\-/]
    (?P<y>\d{2,4})           # year
    (?:\s+\d{1,2}:\d{2}(?::\d{2})?)?  # optional trailing time
    \s*$
    """,
    re.VERBOSE,
)

_DATE_PROSE_RE = re.compile(
    r"""
    ^\s*
    (?P<d>\d{1,2})
    \s+de\s+
    (?P<month>[A-Za-zÁÉÍÓÚáéíóúñÑ]+)
    \s+de\s+
    (?P<y>\d{4})
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

_SPANISH_MONTHS: dict[str, int] = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _strip_accents(s: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn"
    )


def try_date(raw: str) -> TypedValue | None:
    """Match Spanish-style dates: ``DD.MM.YYYY``, ``DD/MM/YYYY``, ``DD-MM-YYYY``
    and the prose form ``29 de marzo de 2021``. Returns ``None`` on no match
    or an invalid calendar date.
    """
    if not raw:
        return None

    m = _DATE_NUMERIC_RE.match(raw)
    if m:
        day = int(m.group("d"))
        month = int(m.group("m"))
        year_raw = m.group("y")
        year = int(year_raw)
        if len(year_raw) == 2:
            # Two-digit year — assume 2000s for 00-79, 1900s otherwise.
            year = 2000 + year if year < 80 else 1900 + year
        try:
            value = date(year, month, day)
        except ValueError:
            return None
        # Slightly lower confidence on 2-digit years since they're ambiguous.
        conf = 0.95 if len(year_raw) == 4 else 0.75
        return TypedValue(raw=raw, kind="date", value=value, confidence=conf)

    m = _DATE_PROSE_RE.match(raw)
    if m:
        month_name = _strip_accents(m.group("month")).lower()
        month = _SPANISH_MONTHS.get(month_name)
        if month is None:
            return None
        try:
            value = date(int(m.group("y")), month, int(m.group("d")))
        except ValueError:
            return None
        return TypedValue(raw=raw, kind="date", value=value, confidence=0.95)

    return None


# ---------------------------------------------------------------------------
# Amount typer (Spanish format: thousands `.`, decimals `,`)
# ---------------------------------------------------------------------------

_AMOUNT_RE = re.compile(
    r"""
    ^\s*
    (?P<sign>-)?                         # optional sign
    (?P<int>\d{1,3}(?:\.\d{3})+|\d+)     # thousands-grouped OR plain integer
    ,(?P<dec>\d{2})                       # mandatory ,DD decimals
    \s*
    (?P<cur>€|EUR|eur)?
    \s*$
    """,
    re.VERBOSE,
)


def try_amount(raw: str) -> TypedValue | None:
    """Match Spanish currency amounts: ``1.234,56``, ``1.234,56 €``, ``-50,00 EUR``.

    Decimal comma is mandatory (an integer with no decimals is not coerced as
    an amount — it would collide with bare integer IDs). Currency defaults
    to EUR even when no symbol is present.
    """
    if not raw:
        return None

    m = _AMOUNT_RE.match(raw)
    if not m:
        return None

    int_part = m.group("int").replace(".", "")
    dec_part = m.group("dec")
    sign = m.group("sign") or ""
    amount = float(f"{sign}{int_part}.{dec_part}")

    has_symbol = m.group("cur") is not None
    # Symbol → very confident this is money. No symbol → still likely money
    # but slightly weaker (could be a measurement, a coefficient, etc.).
    conf = 0.95 if has_symbol else 0.8

    return TypedValue(
        raw=raw,
        kind="amount",
        value={"amount": amount, "currency": "EUR"},
        confidence=conf,
    )


# ---------------------------------------------------------------------------
# Percent typer
# ---------------------------------------------------------------------------

_PERCENT_RE = re.compile(
    r"""
    ^\s*
    (?P<sign>-)?
    (?P<num>\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:\.\d+)?)
    \s*%
    \s*$
    """,
    re.VERBOSE,
)


def try_percent(raw: str) -> TypedValue | None:
    """Match percent strings: ``5%``, ``5,25%``, ``12.6020%``, ``-1,5 %``.

    Returns the value as a decimal fraction (``5,25%`` -> ``0.0525``).
    Accepts both Spanish (``,`` decimal) and English (``.`` decimal) styles
    so values like ``12.6020%`` (already-dotted) coerce cleanly.
    """
    if not raw:
        return None

    m = _PERCENT_RE.match(raw)
    if not m:
        return None

    raw_num = m.group("num")
    # Spanish format detection: presence of a comma means it's the decimal
    # separator (so dots become thousands separators).
    if "," in raw_num:
        normalised = raw_num.replace(".", "").replace(",", ".")
    else:
        normalised = raw_num
    sign = m.group("sign") or ""

    try:
        pct = float(f"{sign}{normalised}")
    except ValueError:
        return None

    return TypedValue(raw=raw, kind="percent", value=pct / 100.0, confidence=0.95)


# ---------------------------------------------------------------------------
# NIF / CIF / NIE typer
# ---------------------------------------------------------------------------

_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_PREFIX = {"X": "0", "Y": "1", "Z": "2"}
# Matches DNI (8d+L), NIE (X/Y/Z + 7d + L), or CIF (L + 7d + L|d).
_NIF_RE = re.compile(r"^\s*(?P<id>[A-Z]?\d{7,8}[A-Z0-9])\s*$", re.IGNORECASE)
# CIF: leading letter (org type), 7 digits, control char (digit or letter).
_CIF_LEADING = set("ABCDEFGHJNPQRSUVW")


def _nif_check_letter(number: int) -> str:
    return _NIF_LETTERS[number % 23]


def _validate_cif(cif: str) -> bool:
    """Spanish CIF control: weighted sum of digits, last char = digit or letter."""
    if len(cif) != 9:
        return False
    leading = cif[0]
    digits = cif[1:8]
    control = cif[8]
    if leading not in _CIF_LEADING or not digits.isdigit():
        return False

    total = 0
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == 0:  # odd positions (1-indexed): doubled
            doubled = d * 2
            total += doubled // 10 + doubled % 10
        else:
            total += d
    check_digit = (10 - (total % 10)) % 10
    check_letter = "JABCDEFGHI"[check_digit]

    # Organisations in {A,B,E,H} must use the digit form; {K,P,Q,S} the letter
    # form; others accept either. We accept either for simplicity.
    return control == str(check_digit) or control.upper() == check_letter


def try_nif(raw: str) -> TypedValue | None:
    """Match a Spanish NIF (DNI), NIE (X/Y/Z prefix), or CIF (org tax id).

    Validates the check character using the official algorithms. Returns
    ``None`` for partial strings or invalid check characters.
    """
    if not raw:
        return None

    m = _NIF_RE.match(raw)
    if not m:
        return None

    ident = m.group("id").upper()

    # NIE: prefix X/Y/Z + 7 digits + letter
    if ident[0] in _NIE_PREFIX and len(ident) == 9:
        body = _NIE_PREFIX[ident[0]] + ident[1:8]
        if not body.isdigit():
            return None
        expected = _nif_check_letter(int(body))
        if expected == ident[-1]:
            return TypedValue(raw=raw, kind="nif", value=ident, confidence=0.98)
        return None

    # CIF: leading letter (not X/Y/Z handled above) + 7 digits + check char
    if ident[0].isalpha() and len(ident) == 9:
        if _validate_cif(ident):
            return TypedValue(raw=raw, kind="nif", value=ident, confidence=0.95)
        return None

    # DNI: 7-8 digits + letter
    if ident[:-1].isdigit() and len(ident) in (8, 9):
        body = ident[:-1]
        expected = _nif_check_letter(int(body))
        if expected == ident[-1]:
            return TypedValue(raw=raw, kind="nif", value=ident, confidence=0.98)
        return None

    return None


# ---------------------------------------------------------------------------
# Boolean typer
# ---------------------------------------------------------------------------

_BOOL_TRUE = {"si", "sí", "yes", "true", "verdadero", "1", "x", "✓"}
_BOOL_FALSE = {"no", "false", "falso", "0"}


def try_bool(raw: str) -> TypedValue | None:
    """Match yes/no style values (Sí, No, Yes, True, 0, 1, ...).

    Case-insensitive. Bare ``0``/``1`` only coerce as bool when no other typer
    has claimed them — ``coerce_value`` runs amount/percent/date first so a
    plain ``1`` only ends up here. Returns ``None`` for empty strings to keep
    blank cells out of the boolean lane.
    """
    if not raw:
        return None
    key = raw.strip().lower()
    if not key:
        return None
    if key in _BOOL_TRUE:
        return TypedValue(raw=raw, kind="bool", value=True, confidence=0.9)
    if key in _BOOL_FALSE:
        return TypedValue(raw=raw, kind="bool", value=False, confidence=0.9)
    return None


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

# Order matters: amount/percent share a digit prefix but are disambiguated by
# the trailing token (`%` vs `€`/decimals). Date comes first so `01-02-2024`
# never gets misread as an amount/percent. NIF before bool so `1` doesn't get
# claimed as a single-digit identifier.
_TYPERS = (try_date, try_amount, try_percent, try_nif, try_bool)


def coerce_value(raw: str) -> TypedValue:
    """Try each typer in order; first non-None wins. Falls back to ``string``
    when nothing matches, with ``confidence=1.0`` (we are sure it's a string).
    """
    if raw is None:
        raw = ""
    for typer in _TYPERS:
        result = typer(raw)
        if result is not None:
            return result
    return TypedValue(raw=raw, kind="string", value=raw, confidence=1.0)
