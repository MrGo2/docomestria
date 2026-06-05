"""Spanish/EU date transformers.

All transformers return `(date|datetime|None, confidence, issues)`.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from ..models import TransformContext

# Month names — Spanish
_ES_MONTHS = {
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
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}

_DATE_NUM_RE = re.compile(r"^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\s*$")
_DATE_LONG_RE = re.compile(
    r"^\s*(\d{1,2})\s+(?:de\s+)?([A-Za-zÀ-ÿ]+)(?:\s+(?:de|del)\s+(\d{2,4}))?\s*$",
    re.IGNORECASE,
)
_ISO_RE = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")
_ISO_DT_RE = re.compile(
    r"^\s*(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})?\s*$",
)


def _expand_year(y: int) -> int:
    if y >= 100:
        return y
    # 00-29 → 2000-2029, 30-99 → 1930-1999 (typical ES form heuristic)
    return 2000 + y if y < 30 else 1900 + y


def _try_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def date_es(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse a Spanish date in numeric (dd/mm/yy) or long (dd de mes [de yyyy]) form."""
    text = (raw or "").strip()
    if not text:
        return None, 0.0, ("empty",)
    m = _DATE_NUM_RE.match(text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        parsed = _try_date(_expand_year(y), mo, d)
        if parsed is None:
            return None, 0.0, ("invalid_date",)
        return parsed, 1.0, ()
    m = _DATE_LONG_RE.match(text)
    if m:
        d = int(m.group(1))
        mon_name = m.group(2).lower()
        mo = _ES_MONTHS.get(mon_name)
        if mo is None:
            return None, 0.0, ("unknown_month",)
        y_raw = m.group(3)
        if y_raw is None:
            today = date.today()
            parsed = _try_date(today.year, mo, d)
            if parsed is None:
                return None, 0.0, ("invalid_date",)
            return parsed, 0.7, ("year_inferred",)
        y = int(y_raw)
        parsed = _try_date(_expand_year(y), mo, d)
        if parsed is None:
            return None, 0.0, ("invalid_date",)
        return parsed, 1.0, ()
    return None, 0.0, ("format_unrecognized",)


date_es.name = "date_es"  # type: ignore[attr-defined]


def date_es_short(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse strictly numeric Spanish dates (dd/mm/yy or dd/mm/yyyy)."""
    text = (raw or "").strip()
    if not text:
        return None, 0.0, ("empty",)
    m = _DATE_NUM_RE.match(text)
    if not m:
        return None, 0.0, ("format_unrecognized",)
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    parsed = _try_date(_expand_year(y), mo, d)
    if parsed is None:
        return None, 0.0, ("invalid_date",)
    return parsed, 1.0, ()


date_es_short.name = "date_es_short"  # type: ignore[attr-defined]


def date_es_long(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse Spanish long-form dates (e.g. '06 de Diciembre' or '6 de diciembre de 2025')."""
    text = (raw or "").strip()
    if not text:
        return None, 0.0, ("empty",)
    m = _DATE_LONG_RE.match(text)
    if not m:
        return None, 0.0, ("format_unrecognized",)
    d = int(m.group(1))
    mon_name = m.group(2).lower()
    mo = _ES_MONTHS.get(mon_name)
    if mo is None:
        return None, 0.0, ("unknown_month",)
    y_raw = m.group(3)
    if y_raw is None:
        today = date.today()
        parsed = _try_date(today.year, mo, d)
        if parsed is None:
            return None, 0.0, ("invalid_date",)
        return parsed, 0.7, ("year_inferred",)
    parsed = _try_date(_expand_year(int(y_raw)), mo, d)
    if parsed is None:
        return None, 0.0, ("invalid_date",)
    return parsed, 1.0, ()


date_es_long.name = "date_es_long"  # type: ignore[attr-defined]


def date_iso(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse an ISO date (YYYY-MM-DD)."""
    text = (raw or "").strip()
    if not text:
        return None, 0.0, ("empty",)
    m = _ISO_RE.match(text)
    if not m:
        return None, 0.0, ("format_unrecognized",)
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    parsed = _try_date(y, mo, d)
    if parsed is None:
        return None, 0.0, ("invalid_date",)
    return parsed, 1.0, ()


date_iso.name = "date_iso"  # type: ignore[attr-defined]


def datetime_iso(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse an ISO 8601 datetime."""
    text = (raw or "").strip()
    if not text:
        return None, 0.0, ("empty",)
    m = _ISO_DT_RE.match(text)
    if not m:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")), 1.0, ()
        except ValueError:
            return None, 0.0, ("format_unrecognized",)
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mm = int(m.group(4)), int(m.group(5))
    ss = int(m.group(6)) if m.group(6) else 0
    try:
        return datetime(y, mo, d, hh, mm, ss), 1.0, ()
    except ValueError:
        return None, 0.0, ("invalid_datetime",)


datetime_iso.name = "datetime_iso"  # type: ignore[attr-defined]
