"""Golden structure spec for BBVA_0539-01547731_DOC2_CONTRATO.pdf page 1.

This is pure data. The library `docomestria.golden.GoldenBuilder` does the
engine-linking and writes the JSON.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/AZUREDOCUI/3_Example/BBVA_0539-01547731_DOC2_CONTRATO.pdf"
PAGE = 1

META = {
    "document_type": "Contrato de Tarjeta BBVA",
    "annotator": "carlos",
    "covers_cases": [2, 3, 4, 5, 6, 7, 8],
}


NOTA_1 = (
    "Por las retiradas de efectivo realizadas en un cajero perteneciente a una "
    "Entidad distinta del Grupo BBVA en España en Euros, BBVA repercutirá el "
    "mismo importe de la comisión cobrada por la entidad titular del cajero a "
    "BBVA. Dicho importe será informado por la entidad titular del cajero antes "
    "de la retirada de efectivo."
)
NOTA_2 = (
    "Por las retiradas de efectivo realizadas en un cajero perteneciente a una "
    "entidad distinta del Grupo BBVA en España en Euros, BBVA repercutirá el "
    "mismo importe de la comisión cobrada por la entidad titular del cajero a "
    "BBVA. Dicho importe será informado por la entidad titular del cajero antes "
    "de la retirada de efectivo. Asimismo, BBVA le cobrará la comisión por "
    "disposición a crédito indicada para cajeros Grupo BBVA en España. Esta "
    "comisión es adicional a la de retirada de efectivo en cajeros de entidades "
    "distintas del Grupo BBVA en España."
)

STRUCTURE = [
    {"type": "section", "id": "header", "title": "Header / Metadata", "y_hint": 90,
     "children": [
        {"type": "kv_leaf", "label": "Contrato Marco — versión", "value": "0006", "y_hint": 64, "datatype": "text"},
        {"type": "kv_leaf", "label": "Documento", "value": "CONTRATO DE TARJETA DESPUES BBVA", "y_hint": 99, "datatype": "title"},
        {"type": "kv_leaf", "label": "Contrato Núm.", "value": "0182 - 0539 - 0615 - 00000028350350", "y_hint": 122, "datatype": "code"},
        {"type": "kv_leaf", "label": "Lugar", "value": "ALBERIC", "y_hint": 133, "datatype": "text"},
        {"type": "kv_leaf", "label": "Fecha", "value": "04 de Abril de 2017", "y_hint": 133, "datatype": "date"},
     ]},

    {"type": "section", "id": "titulares", "title": "Titulares", "y_hint": 146,
     "children": [
        {"type": "array", "id": "titulares_list", "title": "Titulares",
         "items": [
            {"index": 1, "filled": True, "datos_identificativos": {
                "title": "Datos Identificativos", "y_hint": 163,
                "tipo_identificacion": ("NIF PERSONA FISICA", 180),
                "nif": ("009786573G", 180),
                "nombre_apellidos": ("JULIO ALVAREZ SALGUERO", 199),
             }, "datos_operativos_tarjeta": {
                "title": "Datos Operativos de la Tarjeta", "y_hint": 220,
                "nombre_apellidos": ("JULIO ALVAREZ SALGUERO", 240),
                "limite_diario_efectivo_cajeros": ("1.000,00", 256),
                "limite_mensual_efectivo_credito_cajeros_y_oficinas": ("900,00", 290),
                "clave_restriccion": ("SIN RESTRICCIONES", 301),
             }},
            {"index": 2, "filled": False, "datos_identificativos": {
                "title": "Datos Identificativos", "y_hint": 163,
                "tipo_identificacion": (None, 180), "nif": (None, 180), "nombre_apellidos": (None, 199),
             }, "datos_operativos_tarjeta": {
                "title": "Datos Operativos de la Tarjeta", "y_hint": 220,
                "nombre_apellidos": (None, 240),
                "limite_diario_efectivo_cajeros": (None, 256),
                "limite_mensual_efectivo_credito_cajeros_y_oficinas": (None, 290),
                "clave_restriccion": (None, 301),
             }},
         ]}
     ]},

    {"type": "section", "id": "datos_operativos", "title": "Datos Operativos", "y_hint": 339,
     "children": [
        {"type": "kv_group", "pairs": [
            {"label": "Límite de Crédito", "value": "900,00", "y_hint": 351, "datatype": "amount"},
            {"label": "Importes en", "value": "EUR", "y_hint": 351, "datatype": "currency"},
            {"label": "Sistema de reembolso", "value": "TOTAL", "y_hint": 351, "datatype": "text"},
        ]}
     ]},

    {"type": "section", "id": "domiciliacion", "title": "Domiciliación", "y_hint": 358,
     "children": [
        {"type": "kv_group", "pairs": [
            {"label": "Banco", "value": "0182", "y_hint": 373, "datatype": "code"},
            {"label": "Oficina", "value": "0539", "y_hint": 373, "datatype": "code"},
            {"label": "D.C.", "value": "18", "y_hint": 373, "datatype": "code"},
            {"label": "Núm. Cuenta", "value": "0201535528", "y_hint": 373, "datatype": "account"},
        ]}
     ]},

    {"type": "section", "id": "condiciones_economicas", "title": "Condiciones económicas", "y_hint": 392,
     "children": [
        {"type": "table", "id": "cuota_anual", "title": "CUOTA ANUAL", "y_hint": 408,
         "columns": [
             {"id": "concepto", "label": "CUOTA ANUAL", "type": "text"},
             {"id": "importe", "label": "IMPORTE", "type": "amount"},
         ],
         "rows": [
             {"concepto": ("Primera Tarjeta Emitida", 426), "importe": ("40,00", 426)},
             {"concepto": ("Resto de Tarjetas", 443), "importe": ("20,00", 443)},
         ]},

        {"type": "table", "id": "comisiones_otras_operaciones", "title": "COMISIONES POR OTRAS OPERACIONES", "y_hint": 470,
         "columns": [
             {"id": "concepto", "label": "COMISIONES POR OTRAS OPERACIONES", "type": "text"},
             {"id": "importe", "label": "IMPORTE", "type": "amount"},
         ],
         "rows": [
             {"concepto": ("Por Consultas en Cajeros no pertenecientes al grupo BBVA y UE en Euros", 489), "importe": ("0,60", 492)},
             {"concepto": ("Por emisión de duplicados", 510), "importe": ("4,00", 510)},
         ]},

        {"type": "table", "id": "intereses", "title": "INTERESES", "y_hint": 520,
         "columns": [
             {"id": "concepto", "label": "INTERESES", "type": "text"},
             {"id": "tin", "label": "Tipo Nominal Anual %", "type": "percent_or_text"},
             {"id": "tae", "label": "TAE % Anual", "type": "percent_or_text"},
         ],
         "rows": [
             {"concepto": ("Pago Personalizado", 549), "tin": ("18,0000", 549), "tae": ("Detalle en cláusula", 549)},
             {"concepto": ("Cuenta de Crédito de la", 575), "tin": ("22,8000", 580), "tae": ("Detalle en cláusula", 580)},
             {"concepto": ("Pago Total", 605), "tin": ("22,8000", 615), "tae": ("Detalle en cláusula", 615)},
             {"concepto": ("Moratorio, sobre cuotas", 627), "tin": ("Detalle en", 632), "tae": None},
         ]},

        {"type": "table", "id": "comisiones_disposicion_efectivo", "title": "COMISIONES POR DISPOSICIÓN DE EFECTIVO",
         "y_hint": 408, "header_levels": 2,
         "columns": [
             {"id": "concepto", "label": "COMISIONES POR DISPOSICIÓN DE EFECTIVO", "type": "text"},
             {"id": "pct_debito",  "group": "Contra Cuenta Corriente / Ahorro (Débito)", "label": "%",      "type": "percent"},
             {"id": "min_debito",  "group": "Contra Cuenta Corriente / Ahorro (Débito)", "label": "Mínimo", "type": "amount"},
             {"id": "pct_credito", "group": "Contra Cuenta de Tarjeta de Crédito",       "label": "%",      "type": "percent"},
             {"id": "min_credito", "group": "Contra Cuenta de Tarjeta de Crédito",       "label": "Mínimo", "type": "amount"},
         ],
         "rows": [
             {"concepto": ("Cajeros Grupo BBVA en España", 448), "pct_debito": ("0,0000", 448), "min_debito": ("0,00", 448), "pct_credito": ("3,5000", 448), "min_credito": ("3,00", 448)},
             {"concepto": ("Cajeros de entidades distintas del Grupo BBVA en España", 468), "pct_debito": ({"ref": "nota_1"}, 468), "min_debito": ({"ref": "nota_1"}, 468), "pct_credito": ({"ref": "nota_2"}, 468), "min_credito": ({"ref": "nota_2"}, 468)},
             {"concepto": ("Cajeros fuera de España", 494), "pct_debito": ("4,5000", 494), "min_debito": ("3,00", 494), "pct_credito": ("5,0000", 494), "min_credito": ("3,00", 494)},
             {"concepto": ("Oficinas del Grupo BBVA en España", 514), "pct_debito": ("0,0000", 514), "min_debito": ("0,00", 514), "pct_credito": ("3,0000", 514), "min_credito": ("2,50", 514)},
             {"concepto": ("Oficinas en otras Entidades ServiRed", 530), "pct_debito": ("5,0000", 530), "min_debito": ("3,00", 530), "pct_credito": ("5,0000", 530), "min_credito": ("3,00", 530)},
             {"concepto": ("Oficinas de otras Entidades Nacionales y Paises", 546), "pct_debito": ("5,0000", 546), "min_debito": ("3,00", 546), "pct_credito": ("5,0000", 546), "min_credito": ("3,00", 546)},
             {"concepto": ("Oficinas de Entidades en el Extranjero y U.E.", 562), "pct_debito": ("5,0000", 562), "min_debito": ("3,00", 562), "pct_credito": ("5,0000", 562), "min_credito": ("3,00", 562)},
         ],
         "notes": {"nota_1": NOTA_1, "nota_2": NOTA_2},
         "notes_y_hint": 593},

        {"type": "free_text_list", "id": "otras_condiciones", "title": "Otras Condiciones", "y_hint": 670,
         "items": [
             {"label": "De apertura sobre excedido en el límite de crédito en tarjeta", "value": "3,0000 %", "y_hint": 670, "datatype": "percent"},
             {"label": "Por reclamación de posiciones vencidas", "value": "hasta un máximo de 35,00 EUR por una sola vez", "y_hint": 681, "datatype": "amount"},
             {"label": "Por utilización de la Tarjeta fuera de la Zona Euro", "value": "3,0000 %", "y_hint": 691, "datatype": "percent"},
             {"label": "Por gestión de aplazamiento de pagos", "value": "-", "y_hint": 700, "datatype": "amount"},
             {"label": "Compensación por cancelación anticipada de deuda", "value": "-", "y_hint": 710, "datatype": "percent"},
         ]},
     ]},

    {"type": "section", "id": "comisiones_traspaso_fondos",
     "title": "Comisiones por Traspaso de Fondos (Operaciones a Crédito)", "y_hint": 730,
     "children": [
        {"type": "kv_leaf", "label": "A Cuenta Personal BBVA", "value": "3,0000", "y_hint": 754, "datatype": "percent"},
     ]},
]
