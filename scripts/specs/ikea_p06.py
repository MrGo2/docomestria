"""Golden structure spec for CONTRATO IKEA.pdf page 6.

Three blocks:
- Día de pago inicialmente escogido (single KV at top)
- Identificación del Establecimiento (4 fields, mostly populated)
- Disposición que realiza en este acto (form with 11+ empty fields + Modalidad pago=Fraccionado)
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO IKEA.pdf"
PAGE = 6

META = {
    "document_type": "Contrato de cuenta de crédito con o sin Tarjeta IKEA (CaixaBank Payments & Consumer)",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_ikea_dia_pago_kv",
        "caixabank_ikea_identificacion_establecimiento",
        "caixabank_ikea_disposicion_empty_form",
        "caixabank_ikea_multi_line_value_empresa_asociada",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "dia_pago",
        "title": "Día de pago",
        "y_hint": 89,
        "children": [
            {
                "type": "kv_leaf",
                "id": "dia_pago_kv",
                "label": "Día de pago inicialmente escogido",
                "value": "30",
                "y_hint": 89,
            },
        ],
    },
    {
        "type": "section",
        "id": "identificacion_establecimiento",
        "title": "Identificación del Establecimiento",
        "y_hint": 143,
        "children": [
            {
                "type": "kv_group",
                "id": "establecimiento_fields",
                "pairs": [
                    {"label": "Denominación", "value": "IKEA IBERICA", "y_hint": 173},
                    {
                        "label": "Domicilio social",
                        "value": "AUTOVIA SEVILLA-HUELVA , A-49 41950 CASTILLEJA CUESTA",
                        "y_hint": 210,
                    },
                    {
                        "label": "Empresa asociada y entidad colaboradora (identidad y domicilio)",
                        "value": (
                            "Ikea Ibérica, S.A. con CIF A28812618, AVENIDA MATAPIÑONERA , 9 "
                            "28703 SAN SEBASTIAN DE LOS REYES MADRID"
                        ),
                        "y_hint": 246,
                    },
                    {"label": "Código del establecimiento", "value": "32383005", "y_hint": 248},
                ],
            },
        ],
    },
    {
        "type": "section",
        "id": "disposicion_acto",
        "title": "Disposición que realiza en este acto",
        "y_hint": 305,
        "children": [
            {
                "type": "kv_group",
                "id": "disposicion_fields",
                "pairs": [
                    {"label": "Disposición que realiza en este acto", "value": "", "y_hint": 305},
                    {"label": "Importe", "value": "", "y_hint": 305},
                    {"label": "Fecha de vencimiento de la primera cuota", "value": "", "y_hint": 332},
                    {"label": "TIN", "value": "", "y_hint": 370},
                    {"label": "TAE", "value": "", "y_hint": 370},
                    {"label": "Nº de cuotas", "value": "", "y_hint": 408},
                    {"label": "Importe 1ª cuota", "value": "", "y_hint": 408},
                    {"label": "Importe última cuota", "value": "", "y_hint": 408},
                    {"label": "Importe restantes cuotas", "value": "", "y_hint": 446},
                    {"label": "Modalidad de pago aplicable", "value": "Fraccionado", "y_hint": 446},
                    {"label": "Excepcionalidades", "value": "", "y_hint": 486},
                ],
            },
        ],
    },
]
