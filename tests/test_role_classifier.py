import pandas as pd
from docomestria.training.role_classifier import (
    FEATURE_COLS, CATEGORICAL_COLS, LABEL_COL, GROUP_COL,
    load_dataset, dedupe_text_role,
)


def _tiny_df():
    return pd.DataFrame([
        {"pdf": "A", "text": "Total", "role": "key", "x": 0.1, "docling_label": "text"},
        {"pdf": "A", "text": "Total", "role": "key", "x": 0.1, "docling_label": "text"},  # dup
        {"pdf": "B", "text": "100 EUR", "role": "value", "x": 0.5, "docling_label": "text"},
    ])


def test_column_constants_partition_cleanly():
    # features and provenance must not overlap; label/group are provenance
    assert LABEL_COL == "role"
    assert GROUP_COL == "pdf"
    assert "docling_label" in CATEGORICAL_COLS
    assert "role" not in FEATURE_COLS and "pdf" not in FEATURE_COLS
    assert "text" not in FEATURE_COLS


def test_dedupe_text_role_drops_exact_dups():
    df, dropped = dedupe_text_role(_tiny_df())
    assert dropped == 1
    assert len(df) == 2


def test_load_dataset_reads_empty_as_nan(tmp_path):
    p = tmp_path / "t.csv"
    # one numeric col empty -> NaN; categorical empty -> NaN
    p.write_text("pdf,text,role,x,docling_label\nA,Foo,key,,text\n", encoding="utf-8")
    df = load_dataset(p)
    assert pd.isna(df.loc[0, "x"])
