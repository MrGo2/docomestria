"""Detect the document family of a `StructuralExtraction` from its pairs.

Used by `to_json()` and by `schema.canonical_label` to dispatch to a
family-specific label table. The heuristic walks the emitted pair
labels, looking for distinctive markers that appear in one family but
not the others. Pure stdlib — no engine re-runs.

Families covered today:
- LABORAL: judicial labour-court 2-col documents (SS / contracts).
- PATRIMONIAL: judicial multi-page AEAT/registry consultations.
- BANKING: BBVA-style credit-card / loan contract forms.
- UNKNOWN: nothing distinctive found.

New families are added by extending `_MARKERS` and `DocType`.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class DocType(str, Enum):
    LABORAL = "laboral"
    PATRIMONIAL = "patrimonial"
    BANKING = "banking"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DocTypeMatch:
    """Result of detect_doc_type: which family + how sure + why."""

    doc_type: DocType
    confidence: float
    signals: tuple[str, ...]


# Each family is described by:
#   - markers: distinctive label substrings (normalised — lowercase, no accents,
#       no colon, whitespace-collapsed). If 2+ markers hit the family wins.
#   - min_hits: lower bound of marker hits required to claim the type at all.
_MARKERS: dict[DocType, tuple[tuple[str, ...], int]] = {
    DocType.LABORAL: (
        (
            "razon social/convenio/regimen",
            "no seguridad social",
            "situacion actual",
            "fecha alta",
            "tipo contrato",
            "grupo cotizacion",
            "ccc",
        ),
        2,
    ),
    DocType.PATRIMONIAL: (
        (
            "aeat - consulta",
            "lista de productos",
            "entidades financieras",
            "consultas por nif",
            "nacionalidad",
        ),
        2,
    ),
    DocType.BANKING: (
        (
            "tae",
            "tipo nominal anual",
            "sistema de reembolso",
            "limite de credito",
            "comision por retirada",
            "interes nominal anual",
            "cuota",
            "primera tarjeta emitida",
        ),
        2,
    ),
}


def _normalise(text: str) -> str:
    """Lowercase, accent-strip, colon-strip, whitespace-collapse."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(stripped.lower().rstrip(":").split())


def detect_doc_type(labels: Iterable[str]) -> DocTypeMatch:
    """Inspect the emitted pair labels and return the best-fit document type.

    Confidence is `hits / markers_total` for the winning family, capped at 1.0.
    When no family clears its `min_hits` threshold the result is UNKNOWN with
    confidence 0.
    """
    norm_labels = [_normalise(lbl) for lbl in labels]

    best_family = DocType.UNKNOWN
    best_hits = 0
    best_total = 1
    best_signals: list[str] = []

    for family, (markers, min_hits) in _MARKERS.items():
        signals: list[str] = []
        for marker in markers:
            if any(marker in lbl for lbl in norm_labels):
                signals.append(marker)
        hits = len(signals)
        if hits < min_hits:
            continue
        # Pick the family with the highest absolute hit count, breaking ties on
        # density (hits / total markers).
        if hits > best_hits or (
            hits == best_hits and hits / len(markers) > best_hits / best_total
        ):
            best_family = family
            best_hits = hits
            best_total = len(markers)
            best_signals = signals

    if best_family is DocType.UNKNOWN:
        return DocTypeMatch(DocType.UNKNOWN, 0.0, ())

    confidence = min(1.0, best_hits / best_total + 0.2)
    return DocTypeMatch(
        doc_type=best_family,
        confidence=round(confidence, 3),
        signals=tuple(best_signals),
    )
