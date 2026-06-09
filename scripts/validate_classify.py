"""Validate structural/classify.py against the engine outputs we have on disk.

Reads `data/parsebench/outputs/liteparse/<stem>.json`, reconstructs LiteItems
from the serialized payload, runs `classify()`, and prints a row-per-item
table so we can eyeball whether each item ended up with the expected kind.

Usage:
    python scripts/validate_classify.py azuredemo__LABORAL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from docomestria.models import BBox, LiteItem
from docomestria.structural import classify, dominant_font_size

ROOT = Path(__file__).resolve().parent.parent / "data" / "parsebench"
LITEPARSE_DIR = ROOT / "outputs" / "liteparse"


def load_liteitems(stem: str) -> list[LiteItem]:
    payload = json.loads((LITEPARSE_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    out: list[LiteItem] = []
    for it in payload["items"]:
        b = it["bbox"]
        out.append(
            LiteItem(
                text=it["text"],
                bbox=BBox(x=b["x"], y=b["y"], w=b["w"], h=b["h"]),
                font_name=it.get("font_name"),
                font_size=it.get("font_size"),
                page=it["page"],
            )
        )
    return out


def main() -> None:
    if len(sys.argv) < 2:
        stems = sorted(p.stem for p in LITEPARSE_DIR.glob("*.json"))
        print("Usage: python scripts/validate_classify.py <stem>")
        print("\nAvailable stems:")
        for s in stems:
            print(f"  {s}")
        sys.exit(1)

    stem = sys.argv[1].removesuffix(".pdf").removesuffix(".json")
    items = load_liteitems(stem)
    dominant = dominant_font_size(items)
    classified = classify(items)

    print(f"PDF stem: {stem}")
    print(f"Items: {len(items)}")
    print(f"Dominant font size: {dominant}")
    print()
    print(f"{'#':>3}  {'kind':<8}  {'page':>4}  {'Y':>6}  {'size':>5}  bold  {'text':<60}  evidence")
    print("-" * 140)
    for i, ci in enumerate(classified):
        text = (ci.text or "").replace("\n", " ⏎ ")
        if len(text) > 58:
            text = text[:55] + "..."
        size = f"{ci.item.font_size:.1f}" if ci.item.font_size else "-"
        bold = "✓" if (ci.item.font_name and "bold" in ci.item.font_name.lower()) else " "
        ev = ",".join(ci.evidence)
        print(
            f"{i:>3}  {ci.kind.value:<8}  {ci.page:>4}  "
            f"{ci.bbox.y:>6.1f}  {size:>5}   {bold}   {text:<60}  {ev}"
        )

    # Compact summary by kind
    print()
    from collections import Counter
    by_kind = Counter(ci.kind.value for ci in classified)
    print("Kind summary:", dict(by_kind))


if __name__ == "__main__":
    main()
