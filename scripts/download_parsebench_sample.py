"""Download a small ParseBench sample for statistical key-value experiments.

Picks 5 PDFs from each of three ParseBench categories — `table`, `text`,
`layout` — and writes per-PDF ground-truth JSONL files alongside.

Output layout:
    data/parsebench/
        pdfs/<stem>.pdf
        ground_truth/<stem>.jsonl

Idempotent: skips PDFs and GT files already on disk.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "llamaindex/ParseBench"
REPO_TYPE = "dataset"

ROOT = Path(__file__).resolve().parent.parent / "data" / "parsebench"
PDFS_DIR = ROOT / "pdfs"
GT_DIR = ROOT / "ground_truth"

JSONLS = [
    "table.jsonl",
    "text_content.jsonl",
    "text_formatting.jsonl",
    "layout.jsonl",
    "chart.jsonl",
]

# 5 PDFs per category. Mix of easy and hard tags so the sample has a quality
# spread without being curated by hand.
CATEGORIES = {
    "table": 5,
    "text": 5,
    "layout": 5,
}

# PDFs proven incompatible with the digital-only pipeline. All 3 engines must
# return non-empty content; OCR/image inputs are out of scope for v0.7.0.
#  - scanned / handwritten → all 3 engines return 0 items (no OCR)
#  - layout/ category mixes 349 .jpg + 103 .png with PDFs — non-PDF entries
#    are filtered out by extension below, no need to list them here.
KNOWN_BAD = {
    "docs/text/text_dense__baoutou.pdf",            # scanned (Chinese text, no text layer)
    "docs/text/text_handwritting__address.pdf",     # handwritten
}


def load_all_annotations() -> list[dict]:
    """Download every JSONL once and return a flat list of annotation records."""
    records: list[dict] = []
    for jf in JSONLS:
        path = hf_hub_download(REPO_ID, jf, repo_type=REPO_TYPE)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
    return records


def group_by_pdf(records: list[dict]) -> dict[str, list[dict]]:
    by_pdf: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_pdf[rec["pdf"]].append(rec)
    return by_pdf


def pick_pdfs(by_pdf: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Choose N PDFs per top-level docs/<category>/ folder.

    Selection: PDFs sorted alphabetically (deterministic), prefer ones whose
    annotations include at least one `easy` tag in the first half and `hard`
    in the second so we cover both ends.
    """
    chosen: dict[str, list[str]] = {}
    for cat, n in CATEGORIES.items():
        prefix = f"docs/{cat}/"
        cat_pdfs = sorted(
            p for p in by_pdf
            if p.startswith(prefix)
            and p.lower().endswith(".pdf")
            and p not in KNOWN_BAD
        )

        def has_tag(pdf: str, tag: str) -> bool:
            return any(tag in (rec.get("tags") or []) for rec in by_pdf[pdf])

        easy = [p for p in cat_pdfs if has_tag(p, "easy")]
        hard = [p for p in cat_pdfs if has_tag(p, "hard") and p not in easy]

        half = n // 2
        picked = easy[:half] + hard[: n - half]
        # Fill from remaining if we still need more (small categories).
        if len(picked) < n:
            remaining = [p for p in cat_pdfs if p not in picked]
            picked += remaining[: n - len(picked)]
        chosen[cat] = picked[:n]
    return chosen


def stem_of(pdf_repo_path: str) -> str:
    """`docs/table/foo_page1.pdf` -> `table__foo_page1` (collision-safe)."""
    parts = pdf_repo_path.split("/")
    category = parts[-2] if len(parts) >= 2 else "unknown"
    name = Path(parts[-1]).stem
    return f"{category}__{name}"


def download_pdf(pdf_repo_path: str) -> Path:
    stem = stem_of(pdf_repo_path)
    target = PDFS_DIR / f"{stem}.pdf"
    if target.exists() and target.stat().st_size > 0:
        return target
    src = hf_hub_download(REPO_ID, pdf_repo_path, repo_type=REPO_TYPE)
    target.write_bytes(Path(src).read_bytes())
    return target


def write_ground_truth(pdf_repo_path: str, annotations: list[dict]) -> Path:
    stem = stem_of(pdf_repo_path)
    target = GT_DIR / f"{stem}.jsonl"
    if target.exists():
        return target
    with target.open("w", encoding="utf-8") as fh:
        for rec in annotations:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return target


def main() -> None:
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    GT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading all ParseBench annotations from {REPO_ID} ...")
    records = load_all_annotations()
    print(f"  {len(records)} annotation records loaded")

    by_pdf = group_by_pdf(records)
    print(f"  {len(by_pdf)} unique PDFs annotated")

    chosen = pick_pdfs(by_pdf)
    total = sum(len(v) for v in chosen.values())
    print(f"\nPicked {total} PDFs across {len(chosen)} categories:")
    for cat, pdfs in chosen.items():
        print(f"  {cat}: {len(pdfs)}")

    print("\nDownloading PDFs + writing ground truth ...")
    for cat, pdfs in chosen.items():
        for pdf in pdfs:
            pdf_path = download_pdf(pdf)
            gt_path = write_ground_truth(pdf, by_pdf[pdf])
            n_anns = len(by_pdf[pdf])
            print(
                f"  [{cat}] {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)"
                f"  -> {n_anns} annotations"
            )

    print(f"\nDone. PDFs in {PDFS_DIR}, ground truth in {GT_DIR}.")


if __name__ == "__main__":
    main()
