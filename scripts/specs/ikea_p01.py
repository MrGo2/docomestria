"""Golden structure spec for CONTRATO IKEA.pdf page 1 (Índice).

Two-level table of contents:
- A. Condiciones Particulares (single bullet)
- B. Condiciones Generales (26 numbered topics, each title + description)

Each numbered item modelled as free_text_list entry: label=topic title, value=description.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO IKEA.pdf"
PAGE = 1

META = {
    "document_type": "Contrato de cuenta de crédito con o sin Tarjeta IKEA (CaixaBank Payments & Consumer)",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_ikea_index_two_top_sections",
        "caixabank_ikea_index_26_numbered_items",
        "caixabank_ikea_index_title_plus_description_per_item",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "indice",
        "title": "Índice",
        "y_hint": 107,
        "children": [
            {
                "type": "kv_leaf",
                "id": "seccion_a_particulares",
                "label": "A. Condiciones Particulares del contrato de financiación",
                "value": "",
                "y_hint": 132,
            },
            {
                "type": "kv_leaf",
                "id": "seccion_b_generales",
                "label": "B. Condiciones Generales del contrato de financiación",
                "value": "",
                "y_hint": 157,
            },
            {
                "type": "free_text_list",
                "id": "indice_temas",
                "title": "Temas (1-26)",
                "items": [
                    {"label": "1. La cuenta de crédito con o sin Tarjeta IKEA.", "value": "Qué son y qué pueden hacer.", "y_hint": 183},
                    {"label": "2. Modalidades de pago y de disposición que permite su cuenta de crédito con o sin Tarjeta IKEA.", "value": "Qué posibilidades tiene de pagar a crédito, o de retirar dinero en efectivo metálico a crédito si dispone de Tarjeta IKEA.", "y_hint": 195},
                    {"label": "3. Intereses.", "value": "Cómo se calculan los intereses y cuándo se pagan.", "y_hint": 233},
                    {"label": "4. Titularidad.", "value": "Quién se responsabiliza de este contrato de Cuenta de crédito con o sin Tarjeta IKEA y de la Tarjeta IKEA, si la hay.", "y_hint": 245},
                    {"label": "5. Cuenta corriente asociada.", "value": "Qué cuenta puede asociarse al contrato de Cuenta de crédito con o sin Tarjeta IKEA.", "y_hint": 271},
                    {"label": "6. Número de teléfono asociado.", "value": "Por qué es necesario que nos facilite su número de teléfono.", "y_hint": 296},
                    {"label": "7. Acceso y usos.", "value": "Cómo puede disponer de su Cuenta de crédito con o sin Tarjeta IKEA, y hacerlo de forma segura.", "y_hint": 308},
                    {"label": "8. TAE.", "value": "Qué es y cómo calculamos la Tasa Anual Equivalente (TAE).", "y_hint": 333},
                    {"label": "9. Órdenes de pago.", "value": "Cuándo ejecutamos (realizamos) una orden de pago.", "y_hint": 346},
                    {"label": "10. Divisas.", "value": "Qué tipo de cambio aplicamos si paga en una moneda distinta al euro.", "y_hint": 359},
                    {"label": "11. Información de los pagos.", "value": "Cómo y cuándo sabrá usted cuánto ha pagado y cuánto le queda por pagar.", "y_hint": 371},
                    {"label": "12. Impagos.", "value": "Los impagos (retrasos en el pago) generan intereses.", "y_hint": 384},
                    {"label": "13. Bloqueo del saldo disponible de la Cuenta de crédito con o sin Tarjeta IKEA asociada.", "value": "El saldo disponible de su Cuenta de crédito y su Tarjeta IKEA asociada, si la tiene, pueden quedar bloqueados o limitados temporalmente.", "y_hint": 396},
                    {"label": "14. Comunicaciones.", "value": "Cómo nos comunicamos con usted.", "y_hint": 434},
                    {"label": "15. Nuestros deberes y responsabilidades para la seguridad de su Cuenta de crédito, y de su Tarjeta IKEA asociada, si la hay.", "value": "La importancia de proteger su Cuenta de crédito, y, si la tiene, su Tarjeta IKEA y su PIN.", "y_hint": 446},
                    {"label": "16. Incidencias.", "value": "Qué hacer si observa irregularidades en los movimientos realizados con su Cuenta de crédito.", "y_hint": 472},
                    {"label": "17. Ley aplicable a este contrato. Quejas y reclamaciones.", "value": "Cómo puede hacernos llegar sus quejas y reclamaciones.", "y_hint": 484},
                    {"label": "18. Duración y cancelación.", "value": "Quién puede cancelar el contrato, cuándo y cómo.", "y_hint": 509},
                    {"label": "19. Desistimiento.", "value": "Cuándo y cómo puede desistir (renunciar) de este contrato.", "y_hint": 522},
                    {"label": "20. Derechos adicionales que podrá usted ejercer.", "value": "Cuándo y cómo puede ejercitar los derechos que le correspondan frente a CaixaBank Payments & Consumer teniendo el contrato de Cuenta de crédito el carácter de vinculado.", "y_hint": 534},
                    {"label": "21. Modificaciones.", "value": "Cómo y cuándo desde CaixaBank Payments & Consumer podemos modificar las condiciones del contrato, y qué puede hacer usted al respecto.", "y_hint": 572},
                    {"label": "22. Cesión.", "value": "Desde CaixaBank Payments & Consumer podremos ceder los derechos y obligaciones del contrato.", "y_hint": 597},
                    {"label": "23. Servicios vinculados o combinados.", "value": "Para contratar la Cuenta de crédito con o sin Tarjeta IKEA, si el producto contratado la ofrece, no es obligatorio contratar otro servicio más.", "y_hint": 610},
                    {"label": "24. Precios.", "value": "Cuánto cuesta la Cuenta de crédito con o sin Tarjeta IKEA y los servicios que con ella le ofrecemos.", "y_hint": 635},
                    {"label": "25. Tratamiento de datos de carácter personal.", "value": "Cómo tratamos sus datos personales.", "y_hint": 648},
                    {"label": "26. Políticas de sanciones, prevención de blanqueo y lucha contra el fraude.", "value": "En CaixaBank Payments & Consumer gozamos de políticas sobre sanciones económico-financieras internacionales, prevención de blanqueo y lucha contra el fraude.", "y_hint": 660},
                ],
            },
        ],
    },
]
