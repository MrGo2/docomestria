"""Capa 3.8 — schema-aware label mapping.

Maps the human label as it appears on the page (``N.I.F.``, ``Fecha de
emisión``, ``Nº Procedimiento`` ...) to a canonical snake_case slug
(``nif``, ``fecha_emision``, ``procedimiento_numero``).

The lookup is case-, accent-, and punctuation-insensitive — the source
PDFs vary wildly in how labels are typeset.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = [
    "LABEL_SCHEMA",
    "canonical_label",
    "normalise_label",
]


# Canonical label slug for known labels (lookup is normalised via
# ``normalise_label`` before consulting this dict). Keep these keys in their
# already-normalised form (lowercase, no accents, no punctuation).
LABEL_SCHEMA: dict[str, str] = {
    "nif": "nif",
    "n i f": "nif",
    "no procedimiento": "procedimiento_numero",
    "numero procedimiento": "procedimiento_numero",
    "no documento": "documento_numero",
    "numero documento": "documento_numero",
    "fecha de emision": "fecha_emision",
    "fecha emision": "fecha_emision",
    "fecha alta": "fecha_alta",
    "fecha situacion": "fecha_situacion",
    "titular": "titular",
    "razon social convenio regimen": "razon_social",
    "razon social": "razon_social",
    "no seguridad social": "numero_seguridad_social",
    "numero seguridad social": "numero_seguridad_social",
    "tipo contrato": "tipo_contrato",
    "ccc": "ccc",
    "nombre y apellidos": "nombre_apellidos",
    "tipo identificacion": "tipo_identificacion",
    "limite de credito": "limite_credito",
    "sistema de reembolso": "sistema_reembolso",
    "tae": "tae",
    "interes nominal anual": "interes_nominal_anual",
    "cuota": "cuota",
    "importe total adeudado": "importe_total_adeudado",
}


_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalise_label(label: str) -> str:
    """Return the lookup form of ``label``: lowercased, accent-stripped,
    punctuation removed, whitespace collapsed.

    ``N.I.F.`` → ``n i f``, ``Fecha de emisión:`` → ``fecha de emision``,
    ``Nº Procedimiento`` → ``no procedimiento``.
    """
    if not label:
        return ""
    # Strip accents.
    folded = "".join(
        ch
        for ch in unicodedata.normalize("NFD", label)
        if unicodedata.category(ch) != "Mn"
    )
    # Normalise Spanish ordinal ``º``/``ª`` already present in the label
    # before accent stripping has run (NFD leaves them alone). The ``Nº``
    # sequence becomes ``no`` once lowercased + punctuation-stripped.
    folded = folded.replace("º", "o").replace("ª", "a")
    folded = folded.lower()
    folded = _PUNCT_RE.sub(" ", folded)
    folded = _WS_RE.sub(" ", folded).strip()
    return folded


def canonical_label(label: str) -> str | None:
    """Return the canonical schema slug for ``label`` or ``None`` when the
    label is unknown.
    """
    key = normalise_label(label)
    if not key:
        return None
    return LABEL_SCHEMA.get(key)
