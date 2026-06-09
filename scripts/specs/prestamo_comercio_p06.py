"""Golden structure spec for CONTRATO PRESTAMO COMERCIO 2.pdf page 6.

Continuation of Forma de Pago + CONTRATO VINCULADO block + INFORMACIÓN ESPECIALMENTE RELEVANTE prose intro.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO PRESTAMO COMERCIO 2.pdf"
PAGE = 6

META = {
    "document_type": "Contrato de préstamo CaixaBank Payments & Consumer",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_prestamo_forma_pago_cuotas_mixtas",
        "caixabank_prestamo_contrato_vinculado_ortodoncia",
        "caixabank_prestamo_si_no_choices_compra_factura",
        "caixabank_prestamo_excepcionalidades_bonificado",
    ],
}


_EXCEPCIONALIDADES = (
    "CONTRATO BONIFICADO: CONTRATO CON TIPO DE INTERÉS ORDINARIO '0%' MIENTRAS EL TITULAR "
    "CUMPLA A SU VENCIMIENTO SUS OBLIGACIONES DE PAGO, EN LOS TÉRMINOS ESPECIFICADOS EN "
    "LAS CONDICIONES GENERALES."
)


STRUCTURE = [
    {
        "type": "section",
        "id": "forma_pago_cont",
        "title": "FORMA DE PAGO (continuación)",
        "y_hint": 105,
        "children": [
            {
                "type": "table",
                "id": "forma_pago_table_p06",
                "title": "Cuotas mixtas",
                "y_hint": 117,
                "columns": [
                    {"id": "label", "label": "Concepto", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {
                        "label": ("Número de cuotas mixtas", 117),
                        "value": ("30 Desde 28/02/2025 hasta 30/07/2027", 105),
                    },
                    {
                        "label": (
                            "Importe de las cuotas mixtas (cuota de amortización de capital "
                            "prestado y pago de intereses)",
                            151,
                        ),
                        "value": (
                            "1ª CUOTA: 86,25 EUROS ÚLTIMA CUOTA: 86,25 EUROS RESTANTES: 86,25 EUROS",
                            154,
                        ),
                    },
                ],
            },
        ],
    },
    {
        "type": "section",
        "id": "contrato_vinculado",
        "title": "5. CONTRATO VINCULADO",
        "y_hint": 204,
        "children": [
            {
                "type": "table",
                "id": "vinculado_table",
                "title": "Datos del contrato vinculado",
                "y_hint": 224,
                "columns": [
                    {"id": "label", "label": "Concepto", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {"label": ("Objeto financiado", 224), "value": ("ORTODONCIIA NORMAL", 227)},
                    {"label": ("Identificación objeto financiado", 260), "value": ("49243003", 263)},
                    {"label": ("Establecimiento", 295), "value": ("CATALANO CLINICA ODONTOLOGICA", 298)},
                    {
                        "label": ("Empresa Asociada (denominación y domicilio) / Instalador", 331),
                        "value": ("", 331),
                    },
                    {"label": ("Domicilio social", 386), "value": ("CIUDAD DE MARTOS ,Nº 7 , 45400 MORA", 386)},
                    {"label": ("Precio al contado", 419), "value": ("2.500,00 EUROS", 422)},
                    {"label": ("SU COMPRA FINANCIADA/CONTRATO ASOCIADO", 443), "value": ("NO", 444)},
                    {"label": ("FACTURA INTEGRADA", 477), "value": ("NO", 478)},
                    {"label": ("EXCEPCIONALIDADES", 511), "value": (_EXCEPCIONALIDADES, 526)},
                ],
            },
        ],
    },
    {
        "type": "section",
        "id": "info_relevante",
        "title": "INFORMACIÓN ESPECIALMENTE RELEVANTE: TAE Y COMISIONES ASOCIADAS AL PRÉSTAMO",
        "y_hint": 592,
        "children": [],
    },
]
