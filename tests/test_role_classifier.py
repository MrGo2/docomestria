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


import numpy as np
from docomestria.training.role_classifier import docling_baseline_predict, build_encoder, encode_features


def test_docling_baseline_majority_and_fallback():
    train = pd.DataFrame([
        {"docling_label": "section_header", "role": "section_header"},
        {"docling_label": "section_header", "role": "section_header"},
        {"docling_label": "text", "role": "prose"},
        {"docling_label": "text", "role": "key"},
        {"docling_label": "text", "role": "prose"},   # text -> prose majority
        {"docling_label": None, "role": "noise"},
        {"docling_label": None, "role": "noise"},      # global majority -> noise
    ])
    test = pd.DataFrame([
        {"docling_label": "section_header"},   # -> section_header
        {"docling_label": "text"},             # -> prose
        {"docling_label": None},               # missing -> global majority (noise)
        {"docling_label": "caption"},          # unseen -> global majority (noise)
    ])
    preds, fallback_share = docling_baseline_predict(train, test)
    assert list(preds) == ["section_header", "prose", "noise", "noise"]
    assert abs(fallback_share - 0.5) < 1e-9   # 2 of 4 test rows hit fallback


def test_encode_features_onehot_and_numeric_nan():
    train = pd.DataFrame([
        {"x": 0.1, "docling_label": "text", "docling_content_layer": "body"},
        {"x": 0.2, "docling_label": "section_header", "docling_content_layer": "body"},
    ])
    test = pd.DataFrame([
        {"x": np.nan, "docling_label": "caption", "docling_content_layer": "furniture"},  # all unseen
    ])
    enc = build_encoder(train[["x", "docling_label", "docling_content_layer"]],
                        numeric=["x"], categorical=["docling_label", "docling_content_layer"])
    Xtr = encode_features(enc, train[["x", "docling_label", "docling_content_layer"]],
                          numeric=["x"], categorical=["docling_label", "docling_content_layer"])
    Xte = encode_features(enc, test[["x", "docling_label", "docling_content_layer"]],
                          numeric=["x"], categorical=["docling_label", "docling_content_layer"])
    assert Xtr.shape[0] == 2 and Xte.shape[0] == 1
    assert Xtr.shape[1] == Xte.shape[1]          # same width despite unseen categories
    assert np.isnan(Xte[0, 0])                    # numeric NaN preserved (first col = x)
    # unseen categories -> all-zero one-hot block (handle_unknown="ignore")
    assert Xte[0, 1:].sum() == 0.0


from docomestria.training.role_classifier import evaluate_oof, FEATURE_COLS


def _synthetic_dataset(n_pdfs=6, per_pdf=40):
    # learnable signal: docling_label maps cleanly to role, plus a numeric separator
    import itertools
    roles = ["key", "value", "noise", "section_header"]
    rows = []
    for p in range(n_pdfs):
        for i in range(per_pdf):
            r = roles[i % len(roles)]
            rows.append({
                "pdf": f"PDF{p}", "text": f"t{p}_{i}", "role": r,
                "x": 0.1 if r == "key" else 0.8, "y": (i % 10) / 10.0,
                "font_size": 12.0 if r == "section_header" else 9.0,
                "docling_label": {"key": "text", "value": "text",
                                  "noise": "page_footer",
                                  "section_header": "section_header"}[r],
                "docling_content_layer": "furniture" if r == "noise" else "body",
                "docling_heading_level": 1 if r == "section_header" else "",
                # remaining feature cols default 0 (filled below)
            })
    df = pd.DataFrame(rows)
    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = 0
    return df


def test_evaluate_oof_returns_pooled_metrics_and_beats_nothing_gracefully():
    df = _synthetic_dataset()
    result = evaluate_oof(df, n_splits=3, random_state=0)
    # required report keys
    for k in ("macro_f1", "per_class", "confusion", "labels",
              "baseline_macro_f1", "baseline_fallback_share",
              "n_rows", "n_dropped_dups", "sklearn_version"):
        assert k in result
    # one OOF prediction per (deduped) row
    assert len(result["oof_pred"]) == result["n_rows"]
    # learnable synthetic data -> model should be strong
    assert result["macro_f1"] > 0.8


def test_evaluate_oof_is_deterministic():
    df = _synthetic_dataset()
    a = evaluate_oof(df, n_splits=3, random_state=0)
    b = evaluate_oof(df, n_splits=3, random_state=0)
    assert a["macro_f1"] == b["macro_f1"]
    assert a["confusion"] == b["confusion"]
