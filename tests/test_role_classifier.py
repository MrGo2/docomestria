import pandas as pd
from docomestria.training.role_classifier import (
    FEATURE_COLS, CATEGORICAL_COLS, LABEL_COL, GROUP_COL,
    load_dataset,
)


def test_column_constants_partition_cleanly():
    # features and provenance must not overlap; label/group are provenance
    assert LABEL_COL == "role"
    assert GROUP_COL == "pdf"
    assert "docling_label" in CATEGORICAL_COLS
    assert "role" not in FEATURE_COLS and "pdf" not in FEATURE_COLS
    assert "text" not in FEATURE_COLS


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


import pickle
from docomestria.training.role_classifier import (
    evaluate_oof, FEATURE_COLS, fit_final_model, feature_importances,
)


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
              "n_rows", "sklearn_version"):
        assert k in result
    # one OOF prediction per row
    assert len(result["oof_pred"]) == result["n_rows"]
    # learnable synthetic data -> model should be strong
    assert result["macro_f1"] > 0.8


def test_evaluate_oof_is_deterministic():
    df = _synthetic_dataset()
    a = evaluate_oof(df, n_splits=3, random_state=0)
    b = evaluate_oof(df, n_splits=3, random_state=0)
    assert a["macro_f1"] == b["macro_f1"]
    assert a["confusion"] == b["confusion"]


def test_fit_final_model_pickles_and_predicts(tmp_path):
    df = _synthetic_dataset().reset_index(drop=True)
    artifact = fit_final_model(df, random_state=0)
    assert set(artifact) >= {"model", "ohe", "feature_cols", "numeric_cols",
                             "categorical_cols", "labels", "sklearn_version"}
    p = tmp_path / "m.pkl"
    p.write_bytes(pickle.dumps(artifact))
    loaded = pickle.loads(p.read_bytes())
    X = encode_features(loaded["ohe"], df[FEATURE_COLS].head(3),
                        loaded["numeric_cols"], loaded["categorical_cols"])
    preds = loaded["model"].predict(X)
    assert len(preds) == 3


def test_feature_importances_ranked_named():
    df = _synthetic_dataset()
    imps = feature_importances(df, n_splits=3, random_state=0, n_repeats=2)
    # list of (feature_name, importance) sorted desc; names are real feature cols (or one-hot expansions)
    assert imps[0][1] >= imps[-1][1]
    assert all(isinstance(name, str) for name, _ in imps)


from docomestria.training.role_classifier import render_report_md


def test_render_report_md_contains_headline_and_table():
    result = {
        "macro_f1": 0.83, "baseline_macro_f1": 0.71, "baseline_fallback_share": 0.12,
        "per_class": {"key": {"precision": 0.9, "recall": 0.8, "f1-score": 0.85, "support": 100}},
        "confusion": [[10]], "labels": ["key"], "oof_pred": ["key"],
        "n_rows": 1, "sklearn_version": "1.5.0",
    }
    imps = [("docling_label_section_header", 0.21), ("ends_colon", 0.05)]
    md = render_report_md(result, imps)
    assert "Macro-F1" in md and "0.83" in md
    assert "vs Docling baseline" in md and "0.71" in md
    assert "dedup: disabled" in md
    assert "docling_label_section_header" in md
    assert "key" in md   # per-class row


def test_full_pipeline_determinism_on_synthetic():
    df = _synthetic_dataset()
    a = evaluate_oof(df, n_splits=3, random_state=0)
    b = evaluate_oof(df, n_splits=3, random_state=0)
    assert a["macro_f1"] == b["macro_f1"]
    assert a["baseline_macro_f1"] == b["baseline_macro_f1"]
    assert a["confusion"] == b["confusion"]
    assert a["oof_pred"] == b["oof_pred"]
