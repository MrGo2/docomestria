"""Job A — role classifier: load, split, baseline, train, report.

Trains a HistGradientBoosting classifier on .planning/extraction/training/role_table.csv
to predict the per-item `role`, evaluated leakage-free by PDF, and compares against a
raw-Docling-label baseline. See docs/superpowers/specs/2026-06-09-role-classifier...md.
"""
from __future__ import annotations

import pandas as pd

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
