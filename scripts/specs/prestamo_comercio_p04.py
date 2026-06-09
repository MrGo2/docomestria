"""Golden structure spec for CONTRATO PRESTAMO COMERCIO 2.pdf page 4.

- 2 empty representative tables (Avalista/Fiador 2)
- Por otra parte: CaixaBank description block
- Número de préstamo: 202501120127220
- Cuenta de pago y domiciliación: IBAN ES16 2100 3876 9101 0041 9936
- Tarjeta para la domiciliación: SI/NO X
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO PRESTAMO COMERCIO 2.pdf"
PAGE = 4

META = {
    "document_type": "Contrato de préstamo CaixaBank Payments & Consumer",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_prestamo_av_fi_2_representante_empty",
        "caixabank_prestamo_party_caixabank_block",
        "caixabank_prestamo_numero_iban_tarjeta_choice",
    ],
}


def _rep_table(table_id, title, y_base):
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
            {"label": ("Nombre", y_base), "value": ("", y_base)},
            {"label": ("NIF", y_base + 16), "value": ("", y_base + 16)},
            {"label": ("Dirección", y_base + 33), "value": ("", y_base + 33)},
            {"label": ("Teléfono", y_base + 49), "value": ("", y_base + 49)},
            {"label": ("E-mail", y_base + 66), "value": ("", y_base + 66)},
        ],
    }


STRUCTURE = [
    {
        "type": "section",
        "id": "rep_avalista_fiador_2",
        "title": "Datos personales del/de los representante/s del Avalista/Fiador 2 (en particular, si el Avalista/Fiador 2 es una persona jurídica)",
        "y_hint": 92,
        "children": [
            _rep_table("rep_av_fi_2_rep_1", "Representante 1", 130),
            _rep_table("rep_av_fi_2_rep_2", "Representante 2", 235),
        ],
    },
    {
        "type": "section",
        "id": "por_otra_parte",
        "title": "Por otra parte",
        "y_hint": 399,
        "children": [],
    },
    {
        "type": "section",
        "id": "datos_prestamo",
        "title": "Datos del préstamo",
        "y_hint": 578,
        "children": [
            {
                "type": "kv_leaf",
                "id": "numero_prestamo",
                "label": "Número de préstamo",
                "value": "202501120127220",
                "y_hint": 603,
            },
            {
                "type": "kv_group",
                "id": "cuenta_y_tarjeta",
                "pairs": [
                    {"label": "Cuenta de pago y domiciliación (IBAN)", "value": "ES16 2100 3876 9101 0041 9936", "y_hint": 679},
                    {"label": "Tarjeta para la domiciliación", "value": "NO", "y_hint": 671},
                ],
            },
        ],
    },
]
