"""Golden structure spec for LABORAL .pdf page 1.

This is pure data. The library `docomestria.golden.GoldenBuilder` does the
engine-linking and writes the JSON.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/AZUREDOCUI/1_Example/LABORAL .pdf"
PAGE = 1

META = {
    "document_type": "Consulta TGSS situacion",
    "annotator": "codex",
    "covers_cases": ["laboral_datos_peticion", "laboral_respuesta", "laboral_situaciones"],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "consulta_tgss_situacion",
        "title": "Consulta TGSS situacion",
        "y_hint": 52,
        "children": [
            {
                "type": "table",
                "id": "datos_peticion",
                "title": "Datos Petición",
                "y_hint": 113,
                "columns": [
                    {"id": "label", "label": "Datos Petición", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {"label": ("Nº Procedimiento:", 134), "value": ("987-15", 134)},
                    {"label": ("Nº Documento:", 154), "value": ("X6573514E", 154)},
                    {"label": ("Fecha de emisión:", 174), "value": ("17 d’abr. 2026 17:14", 174)},
                ],
            },
            {
                "type": "table",
                "id": "respuesta",
                "title": "Respuesta",
                "y_hint": 203,
                "columns": [
                    {"id": "label", "label": "Respuesta", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {"label": ("Titular:", 224), "value": ("GHEORGHE ADRIAN OPREA ---", 224)},
                    {"label": ("Nº Seguridad Social:", 244), "value": ("341005311371", 244)},
                    {"label": ("Situación actual:", 264), "value": ("BAJA", 264)},
                    {"label": ("Fecha Situación:", 284), "value": ("31.05.2019", 284)},
                ],
            },
            {
                "type": "table",
                "id": "situaciones",
                "title": "Situaciones",
                "y_hint": 304,
                "columns": [
                    {"id": "label", "label": "Situaciones", "type": "text"},
                    {"id": "value", "label": "Valor", "type": "text"},
                ],
                "rows": [
                    {"label": ("CCC:", 324), "value": ("", 324)},
                    {
                        "label": ("Razón Social/Convenio/Régimen:", 353),
                        "value": ("RGIMEN ESPECIAL TRABAJADORES AUTNOMOS", 347),
                    },
                    {
                        "label": ("NIF/CIF - Domicilio de Empresa:", 380),
                        "value": ("No Consta", 374),
                    },
                    {"label": ("Fecha Alta:", 398), "value": ("10.04.2018", 398)},
                    {"label": ("Fecha Efecto:", 418), "value": ("10.04.2018", 418)},
                    {"label": ("Tipo Contrato:", 438), "value": ("", 438)},
                    {"label": ("Coeficiente Tiempo parcial:", 458), "value": ("0", 458)},
                    {"label": ("Grupo Cotización:", 478), "value": ("", 478)},
                ],
            },
        ],
    }
]
