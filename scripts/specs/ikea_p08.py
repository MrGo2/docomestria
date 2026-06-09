"""Golden structure spec for CONTRATO IKEA.pdf page 8.

Consent matrix for data treatment (4 SI/NO decisions, all NO X selected).
Includes signature placeholder at bottom.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO IKEA.pdf"
PAGE = 8

META = {
    "document_type": "Contrato de cuenta de crédito con o sin Tarjeta IKEA (CaixaBank Payments & Consumer)",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_ikea_consent_matrix_si_no",
        "caixabank_ikea_consent_all_no_selected",
        "caixabank_ikea_signature_block_at_bottom",
        "caixabank_ikea_document_mod_reference",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "tratamiento_datos",
        "title": "TRATAMIENTO DE LOS DATOS DEL TITULAR",
        "y_hint": 87,
        "children": [
            {
                "type": "section",
                "id": "resumen_autorizaciones",
                "title": "Resumen de autorizaciones para el tratamiento de datos basados en el consentimiento",
                "y_hint": 127,
                "children": [
                    {
                        "type": "kv_group",
                        "id": "consentimientos_titular",
                        "pairs": [
                            {
                                "label": "Personalización de la oferta de productos y servicios según el análisis de sus datos",
                                "value": "NO",
                                "y_hint": 233,
                            },
                            {
                                "label": "Comunicación de la oferta de productos y servicios — Por aplicaciones móviles, entornos digitales y canales electrónicos",
                                "value": "NO",
                                "y_hint": 329,
                            },
                            {
                                "label": "Comunicación de la oferta de productos y servicios — Por teléfono",
                                "value": "NO",
                                "y_hint": 344,
                            },
                            {
                                "label": "Comunicación de la oferta de productos y servicios — Por carta",
                                "value": "NO",
                                "y_hint": 360,
                            },
                            {
                                "label": "Cesión de sus datos a otras empresas para la remisión de ofertas de productos y servicios",
                                "value": "NO",
                                "y_hint": 441,
                            },
                        ],
                    },
                ],
            },
            {
                "type": "kv_group",
                "id": "firma_block",
                "pairs": [
                    {"label": "Firma del Titular", "value": "", "y_hint": 748},
                    {"label": "P. p.", "value": "", "y_hint": 751},
                    {"label": "Dirección Comercial", "value": "", "y_hint": 810},
                    {
                        "label": "Código de documento",
                        "value": "020250227027091300000000000000010024",
                        "y_hint": 796,
                    },
                    {
                        "label": "Mod. documento",
                        "value": "MOD. (M) 006.PSCC.I.720 (12) - 28 de octubre de 2024",
                        "y_hint": 804,
                    },
                ],
            },
        ],
    },
]
