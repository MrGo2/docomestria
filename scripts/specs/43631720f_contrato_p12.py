"""Golden structure spec for 43631720F_CONTRATO.pdf page 12.

CaixaBank SEPA direct debit order (Orden de Domiciliación de Adeudo Directo SEPA):
prose preamble, Datos del deudor table, Datos del acreedor table, relación subyacente
row, signature block, and sidebar/footer noise.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _patterns import condiciones_table

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/43631720F_CONTRATO.pdf"
PAGE = 12

META = {
    "document_type": "sepa_direct_debit_order",
    "annotator": "scaffolder",
    "covers_cases": [
        "page_banner_noise",
        "label_value_table_2col",
        "single_row_table",
        "prose_preamble",
        "signature_placeholder",
        "sidebar_logalty_noise",
    ],
}


STRUCTURE = [
    # --- Page banner (top-right title block) -> noise, not a section ---
    {
        "type": "noise",
        "id": "banner_titulo",
        "text": "SOLICITUD-CONTRATO DE FINANCIACIÓN ORDEN DE DOMICILIACIÓN DE ADEUDO DIRECTO SEPA",
        "kind": "watermark",
        "y_hint": 48.8,
    },

    # --- Header strip: Lugar / Fecha / Referencia ---
    {
        "type": "kv_group",
        "id": "cabecera",
        "pairs": [
            {"label": "Lugar", "value": "GIRONA", "y_hint": 89.0, "x_hint": 25.6},
            {"label": "Fecha", "value": "24-09-2019", "y_hint": 88.8, "x_hint": 235.4},
            {"label": "Referencia", "value": "20190923126609201", "y_hint": 84.0, "x_hint": 339.4},
        ],
    },

    # --- Prose preamble (SEPA mandate explanatory text) ---
    {
        "type": "prose_block",
        "id": "preambulo_sepa",
        "label": "Preámbulo orden de domiciliación",
        "text": (
            "El número de la orden de domiciliación coincide con el de la "
            "solicitud/contrato de financiación al que afectará. "
            "Mediante la firma de esta orden de domiciliación, el deudor autoriza a "
            "CaixaBank Payments & Consumer, E.F.C., E.P., S.A.U. (en adelante CaixaBank "
            "Payments & Consumer) a enviar instrucciones a dicha entidad del deudor para "
            "adeudar su cuenta y a la entidad para efectuar los adeudos en su cuenta "
            "siguiendo las instrucciones de CaixaBank Payments & Consumer. "
            "Como parte de sus derechos, el deudor está legitimado al reembolso por su "
            "entidad, en los términos y condiciones del contrato suscrito con la misma. "
            "La solicitud de reembolso deberá efectuarse dentro de las ocho semanas que "
            "siguen a la fecha de adeudo en cuenta."
        ),
        "y_hint": 108.4,
    },

    # --- Datos del deudor (5-row label/value table) ---
    {
        "type": "section",
        "id": "datos_deudor",
        "title": "Datos del deudor",
        "y_hint": 187.3,
        "children": [
            condiciones_table(
                "datos_deudor_tabla", "Datos del deudor", 217.8,
                [
                    ("Su nombre", 217.8, "EVA LINARES REBOLLO", 219.5),
                    ("Su dirección", 237.0, "GARRINADA,36 PISO 2", 238.7),
                    ("Código postal y Ciudad", 255.9, "17800 OLOT", 257.7),
                    ("País", 275.1, "ESPAÑA", 276.9),
                    ("Su número de cuenta*", 294.3, "ES90 2100 3724 1321 0049 6694", 296.0),
                ],
            ),
        ],
    },

    # --- Footnote about the account ---
    {
        "type": "prose_block",
        "id": "nota_cuenta",
        "label": "Nota cuenta",
        "text": (
            "* Esta cuenta complementa y, si es el caso, sustituye a la indicada en las "
            "Condiciones Particulares de la Solicitud/Contrato de financiación."
        ),
        "y_hint": 313.2,
    },

    # --- Datos del acreedor (6-row label/value table) ---
    {
        "type": "section",
        "id": "datos_acreedor",
        "title": "Datos del acreedor",
        "y_hint": 336.3,
        "children": [
            condiciones_table(
                "datos_acreedor_tabla", "Datos del acreedor", 366.9,
                [
                    ("Nombre del acreedor", 366.9, "CaixaBank Payments & Consumer, E.F.C., E.P., S.A.U.", 365.9),
                    ("Identificador del acreedor", 385.8, "A-08980153", 385.8),
                    ("Nombre de la calle y número", 405.0, "C/ Caleruega 102", 405.0),
                    ("Código postal y Ciudad", 424.2, "28033 Madrid", 424.2),
                    ("País", 443.4, "España", 443.4),
                    ("Tipo de pago", 462.3, "Pago recurrente", 462.3),
                ],
            ),
        ],
    },

    # --- Información sobre la relación subyacente (single-row table) ---
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
                "value": "43631720F",
                "y_hint": 521.4,
            },
        ],
    },

    # --- Localidad / Fecha de firma ---
    {
        "type": "kv_group",
        "id": "firma_lugar_fecha",
        "pairs": [
            {"label": "Localidad de firma", "value": "GIRONA", "y_hint": 546.9, "x_hint": 29.5},
            {"label": "Fecha", "value": "24-09-2019", "y_hint": 546.9, "x_hint": 243.8},
        ],
    },

    # --- Signature block ---
    {
        "type": "signature_placeholder",
        "id": "firma_deudor",
        "label": "Firma del deudor",
        "value": "",
        "y_hint": 575.1,
    },

    # --- Nota footer ---
    {
        "type": "noise",
        "id": "nota_derechos",
        "text": "Nota: Puede obtener información adicional sobre sus derechos en su entidad financiera.",
        "kind": "sidebar",
        "y_hint": 661.5,
    },

    # --- Footer left ---
    {
        "type": "noise",
        "id": "footer_uso_exclusivo",
        "text": "Documento de uso exclusivo del acreedor.",
        "kind": "sidebar",
        "y_hint": 784.5,
    },

    # --- Footer right (modelo) ---
    {
        "type": "noise",
        "id": "footer_modelo",
        "text": "MOD. (M) 006-720.0085-84 (04) - 17 de julio de 2019",
        "kind": "sidebar",
        "y_hint": 784.5,
    },

    # --- Logalty sidebar metadata (rotated right margin) ---
    {
        "type": "noise",
        "id": "sidebar_logalty",
        "text": "Logalty Guid: 001001-0001-000000036424941.par - Date: 2019/09/24 T 20:10:19 CEST +0200 - Pages: 12/22",
        "kind": "logalty_metadata",
        "y_hint": 269.5,
    },

    # --- Firma Logalty tag ---
    {
        "type": "noise",
        "id": "firma_logalty_tag",
        "text": "@$FIRMALOGALTYTAG{<firmante><id>1-34</id></firmante>}$@",
        "kind": "logalty_metadata",
        "y_hint": 650.7,
    },
]
