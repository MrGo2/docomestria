from docomestria.live_features import (
    _base_row,
    _bbox_to_dict,
    _engine_features,
    build_live_rows,
)
from docomestria.models import BBox, DoclingBlock, LiteItem, VisualRect, WordItem


def test_base_row_geometry_normalised_by_page_size():
    it = LiteItem(
        text="NOMBRE:",
        bbox=BBox(x=60.0, y=120.0, w=90.0, h=12.0),
        font_name="Helvetica-Bold",
        font_size=10.0,
        page=1,
    )
    row = _base_row(it, page_size_pt=(600.0, 800.0))
    assert row["x"] == 60.0 / 600.0
    assert row["y"] == 120.0 / 800.0
    assert row["w"] == 90.0 / 600.0
    assert row["h"] == 12.0 / 800.0
    assert row["is_bold"] == 1
    assert row["font_size"] == 10.0
    assert row["case_upper"] == 1 and row["case_lower"] == 0
    assert row["ends_colon"] is True or row["ends_colon"] == 1
    assert row["text"] == "NOMBRE:"
    assert row["page"] == 1
    assert row["liteparse_present"] == 1


def test_bbox_to_dict_roundtrip():
    assert _bbox_to_dict(BBox(x=1.0, y=2.0, w=3.0, h=4.0)) == {
        "x": 1.0,
        "y": 2.0,
        "w": 3.0,
        "h": 4.0,
    }


def _item(text="Nombre", x=60.0, y=120.0, w=40.0, h=12.0, page=1):
    return LiteItem(
        text=text,
        bbox=BBox(x=x, y=y, w=w, h=h),
        font_name="Helvetica",
        font_size=10.0,
        page=page,
    )


def test_engine_features_docling_match_pulls_content_layer_from_raw_block():
    it = _item()
    blocks = [
        DoclingBlock(
            bbox=BBox(x=0.0, y=0.0, w=600.0, h=800.0),
            label="text",
            heading_level=None,
            content_layer="body",
            page=1,
        )
    ]
    feats = _engine_features(it, blocks, rects=[], words=[])
    assert feats["docling_present"] == 1
    assert feats["docling_content_layer"] == "body"
    assert feats["docling_label"] == "text"


def test_engine_features_missing_engines_degrade_to_zero():
    feats = _engine_features(_item(), blocks=[], rects=[], words=[])
    assert feats["docling_present"] == 0
    assert feats["pdfplumber_present"] == 0
    assert feats["inside_rect"] == 0
    assert feats["rect_is_signature_field"] == 0
    assert feats["engine_agreement"] == 1


def test_engine_features_over_signature_rect():
    it = _item(y=700.0)
    sig = VisualRect(
        bbox=BBox(x=0.0, y=690.0, w=600.0, h=30.0),
        is_checkbox=False,
        is_filled=False,
        page=1,
        rect_type="signature_field",
    )
    feats = _engine_features(it, blocks=[], rects=[sig], words=[])
    assert feats["rect_is_signature_field"] == 1
    assert feats["inside_rect"] == 1


def test_engine_features_real_colon_from_detached_word():
    it = _item(text="Nombre", x=60.0, y=120.0, w=40.0, h=12.0)
    colon = WordItem(text=":", bbox=BBox(x=102.0, y=120.0, w=4.0, h=12.0), page=1)
    feats = _engine_features(it, blocks=[], rects=[], words=[colon])
    assert feats["colon_present"] == 1


def test_engine_features_no_colon_when_absent():
    feats = _engine_features(
        _item(text="Nombre"),
        blocks=[],
        rects=[],
        words=[WordItem(text="Adrian", bbox=BBox(x=102.0, y=120.0, w=40.0, h=12.0), page=1)],
    )
    assert feats["colon_present"] == 0


def test_engine_features_colon_word_on_other_page_ignored():
    it = _item(text="Nombre", x=60.0, y=120.0, w=40.0, h=12.0, page=1)
    colon = WordItem(text=":", bbox=BBox(x=102.0, y=120.0, w=4.0, h=12.0), page=2)
    feats = _engine_features(it, blocks=[], rects=[], words=[colon])
    assert feats["colon_present"] == 0


def test_engine_features_word_containing_colon_is_not_a_detached_colon():
    it = _item(text="Hora", x=60.0, y=120.0, w=40.0, h=12.0)
    word = WordItem(text="5:30", bbox=BBox(x=102.0, y=120.0, w=20.0, h=12.0), page=1)
    feats = _engine_features(it, blocks=[], rects=[], words=[word])
    assert feats["colon_present"] == 0


def test_engine_features_table_cell_sets_in_table_and_inside_rect():
    it = _item(text="Adrian", x=60.0, y=120.0, w=40.0, h=12.0)  # centroid (80, 126)
    grid = (
        (BBox(x=50.0, y=100.0, w=50.0, h=30.0), BBox(x=100.0, y=100.0, w=50.0, h=30.0)),
        (BBox(x=50.0, y=130.0, w=50.0, h=30.0), BBox(x=100.0, y=130.0, w=50.0, h=30.0)),
    )
    table = VisualRect(
        bbox=BBox(x=50.0, y=100.0, w=100.0, h=60.0),
        is_checkbox=False,
        is_filled=False,
        page=1,
        rect_id="t0",
        rect_type="table",
        table_grid=grid,
    )
    feats = _engine_features(it, blocks=[], rects=[table], words=[])
    assert feats["in_table"] == 1
    assert feats["inside_rect"] == 1
    assert feats["table_id"] == "t0"
    assert feats["row_idx"] == "0"
    assert feats["col_id"] == "0"


def test_engine_features_compound_span_interior_colon():
    feats = _engine_features(_item(text="Nombre: Adrian"), blocks=[], rects=[], words=[])
    assert feats["compound_span"] == 1
    feats2 = _engine_features(_item(text="Total:"), blocks=[], rects=[], words=[])
    assert feats2["compound_span"] == 0


def test_build_live_rows_full_schema_and_neighbour_order():
    from docomestria.golden.training_table import FIELDS

    items = [
        LiteItem(
            text="SECCION",
            bbox=BBox(x=60.0, y=100.0, w=120.0, h=14.0),
            font_name="Helvetica-Bold",
            font_size=12.0,
            page=1,
        ),
        LiteItem(
            text="cuerpo normal",
            bbox=BBox(x=60.0, y=130.0, w=200.0, h=10.0),
            font_name="Helvetica",
            font_size=10.0,
            page=1,
        ),
    ]
    rows = build_live_rows(
        "DOC.pdf",
        page=1,
        lite_items=items,
        docling_blocks=[],
        visual_rects=[],
        words=[],
        page_size_pt=(600.0, 800.0),
    )
    assert len(rows) == 2
    for r in rows:
        assert set(r.keys()) == set(FIELDS)
        assert r["pdf"] == "DOC.pdf"
    top, _below = rows[0], rows[1]  # sorted by (y, x)
    assert top["bold_above_nonbold_below"] == 1
    assert abs(top["font_ratio_vs_below"] - 1.2) < 1e-9
    assert top["font_size_ratio"] != ""
    assert top["gap_below"] > 0


def test_build_live_rows_is_centered():
    it = LiteItem(
        text="TITULO",
        bbox=BBox(x=270.0, y=50.0, w=60.0, h=14.0),
        font_name="Helvetica-Bold",
        font_size=12.0,
        page=1,
    )
    rows = build_live_rows("D.pdf", 1, [it], [], [], [], (600.0, 800.0))
    assert rows[0]["is_centered"] == 1
