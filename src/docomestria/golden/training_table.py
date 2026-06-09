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


_CASE_ONEHOT = {
    "UPPER": "case_upper",
    "lower": "case_lower",
    "Title": "case_title",
    "mixed": "case_mixed",
}


def _onehot_case(value: str) -> dict:
    out = {k: 0 for k in _CASE_ONEHOT.values()}
    col = _CASE_ONEHOT.get(value)
    if col:
        out[col] = 1
    return out  # an unrecognised value (incl. "none") leaves all four at 0


def signal_features(signal: dict | None) -> dict:
    """Extract typography/context features + span_id from a golden signal dict.

    Returns "" for absent numeric features and 0 for absent flags. `span_id`
    is the liteparse span index (or None) — used for compound detection and to
    mark atoms consumed.
    """
    lp = (signal or {}).get("liteparse") or None
    dl = (signal or {}).get("docling") or None
    case = (lp or {}).get("case_class", "")
    out = {
        "font_size": (lp or {}).get("font_size", "") if lp else "",
        "is_bold": bool((lp or {}).get("is_bold")) if lp else "",
        "liteparse_present": 1 if lp else 0,
        "pdfplumber_present": 1 if (signal or {}).get("pdfplumber") else 0,
        "docling_present": 1 if dl else 0,
        "docling_column_header": 1 if (dl or {}).get("column_header") else 0,
        "docling_row_header": 1 if (dl or {}).get("row_header") else 0,
        "inside_rect": 1 if (signal or {}).get("rect") else 0,
        "colon_present": 1 if (signal or {}).get("colon_signal") else 0,
        "engine_agreement": ((signal or {}).get("engine_agreement") or 0),
        "span_id": (lp or {}).get("span_id") if lp else None,
    }
    out.update(_onehot_case(case))
    return out
