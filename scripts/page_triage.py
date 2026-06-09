"""Quick per-page structural-richness triage for a PDF.

Decides which pages of a PDF are worth running through the
full kie-extractor pipeline. Uses only pdfplumber + LiteParse v2
(fast, deterministic, no ML) — Docling stays out so the whole PDF
triages in seconds.

For each page, computes:
- counts of substantial rects, lines, vertical edges, images
- LiteParse span counts (total, bold, by case-class)
- median font size and "size diversity" (signals hierarchy)
- KV-pattern signals: lower→UPPER pairs, numeric-after-bold, etc.
- a single composite `structural_score` in [0, 100]
- a `verdict` ∈ {extract, skip, low_priority}

Usage:
    PYTHONPATH=src python3 scripts/page_triage.py <pdf> [--out PATH]

Output: JSON to .planning/extraction/triage/<pdf_stem>.triage.json
        and a one-line summary per page to stderr.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


_NUM_TOKEN = re.compile(r"\b\d[\d.,/\-]*\b")


def _case_class(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "none"
    up = sum(1 for c in letters if c.isupper())
    lo = sum(1 for c in letters if c.islower())
    if up / len(letters) >= 0.80:
        return "UPPER"
    if lo / len(letters) >= 0.80:
        return "lower"
    words = [w for w in text.split() if any(ch.isalpha() for ch in w)]
    if words:
        starts_upper = sum(
            1 for w in words
            if next((c for c in w if c.isalpha()), "").isupper()
        )
        if starts_upper / len(words) >= 0.70:
            return "Title"
    return "mixed"


def _kv_pattern_signal(spans: list[dict]) -> int:
    """Count rough KV pair candidates (lower→UPPER/none on same y-band)."""
    n = 0
    by_y: dict[int, list[dict]] = {}
    for s in spans:
        if s["size"] < 7:
            continue
        key = round(s["y"] / 4) * 4
        by_y.setdefault(key, []).append(s)
    for row_spans in by_y.values():
        row_spans.sort(key=lambda s: s["x"])
        for i in range(len(row_spans) - 1):
            a, b = row_spans[i], row_spans[i + 1]
            if a["case"] == "lower" and b["case"] in ("UPPER", "none"):
                n += 1
            elif a["case"] == "lower" and any(
                c.isdigit() for c in b["text"]
            ):
                n += 1
    return n


def triage_page(pdf_path: Path, page_num: int) -> dict:
    import pdfplumber  # type: ignore[import-not-found]

    from docomestria.engines import extract_lite_items
    from docomestria.structural.classify import is_bold

    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_num - 1]
        media_lly = float(page.mediabox[1])
        page_w = float(page.width)
        page_h = float(page.height)
        rects_all = page.rects or []
        rects_sub = [r for r in rects_all
                     if (float(r["x1"]) - float(r["x0"])) > 50
                     and (float(r["bottom"]) - float(r["top"])) > 8]
        lines = page.lines or []
        v_edges = page.vertical_edges or []
        h_edges = page.horizontal_edges or []
        images = page.images or []
        try:
            tables = page.find_tables() or []
        except Exception:
            tables = []

    spans_raw = [it for it in extract_lite_items(str(pdf_path))
                 if it.page == page_num]
    spans = [
        {
            "text": it.text or "",
            "x": it.bbox.x, "y": it.bbox.y, "w": it.bbox.w, "h": it.bbox.h,
            "size": float(it.font_size or 0.0),
            "bold": is_bold(it.font_name),
            "case": _case_class(it.text or ""),
        }
        for it in spans_raw
    ]
    spans_struct = [s for s in spans if s["size"] >= 7]
    bold_n = sum(1 for s in spans_struct if s["bold"])
    case_hist = Counter(s["case"] for s in spans_struct)
    sizes = [s["size"] for s in spans_struct if s["size"] > 0]
    size_median = float(statistics.median(sizes)) if sizes else 0.0
    size_uniq = len({round(s, 1) for s in sizes})
    size_diversity = float(size_uniq) / max(1, len(sizes)) if sizes else 0.0
    kv_signals = _kv_pattern_signal(spans)

    # ── Composite score ────────────────────────────────────────────────
    # Each signal contributes [0, 20] points; total in [0, 100].
    s_rects = min(20, len(rects_sub) * 0.6)              # 33 rects = 20
    s_edges = min(15, (len(lines) + len(v_edges) / 30))  # explicit rules
    s_tables = min(15, len(tables) * 7)
    s_bold = min(15, bold_n * 0.75)
    s_size_div = min(15, size_diversity * 50)
    s_kv = min(20, kv_signals * 2)
    structural_score = round(
        s_rects + s_edges + s_tables + s_bold + s_size_div + s_kv, 1
    )

    if structural_score >= 40 or len(tables) > 0:
        verdict = "extract"
    elif structural_score >= 20:
        verdict = "low_priority"
    else:
        verdict = "skip"

    reasons = []
    if len(rects_sub) >= 10:
        reasons.append(f"{len(rects_sub)} substantial rects")
    if len(tables) > 0:
        reasons.append(f"{len(tables)} pdfplumber tables")
    if bold_n >= 5:
        reasons.append(f"{bold_n} bold spans")
    if size_uniq >= 3:
        reasons.append(f"{size_uniq} distinct font sizes (hierarchy)")
    if kv_signals >= 3:
        reasons.append(f"{kv_signals} KV-pattern signals")
    if not reasons:
        reasons.append(
            f"sparse: {len(rects_sub)} rects, "
            f"{len(spans_struct)} spans, {bold_n} bold"
        )

    return {
        "page": page_num,
        "page_size_pt": [page_w, page_h],
        "mediabox_offset_y": media_lly,
        "structural_score": structural_score,
        "verdict": verdict,
        "reasons": reasons,
        "signals": {
            "rects_total": len(rects_all),
            "rects_substantial": len(rects_sub),
            "lines": len(lines),
            "horizontal_edges": len(h_edges),
            "vertical_edges": len(v_edges),
            "images": len(images),
            "pdfplumber_tables": len(tables),
            "spans_total": len(spans),
            "spans_structural": len(spans_struct),
            "spans_bold": bold_n,
            "case_hist": dict(case_hist),
            "size_median": size_median,
            "size_diversity": round(size_diversity, 3),
            "kv_pattern_signals": kv_signals,
        },
        "score_breakdown": {
            "rects": round(s_rects, 1),
            "edges": round(s_edges, 1),
            "tables": round(s_tables, 1),
            "bold": round(s_bold, 1),
            "size_diversity": round(s_size_div, 1),
            "kv_signals": round(s_kv, 1),
        },
    }


def main() -> int:
    import pdfplumber  # type: ignore[import-not-found]

    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    with pdfplumber.open(str(pdf_path)) as pdf:
        n_pages = len(pdf.pages)

    print(f"[triage] {pdf_path.name} ({n_pages} pages)", file=sys.stderr)
    print(f"[triage] page  score  verdict        reasons", file=sys.stderr)
    print(f"[triage] ----  -----  -------------  -------", file=sys.stderr)

    pages = []
    for pn in range(1, n_pages + 1):
        r = triage_page(pdf_path, pn)
        pages.append(r)
        print(
            f"[triage]  {pn:2d}   {r['structural_score']:5.1f}  "
            f"{r['verdict']:13s}  {', '.join(r['reasons'])}",
            file=sys.stderr,
        )

    by_verdict = Counter(p["verdict"] for p in pages)
    extract_pages = [p["page"] for p in pages if p["verdict"] == "extract"]
    low_pri_pages = [p["page"] for p in pages if p["verdict"] == "low_priority"]
    skip_pages = [p["page"] for p in pages if p["verdict"] == "skip"]

    out = {
        "pdf": str(pdf_path),
        "n_pages": n_pages,
        "summary": {
            "verdicts": dict(by_verdict),
            "extract_pages": extract_pages,
            "low_priority_pages": low_pri_pages,
            "skip_pages": skip_pages,
        },
        "pages": pages,
    }

    out_path = (Path(args.out).resolve() if args.out
                else ROOT / ".planning" / "extraction" / "triage"
                / f"{pdf_path.stem}.triage.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    print(f"[triage]", file=sys.stderr)
    print(f"[triage] verdicts: {dict(by_verdict)}", file=sys.stderr)
    print(f"[triage] → extract:      {extract_pages}", file=sys.stderr)
    print(f"[triage] → low_priority: {low_pri_pages}", file=sys.stderr)
    print(f"[triage] → skip:         {skip_pages}", file=sys.stderr)
    print(f"[triage] file: {out_path}", file=sys.stderr)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
