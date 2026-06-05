"""Tests for capa 3.8 — schema-aware label mapping (schema.py)."""

from __future__ import annotations

from docomestria.structural.schema import (
    LABEL_SCHEMA,
    canonical_label,
    normalise_label,
)


# ---------------------------------------------------------------------------
# normalise_label
# ---------------------------------------------------------------------------


def test_normalise_lowercases():
    assert normalise_label("TITULAR") == "titular"


def test_normalise_strips_accents():
    assert normalise_label("Razón Social") == "razon social"


def test_normalise_strips_punctuation():
    assert normalise_label("N.I.F.") == "n i f"


def test_normalise_strips_colon():
    assert normalise_label("Fecha de emisión:") == "fecha de emision"


def test_normalise_collapses_whitespace():
    assert normalise_label("Nombre   y  apellidos") == "nombre y apellidos"


def test_normalise_handles_ordinal_no():
    assert normalise_label("Nº Procedimiento") == "no procedimiento"


def test_normalise_empty():
    assert normalise_label("") == ""
    assert normalise_label("   ") == ""


# ---------------------------------------------------------------------------
# canonical_label
# ---------------------------------------------------------------------------


def test_canonical_known_label_simple():
    assert canonical_label("NIF") == "nif"
    assert canonical_label("Titular") == "titular"


def test_canonical_label_with_accents():
    assert canonical_label("Razón Social") == "razon_social"
    assert canonical_label("Fecha de emisión") == "fecha_emision"


def test_canonical_label_with_colon():
    assert canonical_label("Fecha de emisión:") == "fecha_emision"
    assert canonical_label("TAE:") == "tae"


def test_canonical_label_with_ordinal():
    assert canonical_label("Nº Procedimiento") == "procedimiento_numero"
    assert canonical_label("Nº Documento") == "documento_numero"


def test_canonical_label_nif_variants():
    assert canonical_label("N.I.F.") == "nif"
    assert canonical_label("nif") == "nif"
    assert canonical_label("NIF") == "nif"


def test_canonical_label_economic_fields():
    assert canonical_label("TAE") == "tae"
    assert canonical_label("Interés Nominal Anual") == "interes_nominal_anual"
    assert canonical_label("Cuota") == "cuota"
    assert canonical_label("Importe total adeudado") == "importe_total_adeudado"


def test_canonical_label_unknown_returns_none():
    assert canonical_label("Some unknown label") is None
    assert canonical_label("xyz") is None
    assert canonical_label("") is None


def test_canonical_label_employment_fields():
    assert canonical_label("Tipo Contrato") == "tipo_contrato"
    assert canonical_label("CCC") == "ccc"
    assert canonical_label("Nº Seguridad Social") == "numero_seguridad_social"


def test_label_schema_all_values_are_snake_case():
    # Every canonical slug must be lowercase + underscore (no spaces, no
    # punctuation, no accents). Catches typos as the schema grows.
    for slug in LABEL_SCHEMA.values():
        assert slug == slug.lower()
        assert " " not in slug
        assert all(c.isalnum() or c == "_" for c in slug)
