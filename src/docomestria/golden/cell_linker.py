"""link_cell — links one text-bearing cell to all 3 engines + adds KV signals.

Output: an evidence dict ready to attach to a leaf in the structured golden.
"""

from __future__ import annotations

from .engine_data import EngineData


def link_cell(eng: EngineData, text: str, y_hint: float,
              partner_bbox: dict | None = None) -> dict:
    """Link a cell to pdfplumber chars + LiteParse span + Docling cell.

    If `partner_bbox` is given (e.g. the label's bbox when linking its value),
    we also detect:
      - colon_signal: is there a ':' between partner_bbox and this cell?
      - value_extent: where does the value END on the right?
    """
    out = {
        "text": text, "row_y_hint": y_hint,
        "pdfplumber": None, "liteparse": None, "docling": None,
        "rect": None, "colon_signal": None, "value_extent": None,
    }
    if text is None or text == "":
        return out
    if isinstance(text, dict) and "ref" in text:
        out["ref"] = text["ref"]
        out["pdfplumber"] = {"note": f"reference to {text['ref']}"}
        return out

    # 1) pdfplumber chars
    cm = eng.find_char_bbox(str(text), y_hint=y_hint)
    if cm:
        out["pdfplumber"] = {
            "bbox": cm["bbox"],
            "char_indices": cm["char_indices"][:20],
            "n_chars": len(cm["char_indices"]),
            "row_y": cm["row_y"],
        }
    # 2) LiteParse span
    sid, sp = eng.find_span(str(text), y_hint=y_hint)
    if sp:
        out["liteparse"] = {
            "span_id": sid, "bbox": sp.get("bbox"),
            "case_class": sp.get("case_class"),
            "is_bold": sp.get("is_bold"),
            "font_size": sp.get("font_size"),
        }
    # 3) Docling cell
    did, dcell = eng.find_docling_cell(str(text), y_hint=y_hint)
    if dcell:
        out["docling"] = {
            "cell_ref": did, "bbox": dcell.get("bbox"),
            "column_header": dcell.get("column_header"),
            "row_header": dcell.get("row_header"),
        }
    # 4) Containing rect
    primary_bbox = ((out["pdfplumber"] or {}).get("bbox")
                    or (out["liteparse"] or {}).get("bbox"))
    if primary_bbox:
        rid, rect = eng.find_rect(primary_bbox)
        if rect:
            out["rect"] = {"rect_id": rid, "bbox": rect.get("bbox")}

    # Cell bbox: prefer pdfplumber (char-precise), then LiteParse, then Docling
    cell_bbox = ((out["pdfplumber"] or {}).get("bbox")
                 or (out["liteparse"] or {}).get("bbox")
                 or (out["docling"] or {}).get("bbox"))
    if cell_bbox:
        out["cell_bbox"] = cell_bbox
        out["engine_agreement"] = sum(
            1 for k in ("pdfplumber", "liteparse", "docling") if out[k]
        )

    # Colon between partner and value
    if partner_bbox and out.get("cell_bbox"):
        col = eng.colon_between(partner_bbox, out["cell_bbox"])
        if col:
            out["colon_signal"] = {"present": True,
                                    "char_x": col["x"], "char_y": col["y"]}
        else:
            out["colon_signal"] = {"present": False}

    # Value extent (boundary on the right)
    if partner_bbox and out.get("cell_bbox"):
        _, rect = eng.find_enclosing_rect(out["cell_bbox"])
        out["value_extent"] = eng.detect_value_extent(
            out["cell_bbox"],
            container_rect_bbox=rect.get("bbox") if rect else None,
        )
    return out
