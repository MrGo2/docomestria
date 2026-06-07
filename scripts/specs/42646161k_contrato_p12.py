"""Golden structure spec for 42646161K_CONTRATO.pdf page 12.

CaixaBank Payments & Consumer SEPA direct-debit mandate (ORDEN DE
DOMICILIACIÓN DE ADEUDO DIRECTO SEPA): debtor data table, creditor data
table, underlying-relation KV, signature placeholder. Walker-compatible types.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/42646161K_CONTRATO.pdf"
PAGE = 12

META = {
    "document_type": "sepa_direct_debit_mandate",
    "annotator": "scaffolder",
    "covers_cases": [
        "sepa_mandate_header_kv",
        "debtor_data_2col_table",
        "creditor_data_2col_table",
        "underlying_relation_kv",
        "signature_placeholder",
        "rotated_sidebar_noise",
    ],
}


STRUCTURE = [
    # --- Page banner (giant title block at top) -> noise ---
    {
        "type": "noise",
        "id": "banner_solicitud_contrato",
        "text": "SOLICITUD-CONTRATO DE FINANCIACIÓN",
        "kind": "watermark",
        "y_hint": 48.8,
    },
    {
        "type": "noise",
        "id": "banner_orden_domiciliacion",
        "text": "ORDEN DE DOMICILIACIÓN DE ADEUDO DIRECTO SEPA",
        "kind": "watermark",
        "y_hint": 59.0,
    },

    # --- Header row: Lugar / Fecha / Referencia ---
    {
        "type": "kv_group",
        "id": "cabecera_orden",
        "pairs": [
            {"label": "Lugar", "value": "TELDE", "y_hint": 89.0, "x_hint": 25.6},
            {"label": "Fecha", "value": "27-01-2020", "y_hint": 88.8, "x_hint": 235.4},
            {"label": "Referencia", "value": "20200145011529801", "y_hint": 84.0, "x_hint": 339.4},
        ],
    },

    # --- Intro / legal prose ---
    {
        "type": "prose_block",
        "id": "texto_orden_domiciliacion",
        "label": "Términos de la orden de domiciliación",
        "text": (
            "El número de la orden de domiciliación coincide con el de la "
            "solicitud/contrato de financiación al que afectará. "
            "Mediante la firma de esta orden de domiciliación, el deudor autoriza "
            "a CaixaBank Payments & Consumer, E.F.C., E.P., S.A.U. (en adelante "
            "CaixaBank Payments & Consumer) a enviar instrucciones a dicha entidad "
            "del deudor para adeudar su cuenta y a la entidad para efectuar los "
            "adeudos en su cuenta siguiendo las instrucciones de CaixaBank "
            "Payments & Consumer. "
            "Como parte de sus derechos, el deudor está legitimado al reembolso "
            "por su entidad, en los términos y condiciones del contrato suscrito "
            "con la misma. La solicitud de reembolso deberá efectuarse dentro de "
            "las ocho semanas que siguen a la fecha de adeudo en cuenta."
        ),
        "y_hint": 108.4,
    },

    # --- Datos del deudor ---
    {
        "type": "section",
        "id": "datos_deudor",
        "title": "Datos del deudor",
        "y_hint": 187.3,
        "children": [
            {
                "type": "table",
                "id": "datos_deudor_tabla",
                "title": "Datos del deudor",
                "y_hint": 217.8,
                "columns": [
                    {"id": "label", "label": "Campo", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {"label": ("Su nombre", 217.8), "value": ("JUAN MARRERO GARCIA", 219.5)},
                    {"label": ("Su dirección", 237.0), "value": ("JULIAN ROMERO BRIONES,24 PISO 2 - D", 238.7)},
                    {"label": ("Código postal y Ciudad", 255.9), "value": ("35001 PALMAS DE GRAN CANARIA <LAS>", 257.7)},
                    {"label": ("País", 275.1), "value": ("ESPAÑA", 276.9)},
                    {"label": ("Su número de cuenta*", 294.3), "value": ("ES34 0049 1252 5521 9030 3887", 296.0)},
                ],
            },
            {
                "type": "prose_block",
                "id": "nota_cuenta",
                "label": "Nota cuenta",
                "text": (
                    "* Esta cuenta complementa y, si es el caso, sustituye a la "
                    "indicada en las Condiciones Particulares de la Solicitud/Contrato "
                    "de financiación."
                ),
                "y_hint": 313.2,
            },
        ],
    },

    # --- Datos del acreedor ---
    {
        "type": "section",
        "id": "datos_acreedor",
        "title": "Datos del acreedor",
        "y_hint": 336.3,
        "children": [
            {
                "type": "table",
                "id": "datos_acreedor_tabla",
                "title": "Datos del acreedor",
                "y_hint": 366.9,
                "columns": [
                    {"id": "label", "label": "Campo", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {"label": ("Nombre del acreedor", 366.9), "value": ("CaixaBank Payments & Consumer, E.F.C., E.P., S.A.U.", 365.9)},
                    {"label": ("Identificador del acreedor", 385.8), "value": ("A-08980153", 385.8, 243.8)},
                    {"label": ("Nombre de la calle y número", 405.0), "value": ("C/ Caleruega 102", 405.0, 243.8)},
                    {"label": ("Código postal y Ciudad", 424.2), "value": ("28033 Madrid", 424.2, 243.8)},
                    {"label": ("País", 443.4), "value": ("España", 443.4, 243.8)},
                    {"label": ("Tipo de pago", 462.3), "value": ("Pago recurrente", 462.3, 243.8)},
                ],
            },
        ],
    },

    # --- Información sobre la relación subyacente ---
    {
        "type": "section",
        "id": "relacion_subyacente",
        "title": "Información sobre la relación subyacente entre el acreedor y el deudor – a título meramente informativo",
        "y_hint": 489.1,
        "children": [
            {
                "type": "kv_leaf",
                "id": "codigo_identificacion_deudor",
                "label": "Código de identificación del deudor",
                "value": "42646161K",
                "y_hint": 521.4,
            },
        ],
    },

    # --- Localidad / Fecha de firma ---
    {
        "type": "kv_group",
        "id": "firma_lugar_fecha",
        "pairs": [
            {"label": "Localidad de firma", "value": "TELDE", "y_hint": 546.9, "x_hint": 29.5},
            {"label": "Fecha", "value": "27-01-2020", "y_hint": 546.9, "x_hint": 243.8},
        ],
    },

    # --- Signature box ---
    {
        "type": "signature_placeholder",
        "id": "firma_deudor",
        "label": "Firma del deudor",
        "value": "",
        "y_hint": 575.1,
    },

    # --- Nota final ---
    {
        "type": "prose_block",
        "id": "nota_derechos",
        "label": "Nota derechos",
        "text": "Nota: Puede obtener información adicional sobre sus derechos en su entidad financiera.",
        "y_hint": 661.5,
    },

    # --- Footer / sidebar noise ---
    {
        "type": "noise",
        "id": "footer_uso_exclusivo",
        "text": "Documento de uso exclusivo del acreedor.",
        "kind": "watermark",
        "y_hint": 784.5,
    },
    {
        "type": "noise",
        "id": "footer_mod",
        "text": "MOD. (M) 006-720.0085-84 (04) - 17 de julio de 2019",
        "kind": "watermark",
        "y_hint": 784.5,
    },
    {
        "type": "noise",
        "id": "sidebar_pages",
        "text": "Pages: 12/22",
        "kind": "logalty_metadata",
        "y_hint": 300.7,
    },
    {
        "type": "noise",
        "id": "sidebar_guid",
        "text": "Guid: 001001-0001-000000040208342.par",
        "kind": "logalty_metadata",
        "y_hint": 689.5,
    },
    {
        "type": "noise",
        "id": "sidebar_logalty",
        "text": "Logalty",
        "kind": "logalty_metadata",
        "y_hint": 718.3,
    },
]
