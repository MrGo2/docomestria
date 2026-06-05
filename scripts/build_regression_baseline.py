"""Rebuild `.regression/baseline.json` from current code + cached engine outputs.

Captures HIGH-confidence pairs for each of the 5 azuredemo PDFs, along with
their `column_index`, `rule`, and `score`. The diff script
(`scripts/diff_vs_baseline.py`) compares future runs to this snapshot.

Usage:
    PYTHONPATH=src python3 scripts/build_regression_baseline.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from docomestria.models import BBox, DoclingBlock, LiteItem, VisualRect
from docomestria.structural import structural_extract_from_engines

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "data" / "parsebench" / "outputs"
BASELINE = ROOT / ".regression" / "baseline.json"

STEMS = (
    "azuredemo__LABORAL",
    "azuredemo__PATRIMONIAL",
    "azuredemo__BBVA3",
    "azuredemo__BBVA4",
    "azuredemo__BBVA5",
)


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


def main() -> int:
    git_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT
    ).decode().strip()
    git_dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT
    ).decode().strip())

    stems: dict[str, dict] = {}
    for stem in STEMS:
        res = structural_extract_from_engines(
            load_docling(stem), load_lite(stem), load_plumber(stem)
        )
        high_pairs = [
            {
                "label": p.label_text,
                "value": p.value_text,
                "rule": next(iter(p.evidence), "") if p.evidence else "",
                "score": round(p.score, 2),
                "page": p.page,
                "column_index": p.column_index,
            }
            for p in res.pairs if p.confidence.value == "high"
        ]
        stems[stem] = {
            "high_count": len(high_pairs),
            "high_pairs": high_pairs,
        }
        print(f"  {stem}: {len(high_pairs)} HIGH")

    baseline = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "stems": stems,
    }
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(baseline, indent=2, ensure_ascii=False))
    print()
    print(f"Wrote {BASELINE}")
    print(f"  git_sha: {git_sha[:7]}{' (dirty)' if git_dirty else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
