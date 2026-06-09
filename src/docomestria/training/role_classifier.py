"""Job A — role classifier: load, split, baseline, train, report.

Trains a HistGradientBoosting classifier on .planning/extraction/training/role_table.csv
to predict the per-item `role`, evaluated leakage-free by PDF, and compares against a
raw-Docling-label baseline. See docs/superpowers/specs/2026-06-09-role-classifier...md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

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


def dedupe_text_role(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop exact-duplicate (text, role) rows (keep first). Returns (df, n_dropped)."""
    before = len(df)
    out = df.drop_duplicates(subset=["text", LABEL_COL], keep="first").reset_index(drop=True)
    return out, before - len(out)


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
