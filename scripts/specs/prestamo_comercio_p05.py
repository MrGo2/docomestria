"""Golden structure spec for CONTRATO PRESTAMO COMERCIO 2.pdf page 5.

B. CONDICIONES PARTICULARES — Three numbered sub-sections (1-4 visible on this page):
1. IMPORTE TOTAL DEL CAPITAL PRESTADO
2. DURACIÓN (with sub-dates)
3. CONDICIONES ECONÓMICAS (TIN, TAE, demora, precios, comisiones, compensación)
4. FORMA DE PAGO (Importe total, intereses, forma de pago) — continues on p06
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO PRESTAMO COMERCIO 2.pdf"
PAGE = 5

META = {
    "document_type": "Contrato de préstamo CaixaBank Payments & Consumer",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_prestamo_condiciones_particulares_header",
        "caixabank_prestamo_importe_capital_duracion_dates",
        "caixabank_prestamo_condiciones_economicas_table",
        "caixabank_prestamo_long_text_value_amortizaciones",
        "caixabank_prestamo_forma_pago_partial",
    ],
}


_PRECIO_AMORT = (
    "1%, con un máximo de 0,5% si el pago anticipado se realiza durante el último año, "
    "siempre que Usted sea consumidor y el importe total prestado esté entre 200 y 75.000 "
    "euros. En el caso de que Usted sea una empresa o una persona física actuando en su "
    "ámbito profesional, la comisión de amortización anticipada podrá ser hasta un máximo "
    "de un 3%."
)

_COMPENSACION = (
    "15€ por los recursos que destinaremos a poner al día la deuda impagada. Un mismo "
    "impago no podrá generar más de una compensación. Sólo se cobrará esta compensación "
    "en deudas iguales o superiores a 20€. Si después de 15 días se mantiene el impago, "
    "podemos enviarle un burofax o equivalente con certificación de contenido y recibo. "
    "Actualmente el precio del envío del burofax es de 24 euros y le reclamaremos su coste "
    "únicamente en deudas superiores a 300€."
)

_FORMA_PAGO_PART = (
    "El precio del servicio y la comisión de estudio, cuando las haya, se pagarán una sola "
    "vez en el momento de la entrega del dinero, o bien, de manera financiada junto con el "
    "resto del importe del préstamo. Las cuotas del préstamo para devolver el dinero "
    "prestado se pagarán con periodicidad mensual."
)


STRUCTURE = [
    {
        "type": "section",
        "id": "condiciones_particulares",
        "title": "B. CONDICIONES PARTICULARES",
        "y_hint": 84,
        "children": [
            {
                "type": "section",
                "id": "importe_capital",
                "title": "1. IMPORTE TOTAL DEL CAPITAL PRESTADO",
                "y_hint": 105,
                "children": [
                    {
                        "type": "kv_leaf",
                        "id": "importe_capital_kv",
                        "label": "IMPORTE TOTAL DEL CAPITAL PRESTADO",
                        "value": "2.500,00 EUROS",
                        "y_hint": 129,
                    },
                ],
            },
            {
                "type": "section",
                "id": "duracion",
                "title": "2. DURACIÓN",
                "y_hint": 153,
                "children": [
                    {
                        "type": "kv_leaf",
                        "id": "duracion_kv",
                        "label": "DURACIÓN",
                        "value": "30 MESES",
                        "y_hint": 176,
                    },
                    {
                        "type": "kv_leaf",
                        "id": "fecha_primer_pago",
                        "label": "Fecha del primer pago",
                        "value": "28/02/2025",
                        "y_hint": 202,
                    },
                    {
                        "type": "kv_leaf",
                        "id": "fecha_ultimo_pago",
                        "label": "Fecha del último pago (fin de préstamo)",
                        "value": "30/07/2027",
                        "y_hint": 229,
                    },
                ],
            },
            {
                "type": "section",
                "id": "condiciones_economicas",
                "title": "3. CONDICIONES ECONÓMICAS",
                "y_hint": 251,
                "children": [
                    {
                        "type": "table",
                        "id": "condiciones_economicas_table",
                        "title": "Condiciones económicas",
                        "y_hint": 274,
                        "columns": [
                            {"id": "label", "label": "Concepto", "type": "text"},
                            {"id": "value", "label": "Valor", "type": "text"},
                        ],
                        "rows": [
                            {"label": ("TIN (Tipo de Interés Nominal, anual y fijo)", 274), "value": ("0,00 %", 274)},
                            {"label": ("TAE (Tasa Anual Equivalente)", 301), "value": ("2,71 %", 301)},
                            {"label": ("Interés en caso de demora o retraso en el pago (mensual)", 328), "value": ("0,00 %", 331)},
                            {"label": ("Precio del servicio", 366), "value": ("87,50 EUROS", 366)},
                            {"label": ("Comisión de estudio", 393), "value": ("0 EUROS", 394)},
                            {"label": ("Precio de las amortizaciones anticipadas", 421), "value": (_PRECIO_AMORT, 421)},
                            {"label": ("Compensación por costes de cobro ante un impago", 508), "value": (_COMPENSACION, 508)},
                        ],
                    },
                ],
            },
            {
                "type": "section",
                "id": "forma_pago",
                "title": "4. FORMA DE PAGO (Ver, además, el cuadro de amortización que se une como Anexo a este contrato)",
                "y_hint": 615,
                "children": [
                    {
                        "type": "table",
                        "id": "forma_pago_table_p05",
                        "title": "Forma de pago (parte 1)",
                        "y_hint": 650,
                        "columns": [
                            {"id": "label", "label": "Concepto", "type": "text"},
                            {"id": "value", "label": "Valor", "type": "text"},
                        ],
                        "rows": [
                            {
                                "label": (
                                    "Importe total a pagar: resultado de sumar el importe total del capital "
                                    "prestado más el importe total de intereses, más el precio del servicio "
                                    "y la comisión de estudio",
                                    650,
                                ),
                                "value": (
                                    "2.587,50 EUROS (2.500,00 euros del capital prestado + 0 euros de "
                                    "intereses + 87,50 euros de precio del servicio + 0 euros de la "
                                    "comisión de estudio)",
                                    651,
                                ),
                            },
                            {"label": ("Importe total de intereses", 713), "value": ("0 EUROS", 716)},
                            {"label": ("Forma de pago", 776), "value": (_FORMA_PAGO_PART, 746)},
                        ],
                    },
                ],
            },
        ],
    },
]
