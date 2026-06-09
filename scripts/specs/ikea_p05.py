"""Golden structure spec for CONTRATO IKEA.pdf page 5.

Mostly prose explaining the minimum monthly fee formula. Single KV: Período de liquidación.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO IKEA.pdf"
PAGE = 5

META = {
    "document_type": "Contrato de cuenta de crédito con o sin Tarjeta IKEA (CaixaBank Payments & Consumer)",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_ikea_prose_heavy_explanatory_page",
        "caixabank_ikea_periodo_liquidacion_single_kv",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "calculo_cuota_minima",
        "title": "Cómo calculamos la cuota mínima para Pago Aplazado (Revolving):",
        "y_hint": 86,
        "children": [
            {
                "type": "kv_leaf",
                "id": "periodo_liquidacion",
                "label": "Período de liquidación",
                "value": "mensual",
                "y_hint": 635,
            },
        ],
    },
]
