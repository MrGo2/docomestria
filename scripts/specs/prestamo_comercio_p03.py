"""Golden structure spec for CONTRATO PRESTAMO COMERCIO 2.pdf page 3.

5 representative tables (Nombre/NIF/Dirección/Teléfono/E-mail):
- Titular 1 representante 1: populated with ADRIAN SPIRIEON SOLCAN
- Titular 1 representante 2: empty
- Titular 2 representante 1: empty
- Avalista/Fiador 1 representante 1: empty
- Avalista/Fiador 1 representante 2: empty
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO PRESTAMO COMERCIO 2.pdf"
PAGE = 3

META = {
    "document_type": "Contrato de préstamo CaixaBank Payments & Consumer",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_prestamo_representante_tables_5col_form",
        "caixabank_prestamo_representante_titular_1_populated",
        "caixabank_prestamo_representante_remaining_empty",
    ],
}


def _rep_table(table_id, title, y_base, *, nombre="", nif="", direccion="", telefono="", email=""):
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


STRUCTURE = [
    {
        "type": "section",
        "id": "rep_titular_1",
        "title": "Datos personales del/de los representante/s del Titular 1 (en particular, si el Titular es una persona jurídica)",
        "y_hint": 92,
        "children": [
            _rep_table(
                "rep_titular_1_rep_1", "Representante 1", 115,
                nombre="ADRIAN SPIRIEON SOLCAN",
                nif="X7891505K",
                direccion="CL BAYEU 10 45190 TOLEDO",
                telefono="634673967",
                email="NANI198731@HOTMAIL.COM",
            ),
            _rep_table("rep_titular_1_rep_2", "Representante 2", 221),
        ],
    },
    {
        "type": "section",
        "id": "rep_titular_2",
        "title": "Datos personales del/de los representante/s del Titular 2 (en particular, si el Titular es una persona jurídica)",
        "y_hint": 350,
        "children": [
            _rep_table("rep_titular_2_rep_1", "Representante 1", 374),
        ],
    },
    {
        "type": "section",
        "id": "rep_avalista_fiador_1",
        "title": "Datos personales del/de los representante/s del Avalista/Fiador 1 (en particular, si el Avalista/Fiador 1 es una persona jurídica)",
        "y_hint": 503,
        "children": [
            _rep_table("rep_av_fi_1_rep_1", "Representante 1", 540),
            _rep_table("rep_av_fi_1_rep_2", "Representante 2", 645),
        ],
    },
]
