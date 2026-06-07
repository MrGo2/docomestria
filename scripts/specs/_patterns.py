"""Reusable spec patterns extracted from existing CaixaBank/BBVA goldens.

These helpers produce walker-compatible structure dicts. Use them in specs
to avoid retyping common form layouts.

Patterns covered:
- caixabank_person_block: 25-field person form (titular/avalista/fiador)
- representative_table: 5-row Nombre/NIF/Dirección/Teléfono/E-mail table
- consent_matrix: SI/NO checkbox group with N consent items
- condiciones_economicas_table: 2-col label/value with multi-line values
- caixabank_page_noise: standard footer/sidebar noise for CaixaBank docs
"""

from __future__ import annotations


# =====================================================================
# CaixaBank person block (Titular 1/2, Avalista/Fiador 1/2)
# =====================================================================

# Field offsets (y_hint relative to block top). Derived from PRESTAMO p02.
_PERSON_FIELD_OFFSETS = {
    "apellidos": 13, "nombre": 13,
    "nif": 27, "nacionalidad": 27, "fecha_const": 27, "codigo_cnae": 27, "n_empleados": 27,
    "descripcion_sector": 41, "inscrita_en": 41,
    "domicilio": 55, "numero": 55, "piso": 55, "puerta": 55,
    "poblacion": 69, "cp": 69, "tel_fijo": 69, "tel_movil": 69,
    "correo": 83, "sexo": 83, "estado_civil": 83, "fecha_nac": 83,
    "personas_cargo": 97, "sit_viv": 97, "antig_viv": 97, "gastos_viv": 97, "otros_cred": 97,
    "situacion_lab": 111, "profesion": 111, "cargo": 111, "importe_ingr": 111, "antig_empresa": 111,
    "nombre_emp": 125, "actividad_emp": 125, "tel_emp": 125,
}

_PERSON_FIELD_LABELS = {
    "apellidos": "Apellidos", "nombre": "Nombre/Denominación",
    "nif": "NIF/CIF", "nacionalidad": "Nacionalidad",
    "fecha_const": "Fecha de constitución", "codigo_cnae": "Código CNAE", "n_empleados": "Nº empleados",
    "descripcion_sector": "Descripción sector actividad", "inscrita_en": "Inscrita en",
    "domicilio": "Domicilio", "numero": "Nº", "piso": "Piso", "puerta": "Puerta",
    "poblacion": "Población", "cp": "C.P.", "tel_fijo": "Teléfono fijo", "tel_movil": "Teléfono móvil",
    "correo": "Correo electrónico", "sexo": "Sexo", "estado_civil": "Estado civil", "fecha_nac": "Fecha de nacimiento",
    "personas_cargo": "Personas a su cargo", "sit_viv": "Sit. viv.", "antig_viv": "Antigüedad viv.",
    "gastos_viv": "Gastos vivienda", "otros_cred": "Otros créditos",
    "situacion_lab": "Situación laboral", "profesion": "Profesión", "cargo": "Cargo",
    "importe_ingr": "Importe ingresos", "antig_empresa": "Antigüedad en la empresa",
    "nombre_emp": "Nombre empresa", "actividad_emp": "Actividad empresa", "tel_emp": "Teléfono empresa",
}


def caixabank_person_block(block_id: str, y_base: int, **data) -> dict:
    """Generate a kv_group for a CaixaBank person form block.

    Args:
        block_id: e.g. "titular_1", "avalista_fiador_1"
        y_base: top of the block (y where "DEL Titular N" header sits)
        **data: optional field values. Unrecognised keys raise ValueError.
                Empty/missing → empty value (will be captured as form slot).

    Returns:
        dict suitable as a kv_group child of a section.
    """
    unknown = set(data.keys()) - set(_PERSON_FIELD_OFFSETS.keys())
    if unknown:
        raise ValueError(f"Unknown person fields: {unknown}")
    pairs = []
    for field, offset in _PERSON_FIELD_OFFSETS.items():
        pairs.append({
            "label": _PERSON_FIELD_LABELS[field],
            "value": data.get(field, ""),
            "y_hint": y_base + offset,
        })
    return {"type": "kv_group", "id": block_id, "pairs": pairs}


# =====================================================================
# Representative table (5-row: Nombre/NIF/Dirección/Teléfono/E-mail)
# =====================================================================

def representative_table(table_id: str, title: str, y_base: int, *,
                          nombre: str = "", nif: str = "",
                          direccion: str = "", telefono: str = "",
                          email: str = "") -> dict:
    """Generate a 2-col table for a representative entry.

    y_base is the y-coordinate of the Nombre row. Subsequent rows at
    +17, +33, +49, +66 (matches CaixaBank layout).
    """
    return {
        "type": "table",
        "id": table_id,
        "title": title,
        "y_hint": y_base,
        "columns": [
            {"id": "label", "label": "Campo", "type": "text"},
            {"id": "value", "label": "Valor", "type": "text"},
        ],
        "rows": [
            {"label": ("Nombre", y_base + 1), "value": (nombre, y_base)},
            {"label": ("NIF", y_base + 17), "value": (nif, y_base + 16)},
            {"label": ("Dirección", y_base + 33), "value": (direccion, y_base + 33)},
            {"label": ("Teléfono", y_base + 50), "value": (telefono, y_base + 49)},
            {"label": ("E-mail", y_base + 66), "value": (email, y_base + 65)},
        ],
    }


# =====================================================================
# Consent matrix (SI/NO checkboxes)
# =====================================================================

def consent_matrix(group_id: str, items: list[dict]) -> dict:
    """Generate a kv_group for a SI/NO consent matrix.

    Args:
        group_id: e.g. "consentimientos_titular_1"
        items: list of {"label": str, "value": "SI"|"NO"|"", "y_hint": int}

    Returns:
        kv_group dict.
    """
    return {
        "type": "kv_group",
        "id": group_id,
        "pairs": [
            {"label": it["label"], "value": it.get("value", ""), "y_hint": it["y_hint"]}
            for it in items
        ],
    }


# =====================================================================
# Condiciones económicas table (2-col with potentially long values)
# =====================================================================

def condiciones_table(table_id: str, title: str, y_hint: int,
                       rows: list[tuple]) -> dict:
    """Generate a 2-col label/value table from a list of (label, label_y, value, value_y) tuples.

    Each row tuple: (label_text, label_y, value_text, value_y)
    """
    return {
        "type": "table",
        "id": table_id,
        "title": title,
        "y_hint": y_hint,
        "columns": [
            {"id": "label", "label": "Concepto", "type": "text"},
            {"id": "value", "label": "Valor", "type": "text"},
        ],
        "rows": [
            {"label": (r[0], r[1]), "value": (r[2], r[3])}
            for r in rows
        ],
    }


# =====================================================================
# Standard CaixaBank page noise (footer + sidebar metadata)
# =====================================================================

def caixabank_page_noise(page_num: int, total_pages: int) -> list[dict]:
    """Generate noise nodes for a standard CaixaBank Payments & Consumer page.

    Returns a list of noise dicts to append to spec STRUCTURE.

    Note: builder still needs the actual span text to bbox-link; these
    nodes carry only the text + kind, and the walker will link them via y_hint.
    """
    return [
        {
            "type": "noise",
            "id": "footer_pagina",
            "text": f"Pág. {page_num} de {total_pages}",
            "kind": "page_number",
            "y_hint": 805,
        },
        {
            "type": "noise",
            "id": "footer_pages_metadata",
            "text": f"{page_num}/{total_pages}",
            "kind": "logalty_metadata",
            "y_hint": 274,
        },
    ]


# =====================================================================
# Numbered index item (free_text_list entry shortcut)
# =====================================================================

def index_item(number: int, title: str, description: str = "", y_hint: int = 0) -> dict:
    """Shortcut for a numbered index entry like '1. Topic title. Description.'."""
    return {
        "label": f"{number}. {title}",
        "value": description,
        "y_hint": y_hint,
    }
