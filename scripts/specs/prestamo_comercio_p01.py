"""Golden structure spec for CONTRATO PRESTAMO COMERCIO 2.pdf page 1 (Índice).

Three top sections (A intro / B 6-item / C 22-item) + ANEXO trailer.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO PRESTAMO COMERCIO 2.pdf"
PAGE = 1

META = {
    "document_type": "Contrato de préstamo CaixaBank Payments & Consumer",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_prestamo_index_three_top_sections",
        "caixabank_prestamo_index_6_particulares_22_generales",
        "caixabank_prestamo_anexo_cuadro_amortizacion",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "indice",
        "title": "Índice",
        "y_hint": 100,
        "children": [
            {
                "type": "kv_leaf",
                "id": "seccion_a_intervinientes",
                "label": "A. INTERVINIENTES Y DATOS GENERALES",
                "value": "",
                "y_hint": 130,
            },
            {
                "type": "section",
                "id": "seccion_b_particulares",
                "title": "B. CONDICIONES PARTICULARES",
                "y_hint": 155,
                "children": [
                    {
                        "type": "free_text_list",
                        "id": "particulares_items",
                        "title": "Condiciones Particulares (1-6)",
                        "items": [
                            {"label": "1. IMPORTE TOTAL DEL CAPITAL PRESTADO", "value": "", "y_hint": 178},
                            {"label": "2. DURACIÓN", "value": "", "y_hint": 191},
                            {"label": "3. CONDICIONES ECONÓMICAS", "value": "", "y_hint": 204},
                            {"label": "4. FORMA DE PAGO", "value": "", "y_hint": 217},
                            {"label": "5. CONTRATO VINCULADO", "value": "", "y_hint": 230},
                            {"label": "6. CONSENTIMIENTOS PARA EL TRATAMIENTO DE LOS DATOS DEL/DE LOS TITULAR/ES", "value": "", "y_hint": 243},
                        ],
                    },
                ],
            },
            {
                "type": "section",
                "id": "seccion_c_generales",
                "title": "C. CONDICIONES GENERALES. ¿Qué regulan estas condiciones?",
                "y_hint": 272,
                "children": [
                    {
                        "type": "free_text_list",
                        "id": "generales_items",
                        "title": "Condiciones Generales (1-22)",
                        "items": [
                            {"label": "1. Objeto.", "value": "¿En qué consiste este contrato?", "y_hint": 295},
                            {"label": "2. Duración de este contrato de préstamo y desistimiento.", "value": "¿Cuánto tiempo dura el contrato? ¿Cuándo y cómo puede Usted desistir (renunciar) de este contrato?", "y_hint": 308},
                            {"label": "3. Cálculo de las cuotas.", "value": "¿Cómo se calculan las cuotas de amortización (devolución) del capital prestado más el pago de intereses?", "y_hint": 336},
                            {"label": "4. TIN -Tipo de Interés Nominal- (también denominado \"Interés Ordinario\").", "value": "¿Qué es el Tipo de Interés Nominal (TIN)?", "y_hint": 363},
                            {"label": "5. Contrato con intereses bonificados.", "value": "¿Qué significa que estén bonificados?", "y_hint": 390},
                            {"label": "6. TAE (Tasa Anual Equivalente).", "value": "¿Qué es y qué se incluye en la TAE?", "y_hint": 404},
                            {"label": "7. Amortización anticipada de este préstamo.", "value": "¿Puede Usted pagar anticipadamente, parcial o totalmente, este préstamo?", "y_hint": 417},
                            {"label": "8. Interés que le corresponderá pagar a Usted en caso de vencimientos o amortizaciones anticipadas de este préstamo", "value": "", "y_hint": 444},
                            {"label": "9. Forma y plazo de pago.", "value": "¿Cómo y cuándo se paga este préstamo?", "y_hint": 471},
                            {"label": "10. Interés de demora.", "value": "¿Qué ocurre si se retrasa en el pago del préstamo?", "y_hint": 485},
                            {"label": "11. Causas de resolución de este contrato.", "value": "", "y_hint": 499},
                            {"label": "12. Responsabilidades del deudor y del fiador/avalista.", "value": "¿Quién es el responsable del impago (retraso en el pago) del préstamo?", "y_hint": 512},
                            {"label": "13. Compensación por costes de cobro ante un impago.", "value": "¿Qué gastos se generan para CaixaBank Payments & Consumer cuando Usted incumple sus obligaciones de pago? ¿Cómo se aplica la compensación por costes de cobro ocasionados por un impago?", "y_hint": 539},
                            {"label": "14. Contratación de un seguro.", "value": "", "y_hint": 580},
                            {"label": "15. Contrato vinculado.", "value": "¿Qué significa tener un contrato vinculado?", "y_hint": 594},
                            {"label": "16. Ley aplicable a este contrato.", "value": "", "y_hint": 607},
                            {"label": "17. Domicilio y comunicaciones.", "value": "¿Cómo nos comunicaremos con Usted?", "y_hint": 621},
                            {"label": "18. Quejas y reclamaciones.", "value": "¿Cómo puede hacernos llegar sus quejas y reclamaciones?", "y_hint": 634},
                            {"label": "19. Acción judicial.", "value": "¿Cómo determinaremos la deuda si vamos a juicio?", "y_hint": 648},
                            {"label": "20. Cesión.", "value": "", "y_hint": 662},
                            {"label": "21. Tratamiento de datos de carácter personal.", "value": "¿Cómo trataremos sus datos?", "y_hint": 675},
                            {"label": "22. Políticas de sanciones, prevención de blanqueo y lucha contra el fraude.", "value": "", "y_hint": 689},
                        ],
                    },
                ],
            },
            {
                "type": "kv_leaf",
                "id": "anexo",
                "label": "ANEXO: CUADRO DE AMORTIZACIÓN",
                "value": "",
                "y_hint": 720,
            },
        ],
    },
]
