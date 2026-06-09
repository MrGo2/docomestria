"""Golden structure spec for BBVA_0608-01491495_DOC2_CONTRATO.pdf page 1."""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/AZUREDOCUI/5_Example/BBVA_0608-01491495_DOC2_CONTRATO.pdf"
PAGE = 1

META = {
    "document_type": "Contrato de Préstamo Personal BBVA",
    "annotator": "codex",
    "covers_cases": ["bbva_loan_cover_no_kv"],
}


STRUCTURE = [
    {
        "type": "section",
        "id": "cover_title",
        "title": "Contrato de Préstamo Personal",
        "y_hint": 397,
        "children": [],
    },
    {
        "type": "section",
        "id": "contract_parts",
        "title": "El Contrato está compuesto por cinco partes:",
        "y_hint": 617,
        "children": [],
    },
]
