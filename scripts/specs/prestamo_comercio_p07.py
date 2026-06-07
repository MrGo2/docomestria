"""Golden structure spec for CONTRATO PRESTAMO COMERCIO 2.pdf page 7.

- Continuation of INFORMACIÓN ESPECIALMENTE RELEVANTE prose
- 6. CONSENTIMIENTOS PARA EL TRATAMIENTO DE DATOS PERSONALES — consent matrix:
  - Personalización: TITULAR 1 SI X
  - Comunicación (3 channels): Aplicaciones SI X, Teléfono SI X, Carta NO X
  - Cesión: TITULAR 1 SI X
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO PRESTAMO COMERCIO 2.pdf"
PAGE = 7

META = {
    "document_type": "Contrato de préstamo CaixaBank Payments & Consumer",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_prestamo_consent_matrix_titular_1",
        "caixabank_prestamo_consent_mixed_si_no",
        "caixabank_prestamo_consent_three_channels_split",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "consentimientos",
        "title": "6. CONSENTIMIENTOS PARA EL TRATAMIENTO DE DATOS PERSONALES",
        "y_hint": 353,
        "children": [
            {
                "type": "section",
                "id": "resumen_autorizaciones",
                "title": "Resumen de autorizaciones para el tratamiento de datos basados en el consentimiento",
                "y_hint": 390,
                "children": [
                    {
                        "type": "kv_group",
                        "id": "consentimientos_titular_1",
                        "pairs": [
                            {
                                "label": "Personalización de la oferta de productos y servicios según el análisis de sus datos (Titular 1)",
                                "value": "SI",
                                "y_hint": 496,
                            },
                            {
                                "label": "Comunicación de la oferta de productos y servicios — Por aplicaciones móviles, entornos digitales y canales electrónicos (Titular 1)",
                                "value": "SI",
                                "y_hint": 592,
                            },
                            {
                                "label": "Comunicación de la oferta de productos y servicios — Por teléfono (Titular 1)",
                                "value": "SI",
                                "y_hint": 607,
                            },
                            {
                                "label": "Comunicación de la oferta de productos y servicios — Por carta (Titular 1)",
                                "value": "NO",
                                "y_hint": 623,
                            },
                            {
                                "label": "Cesión de sus datos a otras empresas para la remisión de ofertas de productos y servicios (Titular 1)",
                                "value": "SI",
                                "y_hint": 704,
                            },
                        ],
                    },
                ],
            },
        ],
    },
]
