"""Golden structure spec for CONTRATO IKEA.pdf page 7.

Precio de los servicios — single 2-column table with 10 rows of pricing.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO IKEA.pdf"
PAGE = 7

META = {
    "document_type": "Contrato de cuenta de crédito con o sin Tarjeta IKEA (CaixaBank Payments & Consumer)",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_ikea_precio_servicios_table",
        "caixabank_ikea_multi_line_label_pricing",
        "caixabank_ikea_long_text_value_pricing",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "precio_servicios",
        "title": "Precio de los servicios",
        "y_hint": 75,
        "children": [
            {
                "type": "table",
                "id": "precio_servicios_table",
                "title": "Tarifas de servicios",
                "y_hint": 94,
                "columns": [
                    {"id": "label", "label": "Servicio", "type": "text"},
                    {"id": "value", "label": "Precio", "type": "text"},
                ],
                "rows": [
                    {"label": ("Mantenimiento de la Tarjeta IKEA", 94), "value": ("0€.", 94)},
                    {"label": ("Duplicado de Tarjeta IKEA", 115), "value": ("0€.", 116)},
                    {"label": ("Cancelación anticipada de la deuda", 137), "value": ("0€.", 137)},
                    {
                        "label": ("Retirada de dinero en efectivo a crédito en cajeros, a través de la Tarjeta IKEA", 159),
                        "value": ("5% del importe dispuesto, mínimo 4€", 159),
                    },
                    {
                        "label": ("Retirada de efectivo a crédito a través de teléfono", 187),
                        "value": (
                            "4% del importe dispuesto, o porcentaje inferior si se indica en la "
                            "campaña. Importe mínimo de disposición: 100€.",
                            187,
                        ),
                    },
                    {
                        "label": ("Retirada de efectivo a crédito a través de web", 214),
                        "value": (
                            "4% del importe dispuesto, mínimo 3€, o porcentaje inferior si se "
                            "indica en la campaña. Importe mínimo de disposición: 100€.",
                            214,
                        ),
                    },
                    {
                        "label": (
                            "Servicio de fraccionamiento del importe de las compras realizadas "
                            "con modalidad de pago Fin de Mes",
                            241,
                        ),
                        "value": (
                            "3% del importe nominal de la compra realizada cuando se fraccione "
                            "el importe en 3 meses.",
                            241,
                        ),
                    },
                    {
                        "label": (
                            "Cambio de divisa de las disposiciones o compras realizadas en moneda "
                            "diferente al euro",
                            281,
                        ),
                        "value": (
                            "aplicamos el tipo de cambio que la marca de la tarjeta (Visa) tiene "
                            "publicado en su página web en el momento en que recibimos información "
                            "de que usted ha realizado la operación incrementado en un 3,95%.",
                            281,
                        ),
                    },
                    {
                        "label": ("Reclamación de cuota impagada", 330),
                        "value": (
                            "15€ por los recursos que destinaremos a poner al día la deuda "
                            "impagada. Un mismo impago no podrá generar más de una compensación. "
                            "Sólo se cobrará esta compensación en deudas iguales o superiores a "
                            "20€. Si después de 15 días se mantiene el impago, podemos enviarle "
                            "un burofax o equivalente con certificación de contenido y recibo. "
                            "Actualmente el precio del envío del burofax es de 24 euros y le "
                            "reclamaremos su coste únicamente en deudas superiores a 300€.",
                            328,
                        ),
                    },
                    {
                        "label": (
                            "Envío de documentación relativa al contrato por correo postal a "
                            "petición de usted",
                            430,
                        ),
                        "value": ("0,60€ por comunicado.", 436),
                    },
                ],
            },
        ],
    },
]
