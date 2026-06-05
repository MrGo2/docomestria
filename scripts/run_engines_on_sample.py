"""Run Docling, LiteParse and pdfplumber on each ParseBench sample PDF.

Serializes the three engines' raw outputs as JSON under
`data/parsebench/outputs/{engine}/<stem>.json`. Idempotent: skips PDFs whose
output file already exists. Per-PDF errors are caught and logged but do not
stop the run.
"""

from __future__ import annotations

import dataclasses
import json
import time
import traceback
from pathlib import Path
from typing import Any, Callable

from docomestria.engines import (
    extract_docling_blocks,
    extract_lite_items,
    extract_visual_rects,
)

ROOT = Path(__file__).resolve().parent.parent / "data" / "parsebench"
PDFS_DIR = ROOT / "pdfs"
OUT_DIR = ROOT / "outputs"

ENGINES: dict[str, Callable[[str], Any]] = {
    "liteparse": extract_lite_items,
    "pdfplumber": extract_visual_rects,
    "docling": extract_docling_blocks,
}


def to_jsonable(obj: Any) -> Any:
    """Recursively convert frozen dataclasses / tuples to plain JSON types."""
    if dataclasses.is_dataclass(obj):
        return {k: to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj


def run_one(engine: str, fn: Callable[[str], Any], pdf: Path) -> dict[str, Any]:
    target = OUT_DIR / engine / f"{pdf.stem}.json"
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        return {"status": "skipped", "path": target}

    t0 = time.perf_counter()
    try:
        items = fn(str(pdf))
        elapsed = time.perf_counter() - t0
        payload = {
            "pdf": pdf.name,
            "engine": engine,
            "elapsed_seconds": round(elapsed, 3),
            "count": len(items) if hasattr(items, "__len__") else None,
            "items": to_jsonable(items),
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return {"status": "ok", "path": target, "elapsed": elapsed, "count": payload["count"]}
    except Exception as exc:  # noqa: BLE001 — surface all engine failures uniformly
        elapsed = time.perf_counter() - t0
        err_path = target.with_suffix(".error.txt")
        err_path.write_text(
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
        )
        return {"status": "error", "path": err_path, "elapsed": elapsed, "error": str(exc)}


def main() -> None:
    pdfs = sorted(PDFS_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {PDFS_DIR}. Run download_parsebench_sample.py first.")

    print(f"Found {len(pdfs)} PDFs in {PDFS_DIR}")
    print(f"Running engines: {', '.join(ENGINES)}\n")

    for pdf in pdfs:
        print(f"=== {pdf.name} ({pdf.stat().st_size // 1024} KB) ===")
        for engine, fn in ENGINES.items():
            res = run_one(engine, fn, pdf)
            status = res["status"]
            if status == "ok":
                print(
                    f"  {engine:<10} ok   ({res['elapsed']:.2f}s, {res['count']} items)"
                )
            elif status == "skipped":
                print(f"  {engine:<10} skip (already exists)")
            else:
                print(f"  {engine:<10} ERROR {res['error']}")
        print()

    print(f"Outputs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
