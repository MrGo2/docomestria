"""Build the role-classification training table from golden page-files + atoms.

See docs/superpowers/specs/2026-06-08-role-classification-training-table-design.md
"""
from __future__ import annotations

import csv
import os
import statistics
from dataclasses import dataclass, field

from docomestria.golden.engine_data import _norm, _contains
from docomestria.text_features import case_class as _case_class, content_flags

# Fixed column order. Provenance first, then label, then the feature vector.
FIELDS = [
    # provenance (not features)
    "pdf", "page", "text", "node_path", "source_node_type",
    "in_table", "table_id", "row_idx", "col_id",
    # label
    "role",
    # geometry (normalised 0-1 by page size)
    "x", "y", "w", "h",
    # typography
    "font_size", "font_size_ratio", "is_bold",
    "case_upper", "case_lower", "case_title", "case_mixed",
    # content (computed from the item's own text)
    "digit_ratio", "has_currency", "has_date", "has_percent",
    "has_iban", "has_nif", "starts_paren", "ends_colon",
    "n_numeric_tokens", "len_chars",
    # context
    "inside_rect", "colon_present", "engine_agreement",
    "pdfplumber_present", "liteparse_present", "docling_present",
    "docling_column_header", "docling_row_header", "compound_span",
    # neighbour
    "is_centered", "gap_above", "gap_below",
    "font_ratio_vs_below", "bold_above_nonbold_below",
]

_FLOAT_FIELDS = {
    "x", "y", "w", "h", "font_size", "font_size_ratio", "digit_ratio",
    "gap_above", "gap_below", "font_ratio_vs_below",
}


def _fmt(field_name: str, value) -> str:
    """Format one cell: bool -> 0/1, float -> 4dp, None/'' -> '' sentinel."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if field_name in _FLOAT_FIELDS and isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return str(value)


def write_csv(rows: list[dict], path) -> None:
    """Write rows to `path` atomically (temp + rename). Byte-deterministic.

    Uses csv.writer for RFC-correct quoting: the provenance `text` field can
    contain commas, embedded newlines or CRs (real corpus has both), and the
    writer quotes those cells so the column layout never breaks. Cell *values*
    are pre-formatted by `_fmt` (bool->0/1, float->4dp, missing->"") first.
    """
    path = os.fspath(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        w.writerow(FIELDS)
        for r in rows:
            w.writerow([_fmt(f, r.get(f, "")) for f in FIELDS])
    os.replace(tmp, path)
