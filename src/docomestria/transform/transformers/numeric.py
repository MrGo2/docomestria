"""Numeric transformers: integer, decimal, percentage."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from ..models import TransformContext

_INT_RE = re.compile(r"^-?\d+$")


def _to_decimal(text: str) -> Decimal | None:
    last_comma = text.rfind(",")
    last_dot = text.rfind(".")
    if last_comma > last_dot:
        cleaned = text.replace(".", "").replace(",", ".")
    elif last_dot > last_comma:
        cleaned = text.replace(",", "")
    else:
        cleaned = text
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def integer(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Strict integer parsing — no separators allowed."""
    text = (raw or "").strip()
    if not text:
        return None, 0.0, ("empty",)
    cleaned = text.replace(" ", "").replace(".", "").replace(",", "")
    if not _INT_RE.match(cleaned):
        return None, 0.0, ("integer_format_invalid",)
    return int(cleaned), 1.0, ()


integer.name = "integer"  # type: ignore[attr-defined]


def decimal(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Locale-aware decimal parsing (EU or US)."""
    text = (raw or "").strip().replace(" ", "")
    if not text:
        return None, 0.0, ("empty",)
    val = _to_decimal(text)
    if val is None:
        return None, 0.0, ("decimal_format_invalid",)
    return val, 1.0, ()


decimal.name = "decimal"  # type: ignore[attr-defined]


def percentage(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Parse a percentage. Returns the raw number (e.g. 25.5 for '25,5 %')."""
    text = (raw or "").strip().replace("%", "").replace(" ", "")
    if not text:
        return None, 0.0, ("empty",)
    val = _to_decimal(text)
    if val is None:
        return None, 0.0, ("percentage_format_invalid",)
    return val, 1.0, ()


percentage.name = "percentage"  # type: ignore[attr-defined]
