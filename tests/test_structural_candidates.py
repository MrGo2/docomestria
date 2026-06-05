"""Structural pair-candidate emitter regression tests."""

from __future__ import annotations

from docomestria.models import BBox, LiteItem
from docomestria.structural import (
    ClassifiedItem,
    ItemKind,
    Page,
    Table,
    emit_from_docling_tables,
    emit_from_horizontal_pair,
    emit_from_in_item_split,
    emit_from_two_column_form,
)


def _classified_item(
    text: str,
    *,
    x: float = 20.0,
    y: float = 20.0,
    w: float = 220.0,
    kind: ItemKind = ItemKind.LABEL,
) -> ClassifiedItem:
    return ClassifiedItem(
        item=LiteItem(
            text=text,
            bbox=BBox(x=x, y=y, w=w, h=10.0),
            font_name=None,
            font_size=None,
            page=1,
        ),
        kind=kind,
    )


def test_two_column_form_splits_multiple_inline_pairs_in_one_item():
    table = Table(
        bbox=BBox(x=0.0, y=0.0, w=500.0, h=100.0),
        page=1,
        cells=(
            (
                "Tipo Identificación: NIF PERSONA FISICA N.I.F.: 009786573G",
                "Tipo Identificación: - N.I.F.: -",
            ),
        ),
    )

    pairs = emit_from_two_column_form(
        (
            _classified_item(
                "Tipo Identificación: NIF PERSONA FISICA N.I.F.: 009786573G"
            ),
            _classified_item("Tipo Identificación: -", x=300.0, w=90.0),
            _classified_item("N.I.F.: -", x=420.0, w=60.0),
        ),
        (Page(number=1, tables=(table,)),),
    )

    assert [(p.label_text, p.value_text, p.column_index) for p in pairs] == [
        ("Tipo Identificación", "NIF PERSONA FISICA", 1),
        ("N.I.F.", "009786573G", 1),
        ("Tipo Identificación", "-", 2),
        ("N.I.F.", "-", 2),
    ]


def test_two_column_form_attaches_wrapped_value_continuation():
    table = Table(
        bbox=BBox(x=0.0, y=0.0, w=500.0, h=100.0),
        page=1,
        cells=(
            (
                "Tipo Identificación: NIF QUE COMIENCEN CON X Y Z N.I.F.: X3669812R",
                "Tipo Identificación: - N.I.F.: -",
            ),
        ),
    )

    pairs = emit_from_two_column_form(
        (
            _classified_item(
                "Tipo Identificación: NIF QUE COMIENCEN N.I.F.: X3669812R"
            ),
            _classified_item(
                "CON X Y Z",
                y=31.0,
                w=50.0,
                kind=ItemKind.VALUE,
            ),
            _classified_item("Tipo Identificación: -", x=300.0, w=90.0),
            _classified_item("N.I.F.: -", x=420.0, w=60.0),
        ),
        (Page(number=1, tables=(table,)),),
    )

    assert [(p.label_text, p.value_text, p.column_index) for p in pairs][:2] == [
        ("Tipo Identificación", "NIF QUE COMIENCEN CON X Y Z", 1),
        ("N.I.F.", "X3669812R", 1),
    ]


def test_docling_tables_emit_per_column_for_dense_matrix():
    """Shape 4: a `[label, v1, v2]` row with a prior column-header row emits
    one pair per distinct column value with `column_index` set."""
    table = Table(
        bbox=BBox(x=0.0, y=0.0, w=400.0, h=90.0),
        page=1,
        cells=(
            ("", "Sin nomina", "Con nomina"),
            ("TAE", "12,6020%", "11,4813%"),
        ),
    )

    pairs = emit_from_docling_tables((Page(number=1, tables=(table,)),))

    assert [(p.label_text, p.value_text, p.column_index) for p in pairs] == [
        ("TAE", "12,6020%", 1),
        ("TAE", "11,4813%", 2),
    ]


def test_docling_tables_emit_kv_rows_with_trailing_empty_cells():
    """A `[label, value, '']` row in an N-col table is a real KV that just
    happens to leave trailing columns empty. We must NOT suppress these as
    `_is_wide_header_or_sparse_row` only fires when col 1 AND cols 2..N-1
    are empty."""
    table = Table(
        bbox=BBox(x=0.0, y=0.0, w=400.0, h=90.0),
        page=1,
        cells=(
            ("Primera Tarjeta Emitida", "43,00", ""),
            ("Resto de Tarjetas", "20,00", ""),
        ),
    )

    pairs = emit_from_docling_tables((Page(number=1, tables=(table,)),))

    assert [(p.label_text, p.value_text) for p in pairs] == [
        ("Primera Tarjeta Emitida", "43,00"),
        ("Resto de Tarjetas", "20,00"),
    ]


def test_docling_tables_suppress_truly_sparse_header_rows():
    """A row whose only populated cell is col 0 (cols 1..N-1 all empty) is a
    spanned title / section header — suppress as not a KV row."""
    table = Table(
        bbox=BBox(x=0.0, y=0.0, w=400.0, h=90.0),
        page=1,
        cells=(
            ("COMISIONES POR OTRAS OPERACIONES", "", ""),
        ),
    )

    pairs = emit_from_docling_tables((Page(number=1, tables=(table,)),))

    assert pairs == ()


def test_docling_tables_keep_wide_rows_that_look_like_kv_data():
    table = Table(
        bbox=BBox(x=0.0, y=0.0, w=400.0, h=45.0),
        page=1,
        cells=(("Pago Personalizado", "18,0000", "Detalle en clausula"),),
    )

    pairs = emit_from_docling_tables((Page(number=1, tables=(table,)),))

    assert [(p.label_text, p.value_text) for p in pairs] == [
        ("Pago Personalizado", "18,0000")
    ]


def test_docling_tables_do_not_emit_blank_labels():
    table = Table(
        bbox=BBox(x=0.0, y=0.0, w=300.0, h=45.0),
        page=1,
        cells=(("", "% Minimo"),),
    )

    pairs = emit_from_docling_tables((Page(number=1, tables=(table,)),))

    assert pairs == ()


def test_horizontal_pair_skips_pdfplumber_table_regions():
    table = Table(
        bbox=BBox(x=0.0, y=0.0, w=300.0, h=45.0),
        page=1,
        cells=(("Primera Tarjeta Emitida", "43,00"),),
        source="pdfplumber",
    )
    label = _classified_item("Primera Tarjeta Emitida", x=20.0, y=15.0, w=120.0)
    value = _classified_item(
        "43,00",
        x=160.0,
        y=15.0,
        w=40.0,
        kind=ItemKind.VALUE,
    )

    pairs = emit_from_horizontal_pair(
        (label, value),
        (Page(number=1, tables=(table,)),),
    )

    assert pairs == ()


def test_horizontal_pair_keeps_rows_when_only_pdfplumber_shadow_table_matches():
    """pdfplumber occasionally re-detects real content at phantom off-page Y
    coordinates. Those shadow tables must NOT suppress L-horizontal pairs
    sitting on the actual page — only docling/fused table cells trigger
    textual suppression. Regression: BBVA4 p1 `Primera Tarjeta Emitida`
    sits at y=430 but a pdfplumber shadow table at y=1248 contains the
    same row text.
    """
    shadow_table = Table(
        bbox=BBox(x=0.0, y=1000.0, w=300.0, h=45.0),
        page=1,
        cells=(("PrimeraTarjetaEmitida", "43,00"),),
        source="pdfplumber",
    )
    label = _classified_item("Primera Tarjeta Emitida", x=20.0, y=15.0, w=120.0)
    value = _classified_item(
        "43,00",
        x=160.0,
        y=15.0,
        w=40.0,
        kind=ItemKind.VALUE,
    )

    pairs = emit_from_horizontal_pair(
        (label, value),
        (Page(number=1, tables=(shadow_table,)),),
    )

    assert [(p.label_text, p.value_text) for p in pairs] == [
        ("Primera Tarjeta Emitida", "43,00"),
    ]


def test_horizontal_pair_skips_rows_already_in_docling_table_cells():
    """When the matching table is docling/fused (i.e. trusted), the textual
    overlap correctly suppresses the L-horizontal duplicate."""
    table = Table(
        bbox=BBox(x=0.0, y=1000.0, w=300.0, h=45.0),
        page=1,
        cells=(("Primera Tarjeta Emitida", "43,00"),),
        source="docling",
    )
    label = _classified_item("Primera Tarjeta Emitida", x=20.0, y=15.0, w=120.0)
    value = _classified_item(
        "43,00",
        x=160.0,
        y=15.0,
        w=40.0,
        kind=ItemKind.VALUE,
    )

    pairs = emit_from_horizontal_pair(
        (label, value),
        (Page(number=1, tables=(table,)),),
    )

    assert pairs == ()


def test_inline_split_skips_pdfplumber_table_regions():
    table = Table(
        bbox=BBox(x=0.0, y=0.0, w=300.0, h=45.0),
        page=1,
        cells=(("Primera Tarjeta Emitida", "43,00"),),
        source="pdfplumber",
    )

    pairs = emit_from_in_item_split(
        (_classified_item("Primera Tarjeta Emitida: 43,00", x=20.0, y=15.0),),
        (Page(number=1, tables=(table,)),),
    )

    assert pairs == ()
