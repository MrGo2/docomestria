"""Build the LIVE-feature training table: run the three engines on each golden
PDF, compute live features per LiteItem, transfer golden roles, write CSV +
coverage. Mirrors scripts/build_training_table.py but for live features.

Run: /Users/carlos/.pyenv/versions/3.12.9/bin/python scripts/build_live_feature_table.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docomestria.engines import (  # noqa: E402
    extract_docling_blocks,
    extract_lite_items,
    extract_page_sizes,
    extract_visual_rects,
    extract_words,
)
from docomestria.golden.training_table import write_csv  # noqa: E402
from docomestria.live_features import build_live_rows  # noqa: E402
from docomestria.live_labels import golden_annotated_items, transfer_labels  # noqa: E402

GOLDEN_DIR = ROOT / ".planning" / "extraction" / "golden"
ATOMS_DIR = ROOT / ".planning" / "extraction" / "atoms"
OUT_DIR = ROOT / ".planning" / "extraction" / "training"
OUT_CSV = OUT_DIR / "live_role_table.csv"
OUT_COV = OUT_DIR / "live_coverage.csv"

MIN_PAGES = 10  # refuse to build a near-empty (biased) table


def _has_structure(golden: dict) -> bool:
    return isinstance(golden.get("structure"), list) and len(golden["structure"]) > 0


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = []  # (golden_path, golden_dict, atoms_dict)
    for gp in sorted(GOLDEN_DIR.glob("*.json")):
        golden = json.loads(gp.read_text(encoding="utf-8"))
        if not _has_structure(golden):
            continue
        atoms_path = ATOMS_DIR / f"{gp.stem}.atoms.json"
        if not atoms_path.exists():
            raise SystemExit(f"ERROR: structure golden {gp.name} has no atoms at {atoms_path}")
        atoms = json.loads(atoms_path.read_text(encoding="utf-8"))
        pages.append((gp, golden, atoms))

    if len(pages) < MIN_PAGES:
        raise SystemExit(
            f"ERROR: only {len(pages)} pages (< {MIN_PAGES}); refusing to build a biased table"
        )

    cache: dict[str, dict] = {}

    def engines_for(pdf_path: str) -> dict:
        if pdf_path not in cache:
            cache[pdf_path] = {
                "lite": extract_lite_items(pdf_path),
                "docling": extract_docling_blocks(pdf_path),
                "rects": extract_visual_rects(pdf_path),
                "words": extract_words(pdf_path),
                "sizes": extract_page_sizes(pdf_path),
            }
        return cache[pdf_path]

    all_rows: list[dict] = []
    agg_total: dict[str, int] = {}
    agg_matched: dict[str, int] = {}
    for _gp, golden, atoms in pages:
        pdf_path = golden["pdf"]
        page = int(golden["page"])
        eng = engines_for(pdf_path)
        size = eng["sizes"].get(page, (1.0, 1.0))
        rows = build_live_rows(
            pdf_path,
            page,
            eng["lite"],
            eng["docling"],
            eng["rects"],
            eng["words"],
            size,
        )
        spans = (atoms.get("atoms", {}) or {}).get("spans", [])
        g_items = golden_annotated_items(golden, spans)
        labeled, cov = transfer_labels(rows, g_items)
        all_rows.extend(labeled)
        for role, d in cov["per_role"].items():
            agg_total[role] = agg_total.get(role, 0) + d["total"]
            agg_matched[role] = agg_matched.get(role, 0) + d["matched"]

    all_rows.sort(
        key=lambda r: (
            str(r["pdf"]),
            int(r["page"]) if str(r["page"]).isdigit() else 0,
            r["y"] if r["y"] != "" else 9.9,
            r["x"] if r["x"] != "" else 9.9,
        )
    )
    write_csv(all_rows, OUT_CSV)

    overall_t = sum(agg_total.values())
    overall_m = sum(agg_matched.values())
    with open(OUT_COV, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["role", "matched", "total", "pct"])
        for role in sorted(agg_total):
            t, m = agg_total[role], agg_matched.get(role, 0)
            w.writerow([role, m, t, round(100.0 * m / t, 2) if t else 0.0])
        w.writerow(
            [
                "__overall__",
                overall_m,
                overall_t,
                round(100.0 * overall_m / overall_t, 2) if overall_t else 0.0,
            ]
        )

    print(
        f"live_role_table.csv: {len(all_rows)} rows from {len(pages)} pages, "
        f"{len(cache)} PDFs -> {OUT_CSV}"
    )
    print(
        f"coverage: {overall_m}/{overall_t} = "
        f"{(100.0 * overall_m / overall_t) if overall_t else 0.0:.1f}% overall "
        f"-> {OUT_COV}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
