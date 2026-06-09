"""Job A — role classifier: load, split, baseline, train, report.

Trains a HistGradientBoosting classifier on .planning/extraction/training/role_table.csv
to predict the per-item `role`, evaluated leakage-free by PDF, and compares against a
raw-Docling-label baseline. See docs/superpowers/specs/2026-06-09-role-classifier...md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import OneHotEncoder
from sklearn.utils.class_weight import compute_sample_weight

LABEL_COL = "role"
GROUP_COL = "pdf"

# Provenance columns excluded from X (leak the answer or aren't real signals).
PROVENANCE_COLS = [
    "pdf", "page", "text", "node_path", "source_node_type",
    "in_table", "table_id", "row_idx", "col_id", "role",
]

# Low-cardinality categorical strings (one-hot encoded; rest are numeric).
CATEGORICAL_COLS = ["docling_label", "docling_content_layer"]

# Single source of truth: feature columns = the builder's FIELDS minus provenance.
# This auto-tracks the 4 docling/signature columns appended in Phase 1 (Task 2) and can
# never drift from the CSV header (write_csv writes FIELDS as the header row).
from docomestria.golden.training_table import FIELDS as _FIELDS

FEATURE_COLS = [c for c in _FIELDS if c not in PROVENANCE_COLS]
NUMERIC_COLS = [c for c in FEATURE_COLS if c not in CATEGORICAL_COLS]


def load_dataset(path) -> pd.DataFrame:
    """Read the role table; empty cells -> NaN. Categorical cols kept as strings."""
    df = pd.read_csv(path, dtype={c: "string" for c in CATEGORICAL_COLS})
    return df


def docling_baseline_predict(train: pd.DataFrame, test: pd.DataFrame) -> tuple[list, float]:
    """Predict role = train-fold majority role per docling_label; missing/unseen -> global
    train majority. Returns (predictions, share_of_test_rows_using_fallback)."""
    global_majority = train[LABEL_COL].mode().iloc[0]
    label_to_role = {}
    for lab, grp in train.groupby(train["docling_label"], dropna=True):
        label_to_role[lab] = grp[LABEL_COL].mode().iloc[0]
    preds, fallback = [], 0
    for lab in test["docling_label"]:
        if pd.isna(lab) or lab not in label_to_role:
            preds.append(global_majority)
            fallback += 1
        else:
            preds.append(label_to_role[lab])
    return preds, (fallback / len(test) if len(test) else 0.0)


def _new_model(random_state: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(random_state=random_state)


def evaluate_oof(df: pd.DataFrame, n_splits: int = 5, random_state: int = 0) -> dict:
    """GroupKFold-by-pdf; collect pooled out-of-fold predictions for the model and the
    Docling baseline; return a metrics dict (all computed on pooled OOF). No (text,role)
    dedup — leakage is prevented by GroupKFold-by-pdf alone (per user decision)."""
    df = df.reset_index(drop=True)
    y = df[LABEL_COL].to_numpy()
    groups = df[GROUP_COL].to_numpy()
    labels = sorted(pd.unique(y).tolist())

    oof_pred = np.empty(len(df), dtype=object)
    base_pred = np.empty(len(df), dtype=object)
    fallback_shares = []

    gkf = GroupKFold(n_splits=n_splits)
    for tr_idx, te_idx in gkf.split(df, y, groups):
        tr, te = df.iloc[tr_idx], df.iloc[te_idx]
        ohe = build_encoder(tr[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
        Xtr = encode_features(ohe, tr[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
        Xte = encode_features(ohe, te[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
        ytr = tr[LABEL_COL].to_numpy()
        sw = compute_sample_weight("balanced", ytr)
        model = _new_model(random_state)
        model.fit(Xtr, ytr, sample_weight=sw)
        oof_pred[te_idx] = model.predict(Xte)
        bp, fb = docling_baseline_predict(tr, te)
        base_pred[te_idx] = np.array(bp, dtype=object)
        fallback_shares.append(fb)

    report = classification_report(y, oof_pred, labels=labels,
                                   output_dict=True, zero_division=0)
    cm = confusion_matrix(y, oof_pred, labels=labels).tolist()
    return {
        "macro_f1": float(f1_score(y, oof_pred, labels=labels, average="macro", zero_division=0)),
        "baseline_macro_f1": float(f1_score(y, base_pred, labels=labels, average="macro", zero_division=0)),
        "baseline_fallback_share": float(np.mean(fallback_shares)),
        "per_class": {lab: report[lab] for lab in labels},
        "confusion": cm,
        "labels": labels,
        "oof_pred": oof_pred.tolist(),
        "n_rows": len(df),
        "sklearn_version": sklearn.__version__,
    }


def fit_final_model(df: pd.DataFrame, random_state: int = 0) -> dict:
    """Refit the encoder + model on ALL rows; return a picklable artifact dict."""
    ohe = build_encoder(df[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    X = encode_features(ohe, df[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    y = df[LABEL_COL].to_numpy()
    sw = compute_sample_weight("balanced", y)
    model = _new_model(random_state)
    model.fit(X, y, sample_weight=sw)
    return {
        "model": model, "ohe": ohe, "feature_cols": FEATURE_COLS,
        "numeric_cols": NUMERIC_COLS, "categorical_cols": CATEGORICAL_COLS,
        "labels": sorted(pd.unique(y).tolist()), "sklearn_version": sklearn.__version__,
    }


def _encoded_feature_names(ohe) -> list[str]:
    cat_names = ohe.get_feature_names_out(CATEGORICAL_COLS).tolist()
    return list(NUMERIC_COLS) + cat_names


def feature_importances(df: pd.DataFrame, n_splits: int = 5, random_state: int = 0,
                        n_repeats: int = 5) -> list[tuple[str, float]]:
    """Permutation importances computed on one held-out GroupKFold fold."""
    df = df.reset_index(drop=True)
    y = df[LABEL_COL].to_numpy()
    groups = df[GROUP_COL].to_numpy()
    gkf = GroupKFold(n_splits=n_splits)
    tr_idx, te_idx = next(gkf.split(df, y, groups))
    tr, te = df.iloc[tr_idx], df.iloc[te_idx]
    ohe = build_encoder(tr[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    Xtr = encode_features(ohe, tr[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    Xte = encode_features(ohe, te[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    model = _new_model(random_state)
    model.fit(Xtr, tr[LABEL_COL].to_numpy(),
              sample_weight=compute_sample_weight("balanced", tr[LABEL_COL].to_numpy()))
    r = permutation_importance(model, Xte, te[LABEL_COL].to_numpy(),
                               n_repeats=n_repeats, random_state=random_state,
                               scoring="f1_macro")
    names = _encoded_feature_names(ohe)
    pairs = sorted(zip(names, r.importances_mean.tolist()), key=lambda t: t[1], reverse=True)
    return pairs


def build_encoder(train_X: pd.DataFrame, numeric: list[str], categorical: list[str]):
    """Fit a OneHotEncoder on the categorical columns of the TRAIN fold only."""
    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    ohe.fit(train_X[categorical].astype("string").fillna("__nan__"))
    return ohe


def encode_features(ohe, X: pd.DataFrame, numeric: list[str], categorical: list[str]) -> np.ndarray:
    """Numeric block (float, NaN preserved) hstacked with the one-hot categorical block.
    Column order: numeric columns first (in `numeric` order), then one-hot block."""
    num = X[numeric].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    cat = ohe.transform(X[categorical].astype("string").fillna("__nan__"))
    return np.hstack([num, cat])


def render_report_md(result: dict, importances: list[tuple[str, float]]) -> str:
    lines = ["# Role Classifier — Report (Job A)", ""]
    delta = result["macro_f1"] - result["baseline_macro_f1"]
    lines += [
        f"- **Macro-F1 (pooled OOF):** {result['macro_f1']:.4f}",
        f"- **vs Docling baseline:** {result['baseline_macro_f1']:.4f} "
        f"(delta {delta:+.4f}, fallback share {result['baseline_fallback_share']:.3f})",
        f"- Rows: {result['n_rows']} (dedup: disabled (GroupKFold-by-pdf)) "
        f"| sklearn {result['sklearn_version']}",
        "", "## Per-class", "", "| role | precision | recall | f1 | support |",
        "|---|---|---|---|---|",
    ]
    for lab in result["labels"]:
        m = result["per_class"][lab]
        lines.append(f"| {lab} | {m['precision']:.3f} | {m['recall']:.3f} "
                     f"| {m['f1-score']:.3f} | {int(m['support'])} |")
    lines += ["", "## Confusion (rows=true, cols=pred)", "",
              "| | " + " | ".join(result["labels"]) + " |",
              "|" + "---|" * (len(result["labels"]) + 1)]
    for lab, row in zip(result["labels"], result["confusion"]):
        lines.append(f"| **{lab}** | " + " | ".join(str(v) for v in row) + " |")
    lines += ["", "## Top feature importances", ""]
    for name, imp in importances[:25]:
        lines.append(f"- {name}: {imp:.4f}")
    return "\n".join(lines) + "\n"
