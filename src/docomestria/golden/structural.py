"""link_structural_node — attach engine evidence to non-leaf nodes
(section / table / array / kv_group / free_text_list).
"""

from __future__ import annotations

from collections import Counter

from .cell_linker import link_cell
from .engine_data import EngineData


def _container_score(rect, dblock, edges) -> int:
    score = 0
    if rect: score += 1
    if dblock: score += 1
    if edges and (edges.get("vertical", 0) + edges.get("horizontal", 0)) >= 2:
        score += 1
    return score


def link_structural_node(eng: EngineData, node: dict, parent_chain: list) -> dict:
    """Returns evidence dict for the structural node (title + container + signals)."""
    ntype = node.get("type")
    title = node.get("title")
    y_hint = node.get("y_hint")

    out = {
        "title_signal": None,
        "container_signal": None,
        "structural_signals": None,
    }

    # 1) Title signal
    if title:
        title_ev = link_cell(eng, title, y_hint)
        out["title_signal"] = {
            "text": title,
            "pdfplumber": title_ev.get("pdfplumber"),
            "liteparse": title_ev.get("liteparse"),
            "docling": title_ev.get("docling"),
            "bbox": title_ev.get("cell_bbox"),
            "engine_agreement": title_ev.get("engine_agreement", 0),
        }

    # 2) Container signal
    cbb = node.get("container_bbox") or node.get("bbox")
    if cbb:
        rid, rect = eng.find_enclosing_rect(cbb)
        prefer = ("table", "form_area", "key_value_area", "key_value_region")
        dblock = eng.find_enclosing_docling_block(cbb, prefer_labels=prefer)
        edges = eng.count_edges_inside(cbb)
        n_colons = eng.colons_inside(cbb)
        out["container_signal"] = {
            "container_bbox": cbb,
            "pdfplumber_rect": ({"rect_id": rid, "bbox": rect.get("bbox")}
                                if rect else None),
            "docling_block": ({"self_ref": dblock.get("self_ref"),
                               "label": dblock.get("label"),
                               "bbox": dblock.get("bbox")}
                              if dblock else None),
            "edges_inside": edges,
            "colons_inside": n_colons,
            "container_score": _container_score(rect, dblock, edges),
        }

    # 3) Type-specific structural signals
    if ntype == "table":
        cols = node.get("columns") or []
        rows = node.get("rows") or []
        edges = (out["container_signal"] or {}).get("edges_inside") or {}
        cont = out["container_signal"] or {}
        out["structural_signals"] = {
            "kind": "table",
            "n_columns_declared": len(cols),
            "n_rows_declared": len(rows),
            "n_columns_with_group": sum(1 for c in cols if c.get("group")),
            "header_levels": node.get("header_levels", 1),
            "vertical_edges_inside": edges.get("vertical", 0),
            "horizontal_edges_inside": edges.get("horizontal", 0),
            "has_docling_table_block": bool(
                cont.get("docling_block")
                and (cont.get("docling_block") or {}).get("label") == "table"
            ),
            "has_pdfplumber_rect_frame": bool(cont.get("pdfplumber_rect")),
        }
    elif ntype == "array":
        items = node.get("items") or []
        repeat_text = None
        if items:
            first = items[0]
            if isinstance(first, dict):
                # Look for the first sub-object with a 'title'
                for k, v in first.items():
                    if isinstance(v, dict) and v.get("title"):
                        repeat_text = v["title"]
                        break
        repeats = eng.detect_repeats(repeat_text) if repeat_text else []
        ys = [h.get("y") for h in repeats if h.get("y") is not None]
        xs = [h.get("bbox", {}).get("x") for h in repeats
              if h.get("bbox") and "x" in h["bbox"]]
        n_same_y = 0
        if len(ys) >= 2:
            ys_sorted = sorted(ys)
            for i in range(len(ys_sorted) - 1):
                if abs(ys_sorted[i + 1] - ys_sorted[i]) < 5:
                    n_same_y += 1
        out["structural_signals"] = {
            "kind": "array",
            "n_items_declared": len(items),
            "repeat_anchor_text": repeat_text,
            "n_anchor_hits": len(repeats),
            "n_anchor_hits_same_y": n_same_y,
            "anchor_xs": xs[:6],
            "column_boundary_x_estimate": (
                (max(xs) + min(xs)) / 2 if len(xs) >= 2 else None
            ),
        }
    elif ntype == "kv_group":
        pairs = node.get("pairs") or []
        inline_ratio = 0.0
        if pairs:
            first_y = pairs[0].get("y_hint")
            inline_ratio = sum(1 for p in pairs
                               if p.get("y_hint") == first_y) / len(pairs)
        out["structural_signals"] = {
            "kind": "kv_group",
            "n_pairs": len(pairs),
            "layout": ("inline_horizontal" if inline_ratio > 0.8
                       else "stacked_vertical"),
            "same_row_ratio": inline_ratio,
        }
    elif ntype == "section":
        children = node.get("children") or []
        child_types = [c.get("type") for c in children if isinstance(c, dict)]
        out["structural_signals"] = {
            "kind": "section",
            "n_children": len(children),
            "child_type_distribution": dict(Counter(child_types)),
            "path": "/".join(parent_chain + [title or ""]),
        }
    elif ntype == "free_text_list":
        out["structural_signals"] = {
            "kind": "free_text_list",
            "n_items": len(node.get("items") or []),
        }

    return out
