"""Golden structure spec for 16815699P_CONTRATO.pdf page 1 (Datos generales del préstamo F_AS-5).

CaixaBank Payments & Consumer modelo F_AS-5 — Contrato de Préstamo de Financiación
a Comprador de Bienes Muebles. Page 1 includes comprador-prestatario data, empty
fiador slots, financiador/vendedor data, objeto a financiar (vehículo) and price
breakdown table.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/16815699P_CONTRATO.pdf"
PAGE = 1

META = {
    "document_type": "Contrato de Préstamo Financiación Comprador Bienes Muebles (CaixaBank F_AS-5)",
    "annotator": "scaffolder",
    "covers_cases": [
        "caixabank_f_as5_header",
        "comprador_prestatario_form_4col_apellidos_nombre_nif",
        "comprador_prestatario_domicilio_inline",
        "fiador_empty_form_slots",
        "financiador_caixabank_payments_consumer_block",
        "vendedor_intermediario_financiero_block",
        "objeto_financiar_vehiculo_block",
        "precio_breakdown_table_with_comisiones",
        "logalty_metadata_sidebar_noise",
        "caixabank_payments_consumer_footer_prose",
    ],
}


STRUCTURE = [
    # ----------------------------------------------------------------
    # Header (modelo + hoja + nº referencia + título)
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "encabezado",
        "title": "Encabezado modelo",
        "y_hint": 22,
        "children": [
            {
                "type": "kv_leaf",
                "id": "modelo_asnef",
                "label": "Nº Modelo",
                "value": "F_AS-5",
                "y_hint": 22,
            },
            {
                "type": "kv_leaf",
                "id": "hoja_numero",
                "label": "Hoja nº",
                "value": "1/24",
                "y_hint": 35,
            },
            {
                "type": "kv_leaf",
                "id": "nro_referencia",
                "label": "Nº",
                "value": "202405600705506",
                "y_hint": 60,
            },
            {
                "type": "kv_leaf",
                "id": "titulo_contrato",
                "label": "Título",
                "value": "CONTRATO DE PRÉSTAMO DE FINANCIACIÓN A COMPRADOR DE BIENES MUEBLES",
                "y_hint": 86,
            },
            {
                "type": "prose_block",
                "id": "modelo_dgrn_disclaimer",
                "label": "Modelo aprobado ASNEF/DGRN",
                "text": (
                    "Modelo aprobado a la ASNEF por la Dirección General de los Registros "
                    "y del Notariado (DGRN). (Resolución de 04/02/2000. Modificado por "
                    "Resoluciones de DGRN de 23/05/2006, de 29/09/2011, de 02/07/2013, "
                    "de 23/01/2014, de 07/10/2019, de 07/06/2021 y de 22/09/2022"
                ),
                "y_hint": 99,
            },
            {
                "type": "kv_leaf",
                "id": "impreso_numero",
                "label": "IMPRESO Nº",
                "value": "6249596",
                "y_hint": 145,
            },
        ],
    },

    # ----------------------------------------------------------------
    # (1) DATOS COMPRADOR-PRESTATARIO
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "comprador_prestatario",
        "title": "DATOS PERSONALES O DENOMINACIÓN SOCIAL, EN SU CASO, DEL COMPRADOR-PRESTATARIO (1)",
        "y_hint": 166,
        "children": [
            {
                "type": "kv_group",
                "id": "comprador_identidad",
                "pairs": [
                    {"label": "1er Apellido", "value": "JUSTINIANO", "y_hint": 189.6, "x_hint": 94.7},
                    {"label": "2º Apellido", "value": "JUSTINIANO", "y_hint": 189.6, "x_hint": 209.3},
                    {"label": "Nombre", "value": "LUIS FERNANDO", "y_hint": 189.6, "x_hint": 306.4},
                    {"label": "NIF/CIF", "value": "16815699P", "y_hint": 189.6, "x_hint": 444.6},
                ],
            },
            {
                "type": "kv_group",
                "id": "comprador_contacto",
                "pairs": [
                    {
                        "label": "Domicilio",
                        "value": "CL BRAVO MURILLO,20 PISO 3 - 2 - PALMAS DE GRAN CANARIA <LAS> < LAS PALMAS",
                        "y_hint": 206.0,
                    },
                    {"label": "Tel", "value": "651816977", "y_hint": 206.0, "x_hint": 485.5},
                    {"label": "Inscrita en", "value": "", "y_hint": 222.6},
                    {
                        "label": "Correo electrónico",
                        "value": "FAMILIAJUSTINIANO@HOTMAIL.COM",
                        "y_hint": 222.6,
                        "x_hint": 271.3,
                    },
                    {"label": "Y en su nombre", "value": "", "y_hint": 239.3},
                ],
            },
        ],
    },

    # ----------------------------------------------------------------
    # (2) DATOS FIADOR — empty form slots
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "fiador",
        "title": "DATOS PERSONALES O DENOMINACIÓN SOCIAL, EN SU CASO, DEL FIADOR (2)",
        "y_hint": 261.9,
        "children": [
            {
                "type": "kv_group",
                "id": "fiador_identidad",
                "pairs": [
                    {"label": "1er Apellido", "value": "", "y_hint": 273.5, "x_hint": 91.2},
                    {"label": "2º Apellido", "value": "", "y_hint": 273.5, "x_hint": 202.6},
                    {"label": "Nombre", "value": "", "y_hint": 273.5, "x_hint": 319.1},
                    {"label": "NIF/CIF", "value": "", "y_hint": 273.5, "x_hint": 439.8},
                ],
            },
            {
                "type": "kv_group",
                "id": "fiador_contacto",
                "pairs": [
                    {"label": "Domicilio", "value": "", "y_hint": 303.1},
                    {"label": "Tel", "value": "", "y_hint": 301.9, "x_hint": 398.2},
                    {"label": "Inscrita en", "value": "", "y_hint": 318.8},
                    {"label": "Correo electrónico", "value": "", "y_hint": 318.8, "x_hint": 271.3},
                    {"label": "Y en su nombre", "value": "", "y_hint": 335.2},
                ],
            },
        ],
    },

    # ----------------------------------------------------------------
    # FINANCIADOR
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "financiador",
        "title": "FINANCIADOR",
        "y_hint": 367.5,
        "children": [
            {
                "type": "kv_group",
                "id": "financiador_datos",
                "pairs": [
                    {
                        "label": "FINANCIADOR",
                        "value": "CAIXABANK PAYMENTS & CONSUMER, E.F.C., E.P., S.A.U., y en su nombre y representación D.LUIS LAGARES PUIG",
                        "y_hint": 367.5,
                    },
                    {"label": "NIF", "value": "35063208F", "y_hint": 383.9},
                    {
                        "label": "con poder otorgado ante notario de",
                        "value": "BARCELONA",
                        "y_hint": 385.1,
                        "x_hint": 116.9,
                    },
                    {
                        "label": "Notario",
                        "value": "D. TOMAS GIMENEZ DUART",
                        "y_hint": 385.1,
                        "x_hint": 368.1,
                    },
                    {"label": "con fecha", "value": "12-02-2013", "y_hint": 401.7},
                ],
            },
        ],
    },

    # ----------------------------------------------------------------
    # VENDEDOR / INTERMEDIARIO FINANCIERO
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "vendedor_intermediario",
        "title": "VENDEDOR/INTERMEDIARIO FINANCIERO",
        "y_hint": 418.6,
        "children": [
            {
                "type": "kv_group",
                "id": "vendedor_datos",
                "pairs": [
                    {
                        "label": "VENDEDOR/ INTERMEDIARIO FINANCIERO",
                        "value": "MOTOR ARI S.A.",
                        "y_hint": 418.6,
                    },
                    {
                        "label": "Observación",
                        "value": "(No interviene en este acto)",
                        "y_hint": 418.6,
                        "x_hint": 443.2,
                    },
                    {
                        "label": "Domicilio social",
                        "value": "CUZCO ,Nº 1 , 35008 LAS PALMAS",
                        "y_hint": 435.3,
                    },
                ],
            },
        ],
    },

    # ----------------------------------------------------------------
    # (3) OBJETO A FINANCIAR
    # ----------------------------------------------------------------
    {
        "type": "section",
        "id": "objeto_financiar",
        "title": "OBJETO A FINANCIAR (3)",
        "y_hint": 452.1,
        "children": [
            {
                "type": "kv_group",
                "id": "objeto_vehiculo",
                "pairs": [
                    {
                        "label": "OBJETO A FINANCIAR",
                        "value": "TODO TERRENO",
                        "y_hint": 452.1,
                        "x_hint": 27.0,
                    },
                    {"label": "Marca", "value": "NISSAN", "y_hint": 452.1, "x_hint": 280.7},
                    {"label": "Modelo", "value": "QASHQAI", "y_hint": 452.1, "x_hint": 395.4},
                    {
                        "label": "Nº fabricación o chasis",
                        "value": "SJNFFAJ11U2980564",
                        "y_hint": 468.8,
                        "x_hint": 27.0,
                    },
                    {
                        "label": "Matrícula (en su caso)",
                        "value": "3775LSK",
                        "y_hint": 468.8,
                        "x_hint": 267.1,
                    },
                ],
            },
        ],
    },

    # ----------------------------------------------------------------
    # PRICE BREAKDOWN — Precio / Desembolso / Capital / Comisiones / Seguros / Total
    # ----------------------------------------------------------------
    {
        "type": "table",
        "id": "desglose_precio",
        "title": "Desglose económico del préstamo",
        "y_hint": 495.4,
        "columns": [
            {"id": "label", "label": "Concepto", "type": "text"},
            {"id": "value", "label": "Importe (€)", "type": "text"},
        ],
        "rows": [
            {
                "label": ("Precio de compraventa (valor contado)", 495.4),
                "value": ("14.990,00", 496.7),
            },
            {
                "label": ("Desembolso inicial, (en su caso)", 516.2),
                "value": ("0,00", 516.2),
            },
            {
                "label": ("Capital inicial del préstamo.", 533.3),
                "value": ("14.990,00", 534.4),
            },
            {
                "label": ("Importe Total del Préstamo (Capital+Otros conceptos financiados)", 680.5),
                "value": ("15.588,10", 680.5),
            },
        ],
    },

    # Comisiones financiadas (row at y=572.8 with 2 label/value pairs)
    {
        "type": "section",
        "id": "comisiones_gastos",
        "title": "Espacio reservado para incluir las comisiones, gastos etc.",
        "y_hint": 556.1,
        "children": [
            {
                "type": "kv_group",
                "id": "comisiones_financiadas",
                "pairs": [
                    {
                        "label": "Financiadas: Comisión apertura",
                        "value": "598,10",
                        "y_hint": 572.8,
                        "x_hint": 240.3,
                    },
                    {
                        "label": "Financiadas: Comisión Estudio",
                        "value": "0,00",
                        "y_hint": 572.8,
                        "x_hint": 448.1,
                    },
                ],
            },
            {
                "type": "kv_group",
                "id": "comisiones_no_financiadas",
                "pairs": [
                    {
                        "label": "No Financiadas: Comisión apertura (*)",
                        "value": "",
                        "y_hint": 589.7,
                        "x_hint": 240.3,
                    },
                    {
                        "label": "No Financiadas: Comisión Estudio (**)",
                        "value": "",
                        "y_hint": 589.7,
                        "x_hint": 448.1,
                    },
                ],
            },
            {
                "type": "kv_leaf",
                "id": "asterisco_nota",
                "label": "(*) y (**)",
                "value": "",
                "y_hint": 606.3,
            },
        ],
    },

    {
        "type": "section",
        "id": "servicios_accesorios",
        "title": "Espacio reservado para Servicios accesorios relacionados (mantenimiento, seguros, etc.)",
        "y_hint": 627.6,
        "children": [
            {
                "type": "kv_group",
                "id": "seguros_costes",
                "pairs": [
                    {
                        "label": "Condicionantes: Coste del seguro mensual",
                        "value": "",
                        "y_hint": 644.2,
                        "x_hint": 294.2,
                    },
                    {
                        "label": "No Condicionantes: Coste del seguro mensual",
                        "value": "",
                        "y_hint": 661.1,
                        "x_hint": 294.2,
                    },
                ],
            },
        ],
    },

    # ----------------------------------------------------------------
    # Footer prose — Datos del financiador + REVERSO disclaimer
    # ----------------------------------------------------------------
    {
        "type": "prose_block",
        "id": "datos_financiador_footer",
        "label": "Datos del financiador (pie)",
        "text": (
            "Datos del financiador: CaixaBank Payments & Consumer, E.F.C., E.P., S.A.U., "
            "domiciliada en Avenida de Manoteras nº 20. E Madrid, CIF A-08980153. "
            "Inscrita en el Registro Mercantil de Madrid, Tomo 36.556, Folio 29, "
            "Hoja M-656.492 e inscrita co Establecimientos de Crédito del Banco de España."
        ),
        "y_hint": 759.3,
    },
    {
        "type": "prose_block",
        "id": "reverso_disclaimer",
        "label": "Reverso disclaimer",
        "text": (
            "REVERSO SÓLO APTO PARA LA IMPRESIÓN DE LAS CONDICIONES PARTICULARES "
            "CONTENIDAS EN EL B. O. E., SEGÚN RESOLUCIONES REFERI"
        ),
        "y_hint": 799.5,
    },

    # ----------------------------------------------------------------
    # Sidebar / footer Logalty metadata noise
    # ----------------------------------------------------------------
    {
        "type": "noise",
        "id": "sidebar_paginacion",
        "text": "1/29",
        "kind": "page_number",
        "y_hint": 271.9,
    },
    {
        "type": "noise",
        "id": "sidebar_pages_label",
        "text": "- Pages:",
        "kind": "logalty_metadata",
        "y_hint": 329.5,
    },
    {
        "type": "noise",
        "id": "sidebar_tz",
        "text": "+0200",
        "kind": "logalty_metadata",
        "y_hint": 339.1,
    },
    {
        "type": "noise",
        "id": "sidebar_tz_name",
        "text": "CEST",
        "kind": "logalty_metadata",
        "y_hint": 367.9,
    },
    {
        "type": "noise",
        "id": "sidebar_hora",
        "text": "20:05:47",
        "kind": "logalty_metadata",
        "y_hint": 391.9,
    },
    {
        "type": "noise",
        "id": "sidebar_t",
        "text": "T",
        "kind": "logalty_metadata",
        "y_hint": 435.1,
    },
    {
        "type": "noise",
        "id": "sidebar_date",
        "text": "Date: 2024/05/09",
        "kind": "logalty_metadata",
        "y_hint": 497.5,
    },
    {
        "type": "noise",
        "id": "sidebar_dash",
        "text": "-",
        "kind": "logalty_metadata",
        "y_hint": 526.3,
    },
    {
        "type": "noise",
        "id": "sidebar_guid",
        "text": "Guid: 001001-0001-000000124609130.par",
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
    {
        "type": "noise",
        "id": "footer_mod_code",
        "text": "MOD. (M)006-720.0313-02 (29) - 16 de abril de 2024",
        "kind": "page_number",
        "y_hint": 789.1,
    },
]
