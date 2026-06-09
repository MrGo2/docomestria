#!/usr/bin/env python3
"""Dump text spans from a page's atoms.json in human-readable form.

Replaces the ad-hoc Python heredoc used during spec-writing. Outputs
an aligned table that maps directly to y_hint values for spec entries.

Usage:
    python3 scripts/dump_spans.py PDF_NAME PAGE [--bands]
    python3 scripts/dump_spans.py "CONTRATO IKEA.pdf" 2
    python3 scripts/dump_spans.py "CONTRATO IKEA.pdf" 2 --bands

By default expects atoms in .planning/extraction/atoms/<stem>-p<NN>.atoms.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_atoms(pdf_name: str, page: int) -> dict:
    stem = Path(pdf_name).stem  # works whether you pass full path or just name
    atoms_path = (Path.cwd() / ".planning" / "extraction" / "atoms"
                  / f"{stem}-p{page:02d}.atoms.json")
    if not atoms_path.exists():
        raise SystemExit(f"Atoms file not found: {atoms_path}\n"
                         f"Run: PYTHONPATH=src python3 scripts/extract_atoms.py "
                         f"'{pdf_name}' --page {page}")
    return json.loads(atoms_path.read_text())


def _print_flat(spans: list[dict]) -> None:
    spans = sorted([s for s in spans if (s.get("text") or "").strip()],
                   key=lambda s: (s["bbox"]["y"], s["bbox"]["x"]))
    print(f"{'y':>6} {'x':>6} {'sz':>4} {'B':>1} | text")
    print("-" * 90)
    for s in spans:
        t = (s.get("text") or "").strip()
        y = s["bbox"]["y"]
        x = s["bbox"]["x"]
        sz = s.get("font_size", 0)
        b = "B" if s.get("is_bold") else "."
        print(f"{y:>6.1f} {x:>6.1f} {sz:>4.1f} {b:>1} | {t[:120]}")


def _print_bands(spans: list[dict], band_tol: float = 6.0) -> None:
    """Group spans into y-bands and print bandwise."""
    spans = sorted([s for s in spans if (s.get("text") or "").strip()],
                   key=lambda s: (s["bbox"]["y"], s["bbox"]["x"]))
    bands = []
    for s in spans:
        y = s["bbox"]["y"]
        if bands and abs(y - bands[-1]["y_mean"]) < band_tol:
            bands[-1]["spans"].append(s)
            n = len(bands[-1]["spans"])
            bands[-1]["y_mean"] = (bands[-1]["y_mean"] * (n - 1) + y) / n
        else:
            bands.append({"y_mean": y, "spans": [s]})
    for band in bands:
        y = band["y_mean"]
        parts = []
        for s in sorted(band["spans"], key=lambda s: s["bbox"]["x"]):
            t = (s.get("text") or "").strip()
            x = s["bbox"]["x"]
            sz = s.get("font_size", 0)
            b = "B" if s.get("is_bold") else "."
            parts.append(f"[x={x:.0f} sz={sz:.0f} {b}] {t}")
        line = "   ".join(parts)
        print(f"y={y:6.1f} | {line[:200]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf", help="PDF filename or path (stem used to find atoms)")
    ap.add_argument("page", type=int, help="1-based page number")
    ap.add_argument("--bands", action="store_true",
                    help="group spans by y-band (one line per visual row)")
    args = ap.parse_args()

    atoms = _load_atoms(args.pdf, args.page)
    spans = atoms["atoms"]["spans"]
    print(f"# {args.pdf} page {args.page} — {len(spans)} spans")
    print()
    if args.bands:
        _print_bands(spans)
    else:
        _print_flat(spans)


if __name__ == "__main__":
    main()
