"""Golden structure spec for BBVA_0608-01491495_DOC2_CONTRATO.pdf page 3."""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/AZUREDOCUI/5_Example/BBVA_0608-01491495_DOC2_CONTRATO.pdf"
PAGE = 3

META = {
    "document_type": "Contrato de Préstamo Personal BBVA",
    "annotator": "codex",
    "covers_cases": [
        "bbva_loan_conditions",
        "bbva_loan_multicolumn_matrix",
        "bbva_loan_repeated_value_rows",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "condiciones_economicas_prestamo",
        "title": "Condiciones Económicas del Préstamo",
        "y_hint": 87,
        "children": [
            {
                "type": "table",
                "id": "condiciones_base",
                "title": "Condiciones base",
                "y_hint": 112,
                "columns": [
                    {"id": "label", "label": "Condición", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {
                        "label": ("Importe Total del Préstamo", 112),
                        "value": ("29.000,00 Veintinueve mil euros", 123),
                    },
                    {"label": ("Fecha Entrada en Vigor", 153), "value": ("29-03-2021", 153)},
                    {"label": ("Vencimiento Final", 176), "value": ("31-03-2029", 176)},
                    {
                        "label": ("Entrega del Importe del Préstamo", 201),
                        "value": ("ABONO EN CUENTA 0182-0719-22-0201514439", 192),
                    },
                    {
                        "label": ("Interés Nominal de Demora", 236),
                        "value": ("Tipo de Interés Nominal + 2 puntos", 236),
                    },
                    {"label": ("Comisión de Apertura", 259), "value": ("2,3000 %", 259)},
                    {"label": ("Mínimo", 259), "value": ("0,00 euros", 258)},
                    {
                        "label": ("Comisión de Cancelación Anticipada Total", 291),
                        "value": (
                            "1,0000% máximo, con un mínimo de 11,50 euros en concepto "
                            "de coste administrativo de cancelación.",
                            278,
                        ),
                    },
                    {
                        "label": ("Comisión de Cancelación Anticipada Parcial", 351),
                        "value": (
                            "1,0000% máximo, con un mínimo de 11,50 euros en concepto "
                            "de coste administrativo de cancelación.",
                            345,
                        ),
                    },
                ],
            },
            {
                "type": "table",
                "id": "bonificacion_nomina",
                "title": "Bonificación por nómina",
                "y_hint": 405,
                "columns": [
                    {"id": "label", "label": "Condición", "type": "text"},
                    {"id": "sin_nomina", "label": "Sin nómina", "type": "amount_or_percent"},
                    {"id": "con_nomina", "label": "Con nómina", "type": "amount_or_percent"},
                ],
                "rows": [
                    {
                        "label": ("Interés Nominal Anual", 430),
                        "sin_nomina": ("11,2000%", 428),
                        "con_nomina": ("10,2000%", 428),
                    },
                    {
                        "label": ("TAE", 452),
                        "sin_nomina": ("12,6020%", 449),
                        "con_nomina": ("11,4813%", 451),
                    },
                    {
                        "label": ("Importe Total Adeudado", 487),
                        "sin_nomina": ("44.794,73€", 490),
                        "con_nomina": ("43.299,05€", 490),
                    },
                    {
                        "label": ("Cuota", 534),
                        "sin_nomina": ("458,68€", 531),
                        "con_nomina": ("443,13€", 533),
                    },
                ],
            },
            {
                "type": "table",
                "id": "otras_condiciones",
                "title": "Otras condiciones económicas",
                "y_hint": 553,
                "columns": [
                    {"id": "label", "label": "Condición", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {
                        "label": ("Gasto Reclamación Posiciones Deudoras", 553),
                        "value": ("30,00 euros", 554),
                    },
                    {
                        "label": ("Domiciliación de Cuotas", 598),
                        "value": (
                            "CUENTA 0182-0719-22-0201514439 BBVA OVIEDO-PRIMO "
                            "DE RIVERA PL. PRIMO RIVERA, 3",
                            587,
                        ),
                    },
                ],
            },
        ],
    }
]
