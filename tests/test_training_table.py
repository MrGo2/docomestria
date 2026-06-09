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
