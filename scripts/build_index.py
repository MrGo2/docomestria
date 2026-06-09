"""Build data/parsebench/INDEX.md — one row per sample PDF.

Columns:
    file | category | size (KB) | GT records | docling | liteparse | pdfplumber

Engine columns show the item count from the saved JSON output, or `ERROR`
if the engine wrote a `.error.txt` instead.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "parsebench"
PDFS_DIR = ROOT / "pdfs"
GT_DIR = ROOT / "ground_truth"
OUT_DIR = ROOT / "outputs"
INDEX = ROOT / "INDEX.md"

ENGINES = ("docling", "liteparse", "pdfplumber")


def category_of(stem: str) -> str:
    return stem.split("__", 1)[0] if "__" in stem else "?"


def gt_count(stem: str) -> int:
    f = GT_DIR / f"{stem}.jsonl"
    if not f.exists():
        return 0
    return sum(1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip())


def engine_cell(engine: str, stem: str) -> str:
    ok = OUT_DIR / engine / f"{stem}.json"
    err = OUT_DIR / engine / f"{stem}.error.txt"
    if err.exists():
        return "ERROR"
    if not ok.exists():
        return "—"
    try:
        payload = json.loads(ok.read_text(encoding="utf-8"))
        count = payload.get("count")
        elapsed = payload.get("elapsed_seconds")
        if count is None:
            return "?"
        return f"{count} ({elapsed:.2f}s)" if elapsed is not None else str(count)
    except Exception:
        return "PARSE-ERR"


def main() -> None:
    pdfs = sorted(PDFS_DIR.glob("*.pdf"))
    rows: list[dict] = []
    for pdf in pdfs:
        stem = pdf.stem
        rows.append(
            {
                "file": pdf.name,
                "category": category_of(stem),
                "size_kb": pdf.stat().st_size // 1024,
                "gt": gt_count(stem),
                "docling": engine_cell("docling", stem),
                "liteparse": engine_cell("liteparse", stem),
                "pdfplumber": engine_cell("pdfplumber", stem),
            }
        )

    header = (
        "| File | Category | Size (KB) | GT records | Docling | LiteParse | pdfplumber |\n"
        "|---|---|---:|---:|---|---|---|\n"
    )
    body_lines = [
        f"| `{r['file']}` | {r['category']} | {r['size_kb']} | {r['gt']} | "
        f"{r['docling']} | {r['liteparse']} | {r['pdfplumber']} |"
        for r in rows
    ]

    summary = {
        "total_pdfs": len(rows),
        "total_gt": sum(r["gt"] for r in rows),
        "errors": sum(
            1 for r in rows for e in ENGINES if r[e] == "ERROR"
        ),
        "empty": sum(
            1 for r in rows for e in ENGINES if r[e] == "0" or r[e].startswith("0 (")
        ),
    }

    content = [
        "# ParseBench sample — index",
        "",
        f"- Total PDFs: **{summary['total_pdfs']}**",
        f"- Total ground-truth records across all PDFs: **{summary['total_gt']}**",
        f"- Engine errors: **{summary['errors']}**",
        f"- Empty engine outputs (0 items): **{summary['empty']}**",
        "",
        "Engine cells show `<item count> (<elapsed s>)` from the saved JSON,",
        "`ERROR` if the engine wrote `<stem>.error.txt`, or `—` if no output was produced.",
        "",
        header.rstrip() + "\n" + "\n".join(body_lines),
        "",
    ]

    INDEX.write_text("\n".join(content), encoding="utf-8")
    print(f"Wrote {INDEX}")
    print(f"  total PDFs: {summary['total_pdfs']}")
    print(f"  total GT records: {summary['total_gt']}")
    print(f"  engine errors: {summary['errors']}")
    print(f"  empty outputs: {summary['empty']}")


if __name__ == "__main__":
    main()
