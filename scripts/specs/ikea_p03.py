"""Golden structure spec for CONTRATO IKEA.pdf page 3.

Dense form continuation: datos personales (rest), datos profesionales, tarjeta adicional.
4-column layout (label1|val1|label2|val2) modelled as kv_groups (one per visual row).
Checkboxes: only the selected option is recorded as value; unchecked = empty.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO IKEA.pdf"
PAGE = 3

META = {
    "document_type": "Contrato de cuenta de crédito con o sin Tarjeta IKEA (CaixaBank Payments & Consumer)",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_ikea_dense_4col_form",
        "caixabank_ikea_checkbox_selected_value",
        "caixabank_ikea_empty_form_fields",
        "caixabank_ikea_signature_placeholder_empty",
        "caixabank_ikea_multi_line_field_label",
    ],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "datos_personales_cont",
        "title": "Datos personales del titular (continuación)",
        "y_hint": 89,
        "children": [
            {
                "type": "kv_group",
                "id": "fila_nif_cuenta",
                "pairs": [
                    {"label": "NIF", "value": "45337936Z", "y_hint": 89},
                    {
                        "label": "Cuenta corriente asociada informada en el contrato",
                        "value": "ES04 2100 3986 1101 0064 4291",
                        "y_hint": 97,
                    },
                ],
            },
            {
                "type": "kv_group",
                "id": "fila_telefono_email",
                "pairs": [
                    {"label": "Teléfono", "value": "685723443", "y_hint": 134},
                    {"label": "E-mail", "value": "SORAYAGANAZA25@GMAIL.COM", "y_hint": 134},
                ],
            },
            {
                "type": "kv_group",
                "id": "fila_nacionalidad_fecha",
                "pairs": [
                    {"label": "Nacionalidad", "value": "ESPAÑOLA", "y_hint": 169},
                    {"label": "Fecha de nacimiento", "value": "10/01/96", "y_hint": 169},
                ],
            },
            {
                "type": "kv_group",
                "id": "fila_sexo_personas",
                "pairs": [
                    {"label": "Sexo", "value": "Mujer", "y_hint": 217},
                    {"label": "Personas a su cargo", "value": "0", "y_hint": 204},
                ],
            },
            {
                "type": "kv_group",
                "id": "fila_estado_vivienda",
                "pairs": [
                    {"label": "Estado civil", "value": "Soltero/a", "y_hint": 249},
                    {"label": "Vivienda", "value": "", "y_hint": 254},
                ],
            },
            {
                "type": "kv_leaf",
                "id": "tarjeta_credito",
                "label": "Tarjeta de crédito",
                "value": "",
                "y_hint": 301,
            },
        ],
    },
    {
        "type": "section",
        "id": "datos_profesionales",
        "title": "DATOS PROFESIONALES DEL TITULAR",
        "y_hint": 328,
        "children": [
            {
                "type": "kv_leaf",
                "id": "nombre_empresa",
                "label": "Nombre empresa",
                "value": "",
                "y_hint": 352,
            },
            {
                "type": "kv_leaf",
                "id": "domicilio_empresa",
                "label": "Domicilio empresa",
                "value": "11500 CADIZ",
                "y_hint": 397,
            },
            {
                "type": "kv_leaf",
                "id": "actividad",
                "label": "Actividad",
                "value": "",
                "y_hint": 421,
            },
            {
                "type": "kv_group",
                "id": "fila_telefono_fecha_pagas",
                "pairs": [
                    {"label": "Teléfono", "value": "", "y_hint": 456},
                    {"label": "Fecha de ingreso", "value": "", "y_hint": 456},
                    {"label": "Nº de pagas", "value": "12", "y_hint": 456},
                ],
            },
            {
                "type": "kv_group",
                "id": "fila_cuenta_ajena_ingresos",
                "pairs": [
                    {"label": "Por cuenta ajena", "value": "", "y_hint": 507},
                    {"label": "Importe ingresos brutos anuales", "value": "", "y_hint": 497},
                ],
            },
        ],
    },
    {
        "type": "section",
        "id": "tarjeta_adicional",
        "title": "SOLICITUD DE TARJETA ADICIONAL: DATOS DEL BENEFICIARIO",
        "y_hint": 554,
        "children": [
            {
                "type": "kv_leaf",
                "id": "beneficiario_nombre",
                "label": "Nombre y apellidos",
                "value": "",
                "y_hint": 579,
            },
            {
                "type": "kv_group",
                "id": "fila_nif_fecha_benef",
                "pairs": [
                    {"label": "N.I.F.", "value": "", "y_hint": 613},
                    {"label": "Fecha de nacimiento", "value": "", "y_hint": 613},
                ],
            },
            {
                "type": "kv_group",
                "id": "fila_sexo_parentesco_benef",
                "pairs": [
                    {"label": "Sexo", "value": "", "y_hint": 652},
                    {"label": "Parentesco con el titular", "value": "", "y_hint": 649},
                ],
            },
            {
                "type": "kv_leaf",
                "id": "firma_beneficiario",
                "label": "Firma del Beneficiario",
                "value": "",
                "y_hint": 705,
            },
        ],
    },
]
