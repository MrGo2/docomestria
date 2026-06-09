"""Build live role-classifier feature rows (the FIELDS schema) for a production
PDF page, directly from the three engines. Mirrors golden/training_table.py's
row semantics but computes everything from LIVE engine outputs (no golden signal
dict) and fixes the colon quirk. The golden builder is not modified."""

from __future__ import annotations

import re
import statistics

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
    # horizontal window around the item's right edge (scaled by line-height)
    x_tol = 0.5 * ib.h
    right = ib.x + ib.w
    for w in words:
        if w.page != it.page:
            continue
        if w.text.strip() != ":":
            continue
        wb = w.bbox
        if abs((wb.y + wb.h / 2.0) - iy_c) > v_tol:
            continue
        if right - x_tol <= wb.x <= right + x_tol:
            return 1
    return 0


def _any_word_overlaps(it: LiteItem, words: list[WordItem]) -> bool:
    return any(w.page == it.page and it.bbox.iou(w.bbox) > 0 for w in words)


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
) -> dict[str, int | str]:
    """Engine-match feature subset for one LiteItem."""
    feats: dict[str, int | str] = {}

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

    # live-uncomputable 0.0-importance columns: constant 0 to keep the FIELDS schema intact (NOT a stub)
    feats["docling_column_header"] = 0
    feats["docling_row_header"] = 0

    feats["colon_present"] = _has_real_colon(it, words)
    feats["compound_span"] = 1 if _COMPOUND_RE.match(it.text) else 0
    feats["engine_agreement"] = 1 + feats["pdfplumber_present"] + feats["docling_present"]

    return feats


_CENTER_TOL = 0.06  # fraction of page width (mirrors golden/training_table.py)


def build_live_rows(
    pdf: str,
    page: int,
    lite_items: list[LiteItem],
    docling_blocks: list[DoclingBlock],
    visual_rects: list[VisualRect],
    words: list[WordItem],
    page_size_pt: tuple[float, float],
) -> list[dict]:
    """One full FIELDS row per LiteItem for a single page (role left blank).

    Mirrors the page-level + neighbour feature semantics of
    golden/training_table.py:build_page_rows, computing from live engine outputs.
    """
    page_items = [it for it in lite_items if it.page == page]
    page_blocks = [b for b in docling_blocks if b.page == page]
    page_rects = [r for r in visual_rects if r.page == page]
    page_words = [w for w in words if w.page == page]

    rows: list[tuple[LiteItem, dict]] = []
    for it in page_items:
        row = _base_row(it, page_size_pt)
        row["pdf"] = pdf
        row.update(_engine_features(it, page_blocks, page_rects, page_words))
        rows.append((it, row))

    # --- page-level: font_size_ratio + is_centered over items with a font_size ---
    fonts = [
        it.font_size for it, _ in rows if isinstance(it.font_size, (int, float)) and it.font_size
    ]
    median_font = statistics.median(fonts) if fonts else 0.0
    for it, row in rows:
        fs = it.font_size
        row["font_size_ratio"] = (
            (fs / median_font) if (median_font and isinstance(fs, (int, float))) else ""
        )
        cx = row["x"] + row["w"] / 2.0
        row["is_centered"] = 1 if abs(cx - 0.5) <= _CENTER_TOL else 0

    # --- neighbour features: sort by (y, x) in normalised space ---
    ordered = sorted(rows, key=lambda pr: (pr[1]["y"], pr[1]["x"]))
    for idx, (_it, row) in enumerate(ordered):
        prv = ordered[idx - 1][1] if idx > 0 else None
        nxt = ordered[idx + 1][1] if idx + 1 < len(ordered) else None
        if prv is not None:
            row["gap_above"] = max(0.0, row["y"] - (prv["y"] + (prv["h"] or 0)))
        if nxt is not None:
            row["gap_below"] = max(0.0, nxt["y"] - (row["y"] + (row["h"] or 0)))
        if (
            nxt is not None
            and isinstance(row["font_size"], (int, float))
            and isinstance(nxt["font_size"], (int, float))
            and nxt["font_size"]
        ):
            row["font_ratio_vs_below"] = row["font_size"] / nxt["font_size"]
        cur_bold = row["is_bold"] in (1, True)
        nxt_known = nxt is not None and nxt["is_bold"] in (0, 1, True, False)
        nxt_bold = nxt is not None and nxt["is_bold"] in (1, True)
        row["bold_above_nonbold_below"] = 1 if (cur_bold and nxt_known and not nxt_bold) else 0

    return [row for _it, row in rows]
