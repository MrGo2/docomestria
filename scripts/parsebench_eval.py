"""Run structural extraction across every cached ParseBench PDF and report
per-document HIGH/MEDIUM/LOW pair counts plus aggregate coverage.

The cached engine outputs in `data/parsebench/outputs/{docling,liteparse,
pdfplumber}/<stem>.json` are the input — no engine re-runs happen here.
Use `scripts/run_engines_on_sample.py` first to populate the cache for
new PDFs.

Usage:
    PYTHONPATH=src python3 scripts/parsebench_eval.py
    PYTHONPATH=src python3 scripts/parsebench_eval.py --json > /tmp/eval.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from docomestria.models import BBox, DoclingBlock, LiteItem, VisualRect
from docomestria.structural import structural_extract_from_engines

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "data" / "parsebench" / "outputs"


def _bbox(d: dict) -> BBox:
    return BBox(x=d["x"], y=d["y"], w=d["w"], h=d["h"])


def _load_docling(stem: str) -> list[DoclingBlock] | None:
    path = OUTPUTS / "docling" / f"{stem}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    out = []
    for it in payload.get("items", ()):
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


def _load_lite(stem: str) -> list[LiteItem] | None:
    path = OUTPUTS / "liteparse" / f"{stem}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    return [
        LiteItem(
            text=it["text"],
            bbox=_bbox(it["bbox"]),
            font_name=it.get("font_name"),
            font_size=it.get("font_size"),
            page=it["page"],
        )
        for it in payload.get("items", ())
    ]


def _load_plumber(stem: str) -> list[VisualRect] | None:
    path = OUTPUTS / "pdfplumber" / f"{stem}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    out = []
    for it in payload.get("items", ()):
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


def _stems() -> list[str]:
    """List every stem with all three engine outputs cached."""
    stems = []
    for path in sorted((OUTPUTS / "docling").glob("*.json")):
        stem = path.stem
        if (OUTPUTS / "liteparse" / f"{stem}.json").exists() and (
            OUTPUTS / "pdfplumber" / f"{stem}.json"
        ).exists():
            stems.append(stem)
    return stems


def _family(stem: str) -> str:
    """Document family inferred from the stem prefix (delimited by '__')."""
    return stem.split("__", 1)[0] if "__" in stem else "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    args = ap.parse_args()

    stems = _stems()
    by_family: dict[str, list[dict]] = defaultdict(list)
    aggregate = Counter()

    for stem in stems:
        d = _load_docling(stem)
        l = _load_lite(stem)
        p = _load_plumber(stem)
        if d is None or l is None or p is None:
            continue
        try:
            res = structural_extract_from_engines(d, l, p)
        except Exception as exc:  # noqa: BLE001
            row = {
                "stem": stem,
                "error": f"{type(exc).__name__}: {exc}",
                "pages": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            }
            by_family[_family(stem)].append(row)
            continue

        high = sum(1 for x in res.pairs if x.confidence.value == "high")
        medium = sum(1 for x in res.pairs if x.confidence.value == "medium")
        low = sum(1 for x in res.pairs if x.confidence.value == "low")
        row = {
            "stem": stem,
            "pages": len(res.pages),
            "pair_count": len(res.pairs),
            "high": high,
            "medium": medium,
            "low": low,
        }
        by_family[_family(stem)].append(row)
        aggregate["pdfs"] += 1
        aggregate["high"] += high
        aggregate["medium"] += medium
        aggregate["low"] += low

    if args.json:
        out = {
            "schema_version": 1,
            "totals": dict(aggregate),
            "family_count": len(by_family),
            "families": dict(by_family),
            "pdf_count": sum(len(v) for v in by_family.values()),
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    print(f"ParseBench eval — {sum(len(v) for v in by_family.values())} PDFs, "
          f"{len(by_family)} families")
    print()
    for family in sorted(by_family):
        rows = by_family[family]
        fam_high = sum(r.get("high", 0) for r in rows)
        fam_med = sum(r.get("medium", 0) for r in rows)
        fam_low = sum(r.get("low", 0) for r in rows)
        print(f"=== {family} ({len(rows)} PDFs, {fam_high}H/{fam_med}M/{fam_low}L) ===")
        for row in rows:
            if "error" in row:
                print(f"  ❌ {row['stem']:60s}  {row['error']}")
            else:
                print(
                    f"  {row['stem']:60s}  "
                    f"{row['pages']:>2d}p  "
                    f"{row['high']:>3d}H  "
                    f"{row['medium']:>3d}M  "
                    f"{row['low']:>3d}L"
                )
        print()

    print("=== Aggregate ===")
    print(f"  PDFs processed:  {aggregate['pdfs']}")
    print(f"  Families:        {len(by_family)}")
    print(f"  HIGH pairs:      {aggregate['high']}")
    print(f"  MEDIUM pairs:    {aggregate['medium']}")
    print(f"  LOW pairs:       {aggregate['low']}")
    print()
    print("DoD condition #1 targets: ≥50 PDFs across ≥8 families, "
          "precision HIGH ≥95%, recall ≥85%.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
