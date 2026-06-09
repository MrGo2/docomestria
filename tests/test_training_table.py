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


from docomestria.golden.training_table import noise_items


def test_unmatched_atoms_become_noise():
    spans = [
        {"text": "Nombre", "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
         "font_size": 10.0, "is_bold": True, "case_class": "Title"},
        {"text": "JUNK WATERMARK", "bbox": {"x": 9, "y": 9, "w": 5, "h": 4},
         "font_size": 7.0, "is_bold": False, "case_class": "UPPER"},
    ]
    # span 0 consumed by an annotated item; span 1 is unmatched background
    consumed = {0}
    annotated = [("Nombre", {"x": 1, "y": 2, "w": 3, "h": 4})]
    noise = noise_items(spans, consumed, annotated)
    assert len(noise) == 1
    assert noise[0].role == "noise"
    assert noise[0].text == "JUNK WATERMARK"
    assert noise[0].signal["liteparse"]["span_id"] == 1


def test_atom_matched_by_text_bbox_not_double_counted():
    spans = [{"text": "Nombre", "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
              "font_size": 10.0, "is_bold": True, "case_class": "Title"}]
    # not in consumed set, but text+bbox match an annotated item -> NOT noise
    annotated = [("Nombre", {"x": 1, "y": 2, "w": 3, "h": 4})]
    assert noise_items(spans, set(), annotated) == []


from docomestria.golden.training_table import build_page_rows


def _golden_with_two_kv():
    return {
        "pdf": "DOC", "page": 1, "page_size_pt": [600.0, 800.0],
        "structure": [{
            "type": "kv_group", "id": "g",
            "pairs": [{
                "label": "Nº Modelo", "value": "F_AS-5",
                "label_bbox": {"x": 60.0, "y": 24.0, "w": 60.0, "h": 10.0},
                "bbox": {"x": 300.0, "y": 24.0, "w": 40.0, "h": 10.0},
                "evidence": {
                    "label": {"liteparse": {"span_id": 0, "bbox": {"x": 60.0, "y": 24.0, "w": 60.0, "h": 10.0},
                              "case_class": "Title", "is_bold": False, "font_size": 10.0},
                              "engine_agreement": 2},
                    "value": {"liteparse": {"span_id": 1, "bbox": {"x": 300.0, "y": 24.0, "w": 40.0, "h": 10.0},
                              "case_class": "Title", "is_bold": False, "font_size": 10.0},
                              "engine_agreement": 2},
                },
            }],
        }],
    }


def _atoms_two_spans():
    return {"atoms": {"spans": [
        {"text": "Nº Modelo", "bbox": {"x": 60.0, "y": 24.0, "w": 60.0, "h": 10.0},
         "font_size": 10.0, "is_bold": False, "case_class": "Title"},
        {"text": "F_AS-5", "bbox": {"x": 300.0, "y": 24.0, "w": 40.0, "h": 10.0},
         "font_size": 10.0, "is_bold": False, "case_class": "Title"},
    ], "rects": []}}


def test_build_page_rows_geometry_and_label_and_content():
    rows, diag = build_page_rows(_golden_with_two_kv(), _atoms_two_spans())
    assert len(rows) == 2  # both atoms consumed -> no extra noise
    by_role = {r["role"]: r for r in rows}
    key = by_role["key"]
    # geometry normalised by page size [600,800]
    assert abs(key["x"] - 60.0 / 600.0) < 1e-9
    assert abs(key["w"] - 60.0 / 600.0) < 1e-9
    # content computed from the item's own text
    assert by_role["value"]["digit_ratio"] > 0  # "F_AS-5" has a digit
    assert key["digit_ratio"] == 0.0            # "Nº Modelo" has none
    # font_size_ratio: both items have font 10 -> median 10 -> ratio 1.0
    assert abs(key["font_size_ratio"] - 1.0) < 1e-9
    assert diag["unresolved_keys"] == 0


def test_build_page_rows_emits_noise_for_extra_atom():
    g = _golden_with_two_kv()
    atoms = _atoms_two_spans()
    atoms["atoms"]["spans"].append(
        {"text": "WATERMARK", "bbox": {"x": 10.0, "y": 700.0, "w": 80.0, "h": 8.0},
         "font_size": 6.0, "is_bold": False, "case_class": "UPPER"})
    rows, diag = build_page_rows(g, atoms)
    assert any(r["role"] == "noise" and r["text"] == "WATERMARK" for r in rows)


def test_walk_array_emits_value_rows_for_filled_fields():
    # real goldens (e.g. BBVA_0539) use an `array` node: items[] -> groups -> fields.
    structure = [{
        "type": "array", "id": "titulares", "title": "Titulares",
        "items": [
            {"index": 1, "filled": True,
             "datos": {"title": "Datos", "y_hint": 1,
                       "nif": {"text": "009786573G",
                               "evidence": {"liteparse": None},
                               "bbox": {"x": 1, "y": 2, "w": 3, "h": 4}},
                       "vacio": [None, 180]}},
            {"index": 2, "filled": False,
             "datos": {"title": "Datos", "y_hint": 1, "nif": [None, 180]}},
        ],
    }]
    items = walk_structure(structure, spans=[])
    assert len(items) == 1                     # only the filled field
    assert items[0].role == "value"
    assert items[0].text == "009786573G"
    assert items[0].source_node_type == "array"


def test_build_page_rows_survives_null_liteparse_signal():
    # a real golden leaf carries `liteparse: null` (key present, value None);
    # geometry resolution must not crash on it.
    golden = {
        "pdf": "D", "page": 1, "page_size_pt": [600.0, 800.0],
        "structure": [{
            "type": "noise", "id": "n", "text": "Encabezado modelo", "bbox": None,
            "evidence": {"text_signal": {
                "text": "Encabezado modelo",
                "pdfplumber": {"bbox": {"x": 10.0, "y": 20.0, "w": 30.0, "h": 8.0}},
                "liteparse": None, "docling": None, "engine_agreement": 1}},
        }],
    }
    atoms = {"atoms": {"spans": [], "rects": []}}
    rows, diag = build_page_rows(golden, atoms)   # must not raise
    assert any(r["role"] == "noise" for r in rows)


def test_build_page_rows_drops_nonstring_text_cells():
    # a table cell whose value is a footnote-reference object {"ref": ...}
    golden = {
        "pdf": "D", "page": 1, "page_size_pt": [600.0, 800.0],
        "structure": [{
            "type": "table", "id": "t", "columns": [{"id": "label"}, {"id": "value"}],
            "rows": [{
                "label": {"text": "Concepto", "evidence": {"liteparse": None},
                          "bbox": {"x": 1, "y": 9, "w": 2, "h": 2}},
                "value": {"text": {"ref": "nota_1"}, "evidence": {"liteparse": None},
                          "bbox": {"x": 4, "y": 9, "w": 2, "h": 2}},
            }],
        }],
    }
    atoms = {"atoms": {"spans": [], "rects": []}}
    rows, diag = build_page_rows(golden, atoms)   # must not raise
    assert diag["dropped_nonstr_text"] == 1
    assert all(isinstance(r["text"], str) for r in rows)
    assert any(r["text"] == "Concepto" for r in rows)


def test_build_page_rows_is_deterministic():
    g, a = _golden_with_two_kv(), _atoms_two_spans()
    r1, _ = build_page_rows(g, a)
    r2, _ = build_page_rows(g, a)
    assert r1 == r2  # same input -> identical rows, identical order


def test_build_page_rows_font_ratio_empty_when_no_fonts():
    # a page where the only item has no liteparse font -> font_size_ratio is ""
    golden = {
        "pdf": "D", "page": 1, "page_size_pt": [600.0, 800.0],
        "structure": [{
            "type": "prose_block", "id": "p", "text": "sin fuente",
            "bbox": {"x": 10.0, "y": 20.0, "w": 30.0, "h": 8.0},
            "evidence": {"text_signal": {"liteparse": None, "engine_agreement": 1}},
        }],
    }
    atoms = {"atoms": {"spans": [], "rects": []}}
    rows, _ = build_page_rows(golden, atoms)
    prose = [r for r in rows if r["role"] == "prose"][0]
    assert prose["font_size"] == ""
    assert prose["font_size_ratio"] == ""
