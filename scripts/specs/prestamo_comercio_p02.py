"""Golden structure spec for CONTRATO PRESTAMO COMERCIO 2.pdf page 2.

A. INTERVINIENTES Y DATOS GENERALES — Form with 4 person blocks:
- DEL Titular 1 (populated: SPIRIEON SOLCAN / ADRIAN / X7891505K / TOLEDO ...)
- DEL Titular 2 (all empty)
- DEL Avalista/Fiador 1 (all empty)
- DEL Avalista/Fiador 2 (all empty)

Each block has ~25 fields laid out as 2-4 columns per row. Modelled as kv_groups
collapsed per visual row to preserve x-axis adjacency context.
"""

PDF = "/Users/carlos/Edelwyss/Projects/docomestria/Dataset/CONTRATO PRESTAMO COMERCIO 2.pdf"
PAGE = 2

META = {
    "document_type": "Contrato de préstamo CaixaBank Payments & Consumer",
    "annotator": "codex",
    "covers_cases": [
        "caixabank_prestamo_4_person_blocks_form",
        "caixabank_prestamo_titular_populated",
        "caixabank_prestamo_3_persons_empty",
        "caixabank_prestamo_intro_prose_party_definitions",
    ],
}


def _apply_overrides(pairs, overrides):
    """Patcher-injected helper: mutates pair dicts in place based on label match.

    overrides: dict mapping label -> dict of fields to set/override.
    """
    if not overrides:
        return pairs
    out = []
    for p in pairs:
        lbl = p.get("label")
        if lbl in overrides:
            merged = dict(p)
            merged.update(overrides[lbl])
            out.append(merged)
        else:
            out.append(p)
    return out


def _block_pairs(y_base, *,
                 apellidos="", nombre="", nif="", nacionalidad="",
                 fecha_const="", codigo_cnae="", n_empleados="",
                 descripcion_sector="", inscrita_en="",
                 domicilio="", numero="", piso="", puerta="",
                 poblacion="", cp="", tel_fijo="", tel_movil="",
                 correo="", sexo="", estado_civil="", fecha_nac="",
                 personas_cargo="", sit_viv="", antig_viv="", gastos_viv="", otros_cred="",
                 situacion_lab="", profesion="", cargo="", importe_ingr="", antig_empresa="",
                 nombre_emp="", actividad_emp="", tel_emp=""):
    """Generate the standard 12-row pair set for a person block."""
    return [
        {"label": "Apellidos", "value": apellidos, "y_hint": y_base + 13},
        {"label": "Nombre/Denominación", "value": nombre, "y_hint": y_base + 13},
        {"label": "NIF/CIF", "value": nif, "y_hint": y_base + 27},
        {"label": "Nacionalidad", "value": nacionalidad, "y_hint": y_base + 27},
        {"label": "Fecha de constitución", "value": fecha_const, "y_hint": y_base + 27},
        {"label": "Código CNAE", "value": codigo_cnae, "y_hint": y_base + 27},
        {"label": "Nº empleados", "value": n_empleados, "y_hint": y_base + 27},
        {"label": "Descripción sector actividad", "value": descripcion_sector, "y_hint": y_base + 41},
        {"label": "Inscrita en", "value": inscrita_en, "y_hint": y_base + 41},
        {"label": "Domicilio", "value": domicilio, "y_hint": y_base + 55},
        {"label": "Nº", "value": numero, "y_hint": y_base + 55},
        {"label": "Piso", "value": piso, "y_hint": y_base + 55},
        {"label": "Puerta", "value": puerta, "y_hint": y_base + 55},
        {"label": "Población", "value": poblacion, "y_hint": y_base + 69},
        {"label": "C.P.", "value": cp, "y_hint": y_base + 69},
        {"label": "Teléfono fijo", "value": tel_fijo, "y_hint": y_base + 69},
        {"label": "Teléfono móvil", "value": tel_movil, "y_hint": y_base + 69},
        {"label": "Correo electrónico", "value": correo, "y_hint": y_base + 83},
        {"label": "Sexo", "value": sexo, "y_hint": y_base + 83},
        {"label": "Estado civil", "value": estado_civil, "y_hint": y_base + 83},
        {"label": "Fecha de nacimiento", "value": fecha_nac, "y_hint": y_base + 83},
        {"label": "Personas a su cargo", "value": personas_cargo, "y_hint": y_base + 97},
        {"label": "Sit. viv.", "value": sit_viv, "y_hint": y_base + 97},
        {"label": "Antigüedad viv.", "value": antig_viv, "y_hint": y_base + 97},
        {"label": "Gastos vivienda", "value": gastos_viv, "y_hint": y_base + 97},
        {"label": "Otros créditos", "value": otros_cred, "y_hint": y_base + 97},
        {"label": "Situación laboral", "value": situacion_lab, "y_hint": y_base + 111},
        {"label": "Profesión", "value": profesion, "y_hint": y_base + 111},
        {"label": "Cargo", "value": cargo, "y_hint": y_base + 111},
        {"label": "Importe ingresos", "value": importe_ingr, "y_hint": y_base + 111},
        {"label": "Antigüedad en la empresa", "value": antig_empresa, "y_hint": y_base + 111},
        {"label": "Nombre empresa", "value": nombre_emp, "y_hint": y_base + 125},
        {"label": "Actividad empresa", "value": actividad_emp, "y_hint": y_base + 125},
        {"label": "Teléfono empresa", "value": tel_emp, "y_hint": y_base + 125},
    ]


STRUCTURE = [
    {
        "type": "section",
        "id": "intervinientes",
        "title": "A. INTERVINIENTES Y DATOS GENERALES",
        "y_hint": 92,
        "children": [
            {
                "type": "section",
                "id": "datos_personales_profesionales",
                "title": "DATOS PERSONALES Y PROFESIONALES DEL/DE LOS TITULAR/ES Y AVALISTA/S/FIADOR/ES, EN CASO DE HABERLO/S",
                "y_hint": 180,
                "children": [
                    {
                        "type": "kv_group",
                        "id": "titular_1",
                        "pairs": _apply_overrides(_block_pairs(
                            y_base=214,
                            apellidos="SPIRIEON SOLCAN",
                            nombre="ADRIAN",
                            nif="X7891505K",
                            nacionalidad="UNION EUROPEA",
                            n_empleados="0",
                            domicilio="CL BAYEU",
                            numero="10",
                            poblacion="TOLEDO",
                            cp="45190",
                            tel_fijo="634673967",
                            correo="NANI198731@HOTMAIL.COM",
                            sexo="H",
                            fecha_nac="12/12/1984",
                            personas_cargo="0",
                            gastos_viv="0,00",
                            otros_cred="0,00",
                            importe_ingr="0,00",
                        ), {
    "Nº empleados": {"x_hint": 505.0},
    "Sexo": {"x_hint": 314.3},
    "Otros créditos": {"x_hint": 557.0, "label_x_hint": 482.7},
}),
                    },
                    {
                        "type": "kv_group",
                        "id": "titular_2",
                        "pairs": _block_pairs(y_base=353),
                    },
                    {
                        "type": "kv_group",
                        "id": "avalista_fiador_1",
                        "pairs": _block_pairs(y_base=517),
                    },
                    {
                        "type": "kv_group",
                        "id": "avalista_fiador_2",
                        "pairs": _block_pairs(y_base=656),
                    },
                ],
            },
        ],
    },
]
