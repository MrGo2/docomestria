"""Bank identifiers: IBAN, BIC."""

from __future__ import annotations

import re
import string
from typing import Any

from ..models import TransformContext

try:  # pragma: no cover
    from stdnum import bic as _stdnum_bic  # type: ignore
    from stdnum import iban as _stdnum_iban  # type: ignore

    _HAS_STDNUM = True
except ImportError:  # pragma: no cover
    _stdnum_iban = _stdnum_bic = None  # type: ignore[assignment]
    _HAS_STDNUM = False


_IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$")
_BIC_RE = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")


def _clean(raw: str) -> str:
    return re.sub(r"\s+", "", (raw or "").upper())


def _iban_checksum_ok(iban: str) -> bool:
    rearranged = iban[4:] + iban[:4]
    converted = "".join(
        str(string.ascii_uppercase.index(c) + 10) if c in string.ascii_uppercase else c
        for c in rearranged
    )
    try:
        return int(converted) % 97 == 1
    except ValueError:
        return False


def iban(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Validate an IBAN string."""
    cleaned = _clean(raw)
    if not cleaned:
        return None, 0.0, ("empty",)
    if not _IBAN_RE.match(cleaned):
        return None, 0.0, ("iban_format_invalid",)
    if _HAS_STDNUM:
        try:
            _stdnum_iban.validate(cleaned)  # type: ignore[union-attr]
            return cleaned, 1.0, ()
        except Exception:
            return cleaned, 0.5, ("iban_checksum_mismatch",)
    if _iban_checksum_ok(cleaned):
        return cleaned, 1.0, ()
    return cleaned, 0.5, ("iban_checksum_mismatch",)


iban.name = "iban"  # type: ignore[attr-defined]


def bic(raw: str, *, context: TransformContext | None = None) -> tuple[Any, float, tuple[str, ...]]:
    """Validate a BIC/SWIFT code."""
    cleaned = _clean(raw)
    if not cleaned:
        return None, 0.0, ("empty",)
    if not _BIC_RE.match(cleaned):
        return None, 0.0, ("bic_format_invalid",)
    if _HAS_STDNUM:
        try:
            _stdnum_bic.validate(cleaned)  # type: ignore[union-attr]
            return cleaned, 1.0, ()
        except Exception:
            return cleaned, 0.7, ("bic_validation_warning",)
    return cleaned, 0.9, ()


bic.name = "bic"  # type: ignore[attr-defined]
