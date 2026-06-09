"""Dump raw atoms (engine outputs) for a single PDF page as JSON.

This is the data source for the kie-extractor agent. It runs all three
engines (pdfplumber, Docling, LiteParse v2) on one page and emits a
single self-contained JSON file with every piece of information the
agent needs to apply the structural pipeline (Capa 0 → Capa 9).

The output is *raw*: no role inference, no pairing, no hierarchy. The
agent reads this file and does the structural work.

Usage:
    PYTHONPATH=src python3 scripts/extract_atoms.py <pdf> --page N [--out PATH]

Output schema:
{
  "pdf":      "absolute/path.pdf",
  "page":     N,
  "page_size_pt": [W, H],
  "mediabox_offset_y": float,
  "atoms": {
    "spans":  [ ...LiteParse v2 spans with text/bbox/font/size/bold/case... ],
    "rects":  [ ...pdfplumber rects + lines + edges + images... ],
    "blocks": [ ...Docling blocks with label/bbox/text/heading_level/layer/cells... ]
  },
  "engine_diagnostics": { per-engine counts and label histograms }
}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from docomestria.text_features import case_class as _case_class, content_flags as _content_flags


def collect_liteparse(pdf_path: Path, page_num: int) -> list[dict]:
    from docomestria.engines import extract_lite_items
    from docomestria.structural.classify import is_bold

    out = []
    for it in extract_lite_items(str(pdf_path)):
        if it.page != page_num:
            continue
        text = it.text or ""
        out.append({
            "text": text,
            "bbox": {"x": it.bbox.x, "y": it.bbox.y,
                     "w": it.bbox.w, "h": it.bbox.h},
            "font_name": it.font_name,
            "font_size": it.font_size,
            "is_bold": is_bold(it.font_name),
            "case_class": _case_class(text),
            "content": _content_flags(text),
        })
    return out


def collect_pdfplumber(pdf_path: Path, page_num: int) -> dict:
    import pdfplumber

    out = {
        "page_size_pt": None,
        "mediabox_offset_y": 0.0,
        "rects": [],
        "lines": [],
        "horizontal_edges": [],
        "vertical_edges": [],
        "images": [],
        "tables": [],
    }
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_num - 1]
        media_lly = float(page.mediabox[1])
        page_w = float(page.width)
        page_h = float(page.height)
        out["page_size_pt"] = [page_w, page_h]
        out["mediabox_offset_y"] = media_lly

        # Rects — keep all, with derived bbox (top-left, page-relative).
        seen = set()
        for ridx, r in enumerate(page.rects or []):
            w = float(r["x1"]) - float(r["x0"])
            h = float(r["bottom"]) - float(r["top"])
            x = float(r["x0"])
            y = float(r["top"]) - media_lly
            key = (round(x, 1), round(y, 1), round(w, 1), round(h, 1))
            if key in seen:
                continue
            seen.add(key)
            out["rects"].append({
                "id": f"p{page_num}-r{ridx}",
                "bbox": {"x": x, "y": y, "w": w, "h": h},
                "is_substantial": w > 50 and h > 8,
                "is_checkbox_size": 5 <= w <= 18 and 5 <= h <= 18,
                "fill_color": r.get("non_stroking_color"),
                "stroke_color": r.get("stroking_color"),
            })

        # Lines (vector lines, not rect edges).
        for lidx, l in enumerate(page.lines or []):
            w = float(l["x1"]) - float(l["x0"])
            h = float(l["bottom"]) - float(l["top"])
            out["lines"].append({
                "id": f"p{page_num}-l{lidx}",
                "bbox": {
                    "x": float(l["x0"]),
                    "y": float(l["top"]) - media_lly,
                    "w": w, "h": h,
                },
                "orientation": "horizontal" if h < w else "vertical",
            })

        # Edges (derived h/v rules).
        for eidx, e in enumerate(page.horizontal_edges or []):
            out["horizontal_edges"].append({
                "id": f"p{page_num}-he{eidx}",
                "x0": float(e["x0"]),
                "x1": float(e["x1"]),
                "y": float(e["top"]) - media_lly,
                "width": float(e["x1"]) - float(e["x0"]),
            })
        for eidx, e in enumerate(page.vertical_edges or []):
            out["vertical_edges"].append({
                "id": f"p{page_num}-ve{eidx}",
                "x": float(e["x0"]),
                "y0": float(e["top"]) - media_lly,
                "y1": float(e["bottom"]) - media_lly,
                "height": float(e["bottom"]) - float(e["top"]),
            })

        # Images.
        for iidx, im in enumerate(page.images or []):
            out["images"].append({
                "id": f"p{page_num}-i{iidx}",
                "bbox": {
                    "x": float(im["x0"]),
                    "y": float(im["top"]) - media_lly,
                    "w": float(im["x1"]) - float(im["x0"]),
                    "h": float(im["bottom"]) - float(im["top"]),
                },
            })

        # Tables detected by find_tables() — outer bbox only.
        try:
            tables = page.find_tables() or []
        except Exception:
            tables = []
        for tidx, t in enumerate(tables):
            bbox = getattr(t, "bbox", None)
            if bbox is None:
                continue
            x0, top, x1, bottom = bbox
            rows = getattr(t, "rows", None) or []
            n_cols = max(
                (len(getattr(r, "cells", None) or []) for r in rows),
                default=0
            )
            out["tables"].append({
                "id": f"p{page_num}-t{tidx}",
                "bbox": {
                    "x": float(x0),
                    "y": float(top) - media_lly,
                    "w": float(x1 - x0),
                    "h": float(bottom - top),
                },
                "n_rows": len(rows),
                "n_cols": n_cols,
            })

    return out


def collect_docling(pdf_path: Path, page_num: int) -> list[dict]:
    """All Docling blocks on the page with rich per-cell flags."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TableFormerMode,
        TableStructureOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import (
        ContentLayer,
        SectionHeaderItem,
        TableItem,
    )

    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=True,
        force_backend_text=True,
        generate_page_images=False,
        generate_picture_images=False,
        table_structure_options=TableStructureOptions(
            mode=TableFormerMode.ACCURATE,
            do_cell_matching=True,
        ),
    )
    converter = DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    })
    doc = converter.convert(str(pdf_path)).document

    page_heights: dict[int, float] = {
        int(pno): float(page.size.height)
        for pno, page in doc.pages.items()
    }

    blocks = []
    for item, _level in doc.iterate_items(
        included_content_layers={
            ContentLayer.BODY,
            ContentLayer.FURNITURE,
        }
    ):
        if not getattr(item, "prov", None):
            continue
        prov = item.prov[0]
        page_no = int(prov.page_no)
        if page_no != page_num:
            continue
        ph = page_heights.get(page_no)
        if ph is None:
            continue
        l, t, r, b = prov.bbox.to_top_left_origin(page_height=ph).as_tuple()
        x, y = float(l), float(t)
        w = float(r) - float(l)
        h = float(b) - float(t)

        label_obj = getattr(item, "label", None)
        label = label_obj.value if hasattr(label_obj, "value") else str(label_obj)
        layer_obj = getattr(item, "content_layer", None)
        layer = layer_obj.value if hasattr(layer_obj, "value") else "body"

        # Formatting flags from Docling (if present).
        fmt = getattr(item, "formatting", None)
        formatting = None
        if fmt is not None:
            formatting = {
                "bold": getattr(fmt, "bold", False),
                "italic": getattr(fmt, "italic", False),
                "underline": getattr(fmt, "underline", False),
            }

        cells = None
        if isinstance(item, TableItem):
            try:
                data = getattr(item, "data", None)
                if data is not None:
                    grid = getattr(data, "grid", None) or []
                    cells = []
                    for row in grid:
                        row_cells = []
                        for c in row:
                            cell_bbox = getattr(c, "bbox", None)
                            cbb = None
                            if cell_bbox is not None:
                                cl, ct, cr, cb = cell_bbox.to_top_left_origin(
                                    page_height=ph
                                ).as_tuple()
                                cbb = {
                                    "x": float(cl), "y": float(ct),
                                    "w": float(cr) - float(cl),
                                    "h": float(cb) - float(ct),
                                }
                            row_cells.append({
                                "text": getattr(c, "text", "") or "",
                                "bbox": cbb,
                                "row_span": int(getattr(c, "row_span", 1)),
                                "col_span": int(getattr(c, "col_span", 1)),
                                "start_row_offset_idx": int(
                                    getattr(c, "start_row_offset_idx", -1)
                                ),
                                "end_row_offset_idx": int(
                                    getattr(c, "end_row_offset_idx", -1)
                                ),
                                "start_col_offset_idx": int(
                                    getattr(c, "start_col_offset_idx", -1)
                                ),
                                "end_col_offset_idx": int(
                                    getattr(c, "end_col_offset_idx", -1)
                                ),
                                "column_header": bool(getattr(c, "column_header", False)),
                                "row_header": bool(getattr(c, "row_header", False)),
                                "row_section": getattr(c, "row_section", None),
                                "fillable": bool(getattr(c, "fillable", False)),
                            })
                        cells.append(row_cells)
            except Exception:
                cells = None

        heading_level = None
        if isinstance(item, SectionHeaderItem):
            heading_level = int(getattr(item, "level", 0)) or None

        blocks.append({
            "label": label,
            "content_layer": layer,
            "bbox": {"x": x, "y": y, "w": w, "h": h},
            "text": (getattr(item, "text", "") or ""),
            "formatting": formatting,
            "heading_level": heading_level,
            "self_ref": getattr(item, "self_ref", None),
            "cells": cells,
        })
    return blocks


def main() -> int:
    from collections import Counter

    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--out", type=str, default=None,
                    help="Output JSON path (default: alongside the pdf)")
    args = ap.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    print(f"[atoms] {pdf_path.name} page {args.page}", file=sys.stderr)
    print(f"[atoms] pdfplumber …", file=sys.stderr)
    plumber = collect_pdfplumber(pdf_path, args.page)
    print(f"[atoms]   rects={len(plumber['rects'])} "
          f"lines={len(plumber['lines'])} "
          f"h_edges={len(plumber['horizontal_edges'])} "
          f"v_edges={len(plumber['vertical_edges'])} "
          f"images={len(plumber['images'])} "
          f"tables={len(plumber['tables'])}", file=sys.stderr)

    print(f"[atoms] liteparse v2 …", file=sys.stderr)
    spans = collect_liteparse(pdf_path, args.page)
    bold_n = sum(1 for s in spans if s["is_bold"])
    case_hist = Counter(s["case_class"] for s in spans)
    print(f"[atoms]   spans={len(spans)} bold={bold_n} cases={dict(case_hist)}",
          file=sys.stderr)

    print(f"[atoms] docling …", file=sys.stderr)
    blocks = collect_docling(pdf_path, args.page)
    label_hist = Counter(b["label"] for b in blocks)
    layer_hist = Counter(b["content_layer"] for b in blocks)
    print(f"[atoms]   blocks={len(blocks)} "
          f"labels={dict(label_hist)} layers={dict(layer_hist)}",
          file=sys.stderr)

    out = {
        "pdf": str(pdf_path),
        "page": args.page,
        "page_size_pt": plumber["page_size_pt"],
        "mediabox_offset_y": plumber["mediabox_offset_y"],
        "atoms": {
            "spans": spans,
            "rects": plumber["rects"],
            "lines": plumber["lines"],
            "horizontal_edges": plumber["horizontal_edges"],
            "vertical_edges": plumber["vertical_edges"],
            "images": plumber["images"],
            "pdfplumber_tables": plumber["tables"],
            "blocks": blocks,
        },
        "engine_diagnostics": {
            "pdfplumber": {
                "rects": len(plumber["rects"]),
                "lines": len(plumber["lines"]),
                "h_edges": len(plumber["horizontal_edges"]),
                "v_edges": len(plumber["vertical_edges"]),
                "images": len(plumber["images"]),
                "tables": len(plumber["tables"]),
            },
            "liteparse": {
                "spans": len(spans),
                "bold": bold_n,
                "cases": dict(case_hist),
            },
            "docling": {
                "blocks": len(blocks),
                "labels": dict(label_hist),
                "content_layers": dict(layer_hist),
            },
        },
    }

    out_path = (Path(args.out).resolve() if args.out
                else ROOT / ".planning" / "extraction" / "atoms"
                / f"{pdf_path.stem}-p{args.page:02d}.atoms.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"[atoms] → {out_path}", file=sys.stderr)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
