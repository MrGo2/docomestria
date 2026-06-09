"""Compare current extraction against `.regression/baseline.json`.

Loads cached engine outputs from `data/parsebench/outputs/`, runs the current
`structural_extract_from_engines()`, and reports HIGH-pair deltas per PDF.

Exits with code 1 if any baseline HIGH pair is lost. Exits 0 otherwise.

Usage:
    PYTHONPATH=src python3 scripts/diff_vs_baseline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from docomestria.models import BBox, DoclingBlock, LiteItem, VisualRect
from docomestria.structural import structural_extract_from_engines

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "data" / "parsebench" / "outputs"
BASELINE = ROOT / ".regression" / "baseline.json"


def _bbox(d: dict) -> BBox:
    return BBox(x=d["x"], y=d["y"], w=d["w"], h=d["h"])


def load_docling(stem: str) -> list[DoclingBlock]:
    payload = json.loads((OUTPUTS / "docling" / f"{stem}.json").read_text())
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
    payload = json.loads((OUTPUTS / "liteparse" / f"{stem}.json").read_text())
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
    payload = json.loads((OUTPUTS / "pdfplumber" / f"{stem}.json").read_text())
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


def _pair_key(p: dict) -> tuple[str, str, int | None]:
    return (
        p["label"].strip().lower(),
        p["value"].strip().lower(),
        p.get("column_index"),
    )


def main() -> int:
    if not BASELINE.exists():
        print(f"ERR: baseline missing: {BASELINE}")
        return 2
    baseline = json.loads(BASELINE.read_text())
    print(f"Baseline @ {baseline['git_sha'][:7]}  captured {baseline['captured_at']}")
    print()

    any_loss = False
    for stem, expected in baseline["stems"].items():
        res = structural_extract_from_engines(
            load_docling(stem), load_lite(stem), load_plumber(stem)
        )
        high = [p for p in res.pairs if p.confidence.value == "high"]

        actual_keys = {
            (p.label_text.strip().lower(), p.value_text.strip().lower(), p.column_index)
            for p in high
        }
        expected_keys = {_pair_key(p) for p in expected["high_pairs"]}

        lost = expected_keys - actual_keys
        gained = actual_keys - expected_keys

        delta = len(high) - expected["high_count"]
        verdict = "OK" if not lost else "BLOCK"
        if lost:
            any_loss = True
        mark = "✅" if not lost else "❌"
        print(f"{mark} {stem:32s} {len(high):>3d} HIGH (baseline {expected['high_count']}, Δ{delta:+d})  {verdict}")
        if lost:
            print(f"     lost ({len(lost)}):")
            for lbl, val, col in sorted(lost, key=lambda x: (x[0], x[2] or 0, x[1])):
                col_s = f" (col {col})" if col else ""
                print(f"        - {lbl!r:40s} → {val!r}{col_s}")
        if gained:
            print(f"     gained ({len(gained)}):")
            for lbl, val, col in sorted(gained, key=lambda x: (x[0], x[2] or 0, x[1])):
                col_s = f" (col {col})" if col else ""
                print(f"        + {lbl!r:40s} → {val!r}{col_s}")
    print()
    if any_loss:
        print("VERDICT: BLOCK COMMIT — HIGH pairs lost")
        return 1
    print("VERDICT: OK — no HIGH-pair regressions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
