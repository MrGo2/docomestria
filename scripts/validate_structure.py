"""Validate structural/structure.py against saved engine outputs.

Reconstructs Docling / LiteParse / pdfplumber outputs from JSON, runs
`detect_structure()`, and prints a per-page breakdown of:
  - Sections (from Docling section_header)
  - Tables (fused) with cell preview + sub-sections
  - Boxes (pdfplumber rect_type=box)
  - Furniture regions (Docling content_layer=furniture)
  - Picture regions (Docling label=picture)

Usage:
    python scripts/validate_structure.py azuredemo__LABORAL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from docomestria.models import BBox, DoclingBlock, LiteItem, VisualRect
from docomestria.structural import detect_structure

ROOT = Path(__file__).resolve().parent.parent / "data" / "parsebench" / "outputs"


def _bbox(d: dict) -> BBox:
    return BBox(x=d["x"], y=d["y"], w=d["w"], h=d["h"])


def load_docling(stem: str) -> list[DoclingBlock]:
    payload = json.loads((ROOT / "docling" / f"{stem}.json").read_text())
    out = []
    for it in payload["items"]:
        cells = it.get("cells")
        out.append(
            DoclingBlock(
                bbox=_bbox(it["bbox"]),
                label=it["label"],
                heading_level=it.get("heading_level"),
                content_layer=it.get("content_layer", "body"),
                page=it["page"],
                text=it.get("text") or "",
                self_ref=it.get("self_ref"),
                cells=tuple(tuple(r) for r in cells) if cells else None,
            )
        )
    return out


def load_lite(stem: str) -> list[LiteItem]:
    payload = json.loads((ROOT / "liteparse" / f"{stem}.json").read_text())
    return [
        LiteItem(
            text=it["text"],
            bbox=_bbox(it["bbox"]),
            font_name=it.get("font_name"),
            font_size=it.get("font_size"),
            page=it["page"],
        )
        for it in payload["items"]
    ]


def load_plumber(stem: str) -> list[VisualRect]:
    payload = json.loads((ROOT / "pdfplumber" / f"{stem}.json").read_text())
    out = []
    for it in payload["items"]:
        cells = it.get("cells")
        out.append(
            VisualRect(
                bbox=_bbox(it["bbox"]),
                is_checkbox=it.get("is_checkbox", False),
                is_filled=it.get("is_filled", False),
                page=it["page"],
                rect_id=it.get("rect_id", ""),
                rect_type=it.get("rect_type", "box"),
                cells=tuple(tuple(r) for r in cells) if cells else None,
            )
        )
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_structure.py <stem>")
        sys.exit(1)
    stem = sys.argv[1].removesuffix(".pdf").removesuffix(".json")

    d, l, p = load_docling(stem), load_lite(stem), load_plumber(stem)
    print(f"=== {stem} ===")
    print(f"  Docling blocks: {len(d)}  LiteItems: {len(l)}  VisualRects: {len(p)}")
    print()

    pages = detect_structure(d, l, p)
    for page in pages:
        print(f"--- Page {page.number} ---")
        print(f"  Sections: {len(page.sections)}")
        for s in page.sections:
            print(f"    lvl={s.level}  Y={s.bbox.y:.0f}  '{s.title}'")
        print(f"  Furniture regions: {len(page.furniture_regions)}")
        print(f"  Picture regions: {len(page.picture_regions)}")
        print(f"  Boxes: {len(page.boxes)}")
        for b in page.boxes:
            print(f"    Y={b.bbox.y:.0f}  h={b.bbox.h:.0f}  w={b.bbox.w:.0f}")
        print(f"  Tables: {len(page.tables)}")
        for t in page.tables:
            ncells = f"{len(t.cells)}x{max((len(r) for r in t.cells), default=0)}" if t.cells else "no cells"
            print(f"    [{t.source}] Y={t.bbox.y:.0f}  h={t.bbox.h:.0f}  {ncells}"
                  f"  subsections={len(t.subsections)}")
            if t.cells:
                for r, row in enumerate(t.cells[:3]):
                    preview = [c[:40] for c in row]
                    print(f"      row {r}: {preview}")
                if len(t.cells) > 3:
                    print(f"      ... +{len(t.cells)-3} more rows")
            for sub in t.subsections:
                print(f"      sub: Y={sub.header_bbox.y:.0f}  '{sub.header_text}'")
        print()


if __name__ == "__main__":
    main()
