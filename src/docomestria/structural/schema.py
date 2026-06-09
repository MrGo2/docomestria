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

from .doctype import DocType

__all__ = [
    "BANKING_SCHEMA",
    "LABEL_SCHEMA",
    "LABORAL_SCHEMA",
    "PATRIMONIAL_SCHEMA",
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


LABORAL_SCHEMA: dict[str, str] = {
    "ccc": "ccc",
    "razon social convenio regimen": "razon_social",
    "no seguridad social": "numero_seguridad_social",
    "numero seguridad social": "numero_seguridad_social",
    "situacion actual": "situacion_actual",
    "fecha situacion": "fecha_situacion",
    "fecha alta": "fecha_alta",
    "tipo contrato": "tipo_contrato",
    "grupo cotizacion": "grupo_cotizacion",
    "titular": "titular",
}

PATRIMONIAL_SCHEMA: dict[str, str] = {
    "nombre": "nombre",
    "primer apellido": "primer_apellido",
    "segundo apellido": "segundo_apellido",
    "dni": "dni",
    "nacionalidad": "nacionalidad",
    "aeat consulta percepciones": "aeat_consulta_percepciones",
    "aeat consulta actividades economicas": "aeat_consulta_actividades_economicas",
    "aeat cuentasampliadas mod 196": "aeat_cuentas_ampliadas",
}

BANKING_SCHEMA: dict[str, str] = {
    "tae": "tae",
    "interes nominal anual": "interes_nominal_anual",
    "cuota": "cuota",
    "importe total adeudado": "importe_total_adeudado",
    "limite de credito": "limite_credito",
    "sistema de reembolso": "sistema_reembolso",
    "nombre y apellidos": "titular_principal",
    "primera tarjeta emitida": "comision_primera_tarjeta",
    "resto de tarjetas": "comision_resto_tarjetas",
    "clave restriccion": "clave_restriccion",
}


_FAMILY_SCHEMAS: dict[DocType, dict[str, str]] = {
    DocType.LABORAL: LABORAL_SCHEMA,
    DocType.PATRIMONIAL: PATRIMONIAL_SCHEMA,
    DocType.BANKING: BANKING_SCHEMA,
}


def canonical_label(
    label: str, doc_type: DocType = DocType.UNKNOWN
) -> str | None:
    """Return the canonical schema slug for ``label`` or ``None`` when the
    label is unknown.

    When ``doc_type`` is given the family-specific table is consulted first,
    so the same label ('Titular' on a banking form vs a labour court doc)
    can resolve to different slugs per family.
    """
    key = normalise_label(label)
    if not key:
        return None
    family_table = _FAMILY_SCHEMAS.get(doc_type)
    if family_table is not None and key in family_table:
        return family_table[key]
    return LABEL_SCHEMA.get(key)
