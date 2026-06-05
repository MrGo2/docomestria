"""Document family detection (capa 3.8) — DocType + per-family schema."""

from __future__ import annotations

from docomestria.structural.doctype import DocType, detect_doc_type
from docomestria.structural.schema import (
    BANKING_SCHEMA,
    LABORAL_SCHEMA,
    PATRIMONIAL_SCHEMA,
    canonical_label,
)


def test_detect_laboral_from_distinctive_labels():
    labels = [
        "Razón Social/Convenio/Régimen:",
        "Nº Seguridad Social:",
        "Situación actual:",
        "Fecha Alta:",
        "Tipo Contrato:",
    ]
    match = detect_doc_type(labels)
    assert match.doc_type is DocType.LABORAL
    assert match.confidence >= 0.7
    assert "razon social/convenio/regimen" in match.signals


def test_detect_patrimonial_from_aeat_labels():
    labels = [
        "AEAT - Consulta Percepciones:",
        "AEAT - Consulta Actividades Economicas:",
        "Lista de productos",
        "Nacionalidad:",
    ]
    match = detect_doc_type(labels)
    assert match.doc_type is DocType.PATRIMONIAL
    assert match.confidence >= 0.7


def test_detect_banking_from_bbva_credit_card_labels():
    labels = [
        "TAE",
        "Tipo Nominal Anual%",
        "Cuota",
        "Sistema de reembolso",
        "Límite de Crédito",
        "Comisión por retirada de efectivo",
    ]
    match = detect_doc_type(labels)
    assert match.doc_type is DocType.BANKING
    assert match.confidence >= 0.7


def test_detect_unknown_when_no_markers_match():
    labels = ["Some random text", "Another label", "Third one"]
    match = detect_doc_type(labels)
    assert match.doc_type is DocType.UNKNOWN
    assert match.confidence == 0.0
    assert match.signals == ()


def test_detect_handles_empty_labels():
    match = detect_doc_type([])
    assert match.doc_type is DocType.UNKNOWN


def test_detection_requires_minimum_marker_count():
    # Only ONE laboral marker — below min_hits=2 threshold.
    match = detect_doc_type(["Razón Social/Convenio/Régimen:"])
    assert match.doc_type is DocType.UNKNOWN


def test_canonical_label_default_falls_back_to_generic_schema():
    """Without a doc_type, the generic LABEL_SCHEMA wins."""
    assert canonical_label("N.I.F.") == "nif"
    assert canonical_label("Nº Procedimiento") == "procedimiento_numero"


def test_canonical_label_uses_family_schema_when_given():
    """With doc_type=BANKING, 'Nombre y apellidos' maps to titular_principal."""
    assert canonical_label("Nombre y apellidos", DocType.BANKING) == "titular_principal"
    # Generic schema still has it as nombre_apellidos.
    assert canonical_label("Nombre y apellidos") == "nombre_apellidos"


def test_canonical_label_family_specific_only_in_laboral():
    """LABORAL_SCHEMA has 'Grupo Cotización' → 'grupo_cotizacion'."""
    assert canonical_label("Grupo Cotización", DocType.LABORAL) == "grupo_cotizacion"
    # Generic schema does NOT have this key.
    assert canonical_label("Grupo Cotización") is None


def test_canonical_label_falls_through_to_generic_if_family_lacks_key():
    """A label that isn't in BANKING_SCHEMA should still resolve via LABEL_SCHEMA."""
    assert canonical_label("N.I.F.", DocType.BANKING) == "nif"


def test_canonical_label_handles_unknown_doc_type_safely():
    # DocType.UNKNOWN means: use generic schema only.
    assert canonical_label("N.I.F.", DocType.UNKNOWN) == "nif"


def test_family_schemas_are_disjoint_from_generic_keys():
    """Family schemas should hold family-specific slugs, not duplicate the
    generic LABEL_SCHEMA for shared labels — except where the slug changes."""
    # 'titular' should be in LABORAL_SCHEMA (also in generic — same slug).
    assert LABORAL_SCHEMA.get("titular") == "titular"
    # Banking remaps 'nombre y apellidos' to a banking-specific slug.
    assert BANKING_SCHEMA["nombre y apellidos"] != "nombre_apellidos"


def test_detect_doc_type_is_case_and_accent_insensitive():
    labels = [
        "RAZÓN SOCIAL/CONVENIO/RÉGIMEN",       # all caps with accents
        "Nº Seguridad Social",
    ]
    match = detect_doc_type(labels)
    assert match.doc_type is DocType.LABORAL
