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
