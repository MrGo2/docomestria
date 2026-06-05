"""Spanish national identifiers: NIF, NIE, CIF.

Uses `python-stdnum` when available for checksum validation. Falls back to
hand-rolled validation so the package still works if stdnum is missing.
"""

from __future__ import annotations

import re
from typing import Any

from ..models import TransformContext

try:  # pragma: no cover
    from stdnum.es import cif as _stdnum_cif
    from stdnum.es import nie as _stdnum_nie
    from stdnum.es import nif as _stdnum_nif

    _HAS_STDNUM = True
except ImportError:  # pragma: no cover
    _stdnum_nif = _stdnum_nie = _stdnum_cif = None  # type: ignore[assignment]
    _HAS_STDNUM = False


_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

_NIF_RE = re.compile(r"^[0-9]{8}[A-Z]$")
_NIE_RE = re.compile(r"^[XYZ][0-9]{7}[A-Z]$")
_CIF_RE = re.compile(r"^[ABCDEFGHJKLMNPQRSUVW][0-9]{7}[0-9A-J]$")


def _clean(raw: str) -> str:
    return re.sub(r"[\s\-./]", "", (raw or "").upper())


def _nif_letter(num: int) -> str:
    return _NIF_LETTERS[num % 23]


def nif_es(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Validate a Spanish NIF (DNI for natural persons)."""
    cleaned = _clean(raw)
    if not cleaned:
        return None, 0.0, ("empty",)
    if not _NIF_RE.match(cleaned):
        return None, 0.0, ("nif_format_invalid",)
    if _HAS_STDNUM:
        try:
            _stdnum_nif.validate(cleaned)  # type: ignore[union-attr]
            return cleaned, 1.0, ()
        except Exception:
            return cleaned, 0.5, ("nif_checksum_mismatch",)
    expected = _nif_letter(int(cleaned[:8]))
    if expected != cleaned[8]:
        return cleaned, 0.5, ("nif_checksum_mismatch",)
    return cleaned, 1.0, ()


nif_es.name = "nif_es"  # type: ignore[attr-defined]


def nie_es(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Validate a Spanish NIE (foreigner ID)."""
    cleaned = _clean(raw)
    if not cleaned:
        return None, 0.0, ("empty",)
    if not _NIE_RE.match(cleaned):
        return None, 0.0, ("nie_format_invalid",)
    if _HAS_STDNUM:
        try:
            _stdnum_nie.validate(cleaned)  # type: ignore[union-attr]
            return cleaned, 1.0, ()
        except Exception:
            return cleaned, 0.5, ("nie_checksum_mismatch",)
    prefix_map = {"X": "0", "Y": "1", "Z": "2"}
    num = int(prefix_map[cleaned[0]] + cleaned[1:8])
    expected = _nif_letter(num)
    if expected != cleaned[8]:
        return cleaned, 0.5, ("nie_checksum_mismatch",)
    return cleaned, 1.0, ()


nie_es.name = "nie_es"  # type: ignore[attr-defined]


def cif_es(
    raw: str, *, context: TransformContext | None = None
) -> tuple[Any, float, tuple[str, ...]]:
    """Validate a Spanish CIF (company tax ID)."""
    cleaned = _clean(raw)
    if not cleaned:
        return None, 0.0, ("empty",)
    if not _CIF_RE.match(cleaned):
        return None, 0.0, ("cif_format_invalid",)
    if _HAS_STDNUM:
        try:
            _stdnum_cif.validate(cleaned)  # type: ignore[union-attr]
            return cleaned, 1.0, ()
        except Exception:
            return cleaned, 0.5, ("cif_checksum_mismatch",)
    # Lightweight fallback: accept format-valid CIFs (issues still empty).
    return cleaned, 0.8, ()


cif_es.name = "cif_es"  # type: ignore[attr-defined]
