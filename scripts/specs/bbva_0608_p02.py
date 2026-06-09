"""Golden structure spec for BBVA_0608-01491495_DOC2_CONTRATO.pdf page 2."""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/AZUREDOCUI/5_Example/BBVA_0608-01491495_DOC2_CONTRATO.pdf"
PAGE = 2

META = {
    "document_type": "Contrato de Préstamo Personal BBVA",
    "annotator": "codex",
    "covers_cases": ["bbva_loan_titulares", "bbva_loan_domicilio"],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "identificacion_partes",
        "title": "IDENTIFICACIÓN DE LAS PARTES CONTRATANTES",
        "y_hint": 119,
        "children": [
            {
                "type": "section",
                "id": "titulares",
                "title": "TITULARES",
                "y_hint": 176,
                "children": [
                    {
                        "type": "table",
                        "id": "sus_datos_personales",
                        "title": "Sus Datos Personales",
                        "y_hint": 206,
                        "columns": [
                            {"id": "label", "label": "Sus Datos Personales", "type": "text"},
                            {"id": "value", "label": "Valor", "type": "text"},
                        ],
                        "rows": [
                            {"label": ("Primer apellido", 230), "value": ("PRIETO", 229)},
                            {"label": ("Segundo apellido", 245), "value": ("ALVAREZ", 245)},
                            {"label": ("Nombre", 259), "value": ("JULIA", 259)},
                            {"label": ("NIF", 274), "value": ("011075308A", 274)},
                        ],
                    },
                    {
                        "type": "table",
                        "id": "su_domicilio",
                        "title": "Su Domicilio",
                        "y_hint": 298,
                        "columns": [
                            {"id": "label", "label": "Su Domicilio", "type": "text"},
                            {"id": "value", "label": "Valor", "type": "text"},
                        ],
                        "rows": [
                            {"label": ("Domicilio fiscal", 312), "value": ("CENERA, 42", 313)},
                            {"label": ("Código postal", 341), "value": ("33600", 341)},
                            {"label": ("Plaza", 355), "value": ("MIERES DEL CAMINO", 355)},
                        ],
                    },
                ],
            }
        ],
    }
]
