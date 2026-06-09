"""Build live role-classifier feature rows (the FIELDS schema) for a production
PDF page, directly from the three engines. Mirrors golden/training_table.py's
row semantics but computes everything from LIVE engine outputs (no golden signal
dict) and fixes the colon quirk. The golden builder is not modified."""

from __future__ import annotations

import re

from .fusion import _best_docling_block, _find_cell, _smallest_containing_rect
from .golden.training_table import FIELDS, _onehot_case
from .models import BBox, DoclingBlock, LiteItem, VisualRect, WordItem
from .structural.classify import is_bold
from .text_features import case_class, content_flags

_COMPOUND_RE = re.compile(r"^\s*\S.*:\s*\S")


def _bbox_to_dict(bb: BBox) -> dict:
    return {"x": bb.x, "y": bb.y, "w": bb.w, "h": bb.h}


def _base_row(it: LiteItem, page_size_pt: tuple[float, float]) -> dict:
    """Provenance + content + typography + case + normalised geometry for one item.
    Engine-match, colon, neighbour, and label fields are filled later."""
    pw, ph = page_size_pt
    pw = pw or 1.0
    ph = ph or 1.0
    text = it.text.strip()

    row: dict = {f: "" for f in FIELDS}  # full schema, blanks filled below

    row["pdf"] = ""  # filled by build_live_rows
    row["page"] = it.page
    row["text"] = text
    row["node_path"] = ""
    row["source_node_type"] = "live_item"
    row["in_table"] = 0
    row["table_id"] = ""
    row["row_idx"] = ""
    row["col_id"] = ""
    row["role"] = ""

    row["x"] = it.bbox.x / pw
    row["y"] = it.bbox.y / ph
    row["w"] = it.bbox.w / pw
    row["h"] = it.bbox.h / ph

    row["font_size"] = it.font_size if it.font_size is not None else ""
    row["font_size_ratio"] = ""
    row["is_bold"] = 1 if is_bold(it.font_name) else 0
    row.update(_onehot_case(case_class(text)))

    row.update(content_flags(text))

    row["liteparse_present"] = 1

    return row


def _has_real_colon(it: LiteItem, words: list[WordItem]) -> int:
    """Real colon test: colon inside item text, or a detached ':' word hugging the
    item's right edge on the same baseline (tight 0.5*line-height tolerance both axes)."""
    if ":" in it.text:
        return 1
    ib = it.bbox
    iy_c = ib.y + ib.h / 2.0
    v_tol = 0.5 * ib.h
    h_tol = 0.5 * ib.h
    right = ib.x + ib.w
    for w in words:
        if w.page != it.page:
            continue
        if w.text.strip() != ":":
            continue
        wb = w.bbox
        if abs((wb.y + wb.h / 2.0) - iy_c) > v_tol:
            continue
        if right - h_tol <= wb.x <= right + h_tol:
            return 1
    return 0


def _any_word_overlaps(it: LiteItem, words: list[WordItem]) -> bool:
    a = _bbox_to_dict(it.bbox)
    for w in words:
        if w.page != it.page:
            continue
        b = _bbox_to_dict(w.bbox)
        ix = max(0.0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
        iy = max(0.0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
        if ix * iy > 0:
            return True
    return False


def _center_in_signature_rect(it: LiteItem, rects: list[VisualRect]) -> bool:
    cx = it.bbox.x + it.bbox.w / 2.0
    cy = it.bbox.y + it.bbox.h / 2.0
    for r in rects:
        if r.rect_type != "signature_field":
            continue
        b = r.bbox
        if b.x <= cx <= b.x + b.w and b.y <= cy <= b.y + b.h:
            return True
    return False


def _engine_features(
    it: LiteItem,
    blocks: list[DoclingBlock],
    rects: list[VisualRect],
    words: list[WordItem],
) -> dict:
    """Engine-match feature subset for one LiteItem."""
    feats: dict = {}

    # Docling block (sort by area ascending so "first containing" = smallest)
    sorted_blocks = sorted(blocks, key=lambda b: b.bbox.area)
    block, _method, _score = _best_docling_block(it, sorted_blocks)
    if block is not None:
        feats["docling_present"] = 1
        feats["docling_label"] = block.label or ""
        feats["docling_heading_level"] = (
            block.heading_level if block.heading_level is not None else ""
        )
        feats["docling_content_layer"] = block.content_layer or ""
    else:
        feats["docling_present"] = 0
        feats["docling_label"] = ""
        feats["docling_heading_level"] = ""
        feats["docling_content_layer"] = ""

    feats["pdfplumber_present"] = 1 if _any_word_overlaps(it, words) else 0

    sorted_rects = sorted(rects, key=lambda r: r.bbox.area)
    rect = _smallest_containing_rect(it, sorted_rects)
    feats["inside_rect"] = 1 if rect is not None else 0

    sorted_tables = sorted((r for r in rects if r.rect_type == "table"), key=lambda r: r.bbox.area)
    cell = _find_cell(it, sorted_tables)
    if cell is not None:
        table_id, row_idx, col_idx, _cell_bbox = cell
        feats["in_table"] = 1
        feats["table_id"] = str(table_id)
        feats["row_idx"] = str(row_idx)
        feats["col_id"] = str(col_idx)
    else:
        feats["in_table"] = 0
        feats["table_id"] = ""
        feats["row_idx"] = ""
        feats["col_id"] = ""

    feats["rect_is_signature_field"] = 1 if _center_in_signature_rect(it, rects) else 0

    feats["docling_column_header"] = 0
    feats["docling_row_header"] = 0

    feats["colon_present"] = _has_real_colon(it, words)
    feats["compound_span"] = 1 if _COMPOUND_RE.match(it.text) else 0
    feats["engine_agreement"] = 1 + feats["pdfplumber_present"] + feats["docling_present"]

    return feats
