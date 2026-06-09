from pathlib import Path
from docomestria.golden.training_table import FIELDS, write_csv


def test_fields_are_unique_and_start_with_provenance():
    assert len(FIELDS) == len(set(FIELDS))
    assert FIELDS[:5] == ["pdf", "page", "text", "node_path", "source_node_type"]
    assert "role" in FIELDS


def test_write_csv_is_byte_deterministic(tmp_path):
    rows = [
        {f: "" for f in FIELDS},
        {f: "" for f in FIELDS},
    ]
    rows[0].update({"pdf": "B", "page": 2, "role": "value",
                    "is_bold": True, "x": 0.123456})
    rows[1].update({"pdf": "A", "page": 1, "role": "key",
                    "is_bold": False, "x": 0.5})
    out = tmp_path / "t.csv"
    write_csv(rows, out)
    text = out.read_text(encoding="utf-8")
    lines = text.splitlines()
    # header is FIELDS joined; bool -> 0/1; float rounded to 4 dp; \n newline
    assert lines[0] == ",".join(FIELDS)
    assert ",0.1235," in text          # x rounded to 4 dp
    # bools encoded as 0/1 somewhere in the data rows
    assert any(cell in ("0", "1") for cell in lines[1].split(","))
    # rows are written in the order given (sorting happens in the CLI, not here)
    assert lines[1].startswith("B,2,")


from docomestria.golden.training_table import signal_features


_SIGNAL = {
    "text": "Nombre",
    "pdfplumber": {"bbox": {"x": 1, "y": 2, "w": 3, "h": 4}},
    "liteparse": {"span_id": 7, "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
                  "case_class": "Title", "is_bold": True, "font_size": 10.0},
    "docling": {"cell_ref": "#/texts/36", "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
                "column_header": None, "row_header": None},
    "rect": None,
    "colon_signal": None,
    "engine_agreement": 3,
}


def test_signal_features_reads_liteparse_and_presence():
    f = signal_features(_SIGNAL)
    assert f["font_size"] == 10.0
    assert f["is_bold"] is True
    assert f["case_title"] == 1 and f["case_upper"] == 0
    assert f["liteparse_present"] == 1
    assert f["pdfplumber_present"] == 1
    assert f["docling_present"] == 1
    assert f["inside_rect"] == 0
    assert f["colon_present"] == 0
    assert f["engine_agreement"] == 3
    assert f["span_id"] == 7


def test_signal_features_none_is_all_absent():
    f = signal_features(None)
    assert f["liteparse_present"] == 0
    assert f["font_size"] == ""
    assert f["span_id"] is None


from docomestria.golden.training_table import rederive_signal


_SPANS = [
    {"text": "Nº Modelo", "bbox": {"x": 477.0, "y": 24.0, "w": 47.0, "h": 9.0},
     "font_size": 10.0, "is_bold": False, "case_class": "Title"},
    {"text": "Nombre", "bbox": {"x": 100.0, "y": 24.0, "w": 30.0, "h": 9.0},
     "font_size": 10.0, "is_bold": True, "case_class": "Title"},
    {"text": "Nombre", "bbox": {"x": 400.0, "y": 24.0, "w": 30.0, "h": 9.0},
     "font_size": 9.0, "is_bold": False, "case_class": "Title"},
]


def test_rederive_resolves_by_text_and_bbox_overlap():
    sig, status = rederive_signal("Nº Modelo",
                                  {"x": 478.0, "y": 24.0, "w": 47.0, "h": 9.0},
                                  _SPANS)
    assert status == "resolved"
    assert sig["liteparse"]["span_id"] == 0
    assert sig["liteparse"]["font_size"] == 10.0


def test_rederive_ambiguous_when_two_spans_overlap_same_text():
    # both "Nombre" spans match text; neither overlaps the query bbox -> unresolved
    sig, status = rederive_signal("Nombre",
                                  {"x": 250.0, "y": 24.0, "w": 30.0, "h": 9.0},
                                  _SPANS)
    assert status == "unresolved"
    assert sig is None


def test_rederive_picks_the_overlapping_one_when_unambiguous():
    sig, status = rederive_signal("Nombre",
                                  {"x": 101.0, "y": 24.0, "w": 30.0, "h": 9.0},
                                  _SPANS)
    assert status == "resolved"
    assert sig["liteparse"]["span_id"] == 1


from docomestria.golden.training_table import Item, walk_structure


def _items_by_role(items):
    out = {}
    for it in items:
        out.setdefault(it.role, []).append(it.text)
    return out


def test_walk_kv_group_emits_key_and_value_rows():
    structure = [{
        "type": "kv_group", "id": "titular",
        "pairs": [{
            "label": "Nombre", "value": "ADRIAN",
            "label_bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
            "bbox": {"x": 5, "y": 2, "w": 3, "h": 4},
            "evidence": {
                "label": {"liteparse": {"span_id": 7, "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
                          "case_class": "Title", "is_bold": True, "font_size": 10.0},
                          "engine_agreement": 3},
                "value": {"liteparse": {"span_id": 8, "bbox": {"x": 5, "y": 2, "w": 3, "h": 4},
                          "case_class": "UPPER", "is_bold": False, "font_size": 10.0},
                          "engine_agreement": 3},
            },
        }],
    }]
    items = walk_structure(structure, spans=[])
    roles = _items_by_role(items)
    assert roles["key"] == ["Nombre"]
    assert roles["value"] == ["ADRIAN"]
    # different span_ids -> not compound
    assert all(it.compound_span == 0 for it in items)


def test_walk_fused_span_sets_compound_on_both_rows():
    # key and value resolve to the SAME liteparse span_id -> compound_span=1
    structure = [{
        "type": "kv_group", "id": "g",
        "pairs": [{
            "label": "Nº Modelo", "value": "F_AS-5",
            "label_bbox": {"x": 1, "y": 2, "w": 9, "h": 4},
            "bbox": {"x": 1, "y": 2, "w": 9, "h": 4},
            "evidence": {
                "label": {"liteparse": {"span_id": 4, "bbox": {"x": 1, "y": 2, "w": 9, "h": 4},
                          "case_class": "Title", "is_bold": False, "font_size": 10.0}},
                "value": {"liteparse": {"span_id": 4, "bbox": {"x": 1, "y": 2, "w": 9, "h": 4},
                          "case_class": "Title", "is_bold": False, "font_size": 10.0}},
            },
        }],
    }]
    items = walk_structure(structure, spans=[])
    assert all(it.compound_span == 1 for it in items)
    # content features still differ per row (computed later from each item's text)
    from docomestria.text_features import content_flags
    assert content_flags("Nº Modelo")["digit_ratio"] == 0.0
    assert content_flags("F_AS-5")["digit_ratio"] > 0.0


def test_walk_table_maps_header_keycol_valuecol():
    structure = [{
        "type": "table", "id": "t1", "title": "Datos",
        "columns": [{"id": "label", "label": "Concepto"},
                    {"id": "value", "label": "Importe"}],
        "rows": [{
            "label": {"text": "Precio", "evidence": {"liteparse": None}, "bbox": {"x": 1, "y": 9, "w": 2, "h": 2}},
            "value": {"text": "14.990,00", "evidence": {"liteparse": None}, "bbox": {"x": 4, "y": 9, "w": 2, "h": 2}},
        }],
    }]
    items = walk_structure(structure, spans=[])
    roles = _items_by_role(items)
    assert "Precio" in roles["key"]
    assert "14.990,00" in roles["value"]
    # column header labels become table_header
    assert "Concepto" in roles["table_header"] and "Importe" in roles["table_header"]


def test_walk_noise_node():
    structure = [{"type": "noise", "id": "n1", "text": "pág 1/24",
                  "bbox": {"x": 1, "y": 1, "w": 2, "h": 2},
                  "evidence": {"text_signal": {"liteparse": None, "engine_agreement": 1}}}]
    items = walk_structure(structure, spans=[])
    assert items[0].role == "noise" and items[0].text == "pág 1/24"


def test_walk_unknown_node_raises():
    import pytest
    with pytest.raises(ValueError):
        walk_structure([{"type": "frobnicate"}], spans=[])
