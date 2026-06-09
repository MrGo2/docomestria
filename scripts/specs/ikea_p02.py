"""Golden structure spec for CONTRATO IKEA.pdf page 2 (CaixaBank Payments & Consumer).

Walker-compatible types only: section / kv_leaf / kv_group / table / array.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO IKEA.pdf"
PAGE = 2

META = {
    "document_type": "Contrato de cuenta de crédito con o sin Tarjeta IKEA (CaixaBank Payments & Consumer)",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_ikea_titular_dni_2col_kv_group",
        "caixabank_ikea_standalone_reference",
        "caixabank_ikea_condiciones_particulares_2col",
        "caixabank_ikea_multi_line_value_modalidad_pago",
        "caixabank_ikea_datos_personales_direccion_multi_line",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "parte_titular",
        "title": "Por una parte, usted (titular de la Cuenta de crédito con o sin Tarjeta IKEA)",
        "y_hint": 102,
        "children": [
            {
                "type": "kv_group",
                "id": "titular_identidad",
                "pairs": [
                    {"label": "Titular", "value": "SORALLA GAMAZA DOMÍNGUEZ", "y_hint": 153},
                    {"label": "DNI", "value": "45337936Z", "y_hint": 155},
                ],
            }
        ],
    },
    {
        "type": "section",
        "id": "parte_caixabank",
        "title": "Por otra parte, nosotros",
        "y_hint": 198,
        "children": [],
    },
    {
        "type": "section",
        "id": "datos_solicitud",
        "title": "Solicitud y preámbulo",
        "y_hint": 287,
        "children": [
            {
                "type": "kv_leaf",
                "id": "nro_solicitud",
                "label": "Nº solicitud-contrato",
                "value": "202502270270913",
                "y_hint": 287,
            },
        ],
    },
    {
        "type": "section",
        "id": "condiciones_particulares",
        "title": "A. CONDICIONES PARTICULARES",
        "y_hint": 479,
        "children": [
            {
                "type": "section",
                "id": "que_regulan",
                "title": "Qué regulan estas Condiciones Particulares",
                "y_hint": 496,
                "children": [
                    {
                        "type": "table",
                        "id": "producto_modalidad",
                        "title": "Producto y Modalidad de Pago",
                        "y_hint": 539,
                        "columns": [
                            {"id": "label", "label": "Concepto", "type": "text"},
                            {"id": "value", "label": "Valor", "type": "text"},
                        ],
                        "rows": [
                            {
                                "label": ("Producto", 539),
                                "value": ("Contrato de Cuenta de crédito con o sin Tarjeta IKEA VISA.", 539),
                            },
                            {
                                "label": ("Modalidad de pago elegida", 576),
                                "value": (
                                    "Pago Aplazado (Revolving). Por defecto, si no elige otra modalidad, "
                                    "se activará la modalidad de Pago Aplazado (Revolving). No obstante, "
                                    "le recordamos que las modalidades de pago que permite la tarjeta son: "
                                    "el Pago Fin de Mes, el Pago Aplazado (Revolving) y el Pago Fraccionado. "
                                    "Usted puede modificar la modalidad de pago elegida en cualquier momento.",
                                    566,
                                ),
                            },
                        ],
                    },
                ],
            }
        ],
    },
    {
        "type": "section",
        "id": "datos_personales_titular",
        "title": "DATOS PERSONALES DEL TITULAR",
        "y_hint": 634,
        "children": [
            {
                "type": "table",
                "id": "datos_titular",
                "title": "Datos personales",
                "y_hint": 661,
                "columns": [
                    {"id": "label", "label": "Campo", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {
                        "label": ("Titular del contrato", 661),
                        "value": ("SORALLA GAMAZA DOMÍNGUEZ", 669),
                    },
                    {
                        "label": ("Dirección", 701),
                        "value": (
                            "PAGO VILLARANA 8 11500 PUERTO DE SANTA MARIA, EL CADIZ",
                            701,
                        ),
                    },
                ],
            }
        ],
    },
]
