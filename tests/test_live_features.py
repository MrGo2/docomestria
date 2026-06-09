from docomestria.live_features import _base_row, _bbox_to_dict, _engine_features
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


def test_engine_features_compound_span_interior_colon():
    feats = _engine_features(_item(text="Nombre: Adrian"), blocks=[], rects=[], words=[])
    assert feats["compound_span"] == 1
    feats2 = _engine_features(_item(text="Total:"), blocks=[], rects=[], words=[])
    assert feats2["compound_span"] == 0
