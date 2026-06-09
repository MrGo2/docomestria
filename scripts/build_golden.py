"""Generic golden builder CLI.

    PYTHONPATH=src python3 scripts/build_golden.py SPEC_MODULE [--out PATH]

SPEC_MODULE is a dotted path (e.g. `specs.bbva_0539_p01`) or a file path
to a Python module exporting `PDF`, `PAGE`, `STRUCTURE`, and `META`.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from docomestria.golden import GoldenBuilder

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / ".planning" / "extraction" / "golden"
DRAFT_DIR = ROOT / ".planning" / "extraction" / "drafts"


def _load_spec(arg: str):
    p = Path(arg)
    if p.exists():
        spec = importlib.util.spec_from_file_location("spec_mod", str(p))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    # Try as dotted module under scripts/
    sys.path.insert(0, str(ROOT / "scripts"))
    return importlib.import_module(arg)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="Path to spec module or dotted name (e.g. specs.bbva_0539_p01)")
    ap.add_argument("--out", default=None, help="Output JSON path (default: golden/<stem>.json)")
    args = ap.parse_args(argv)

    mod = _load_spec(args.spec)
    pdf = Path(mod.PDF)
    page = int(mod.PAGE)
    structure = mod.STRUCTURE
    meta = getattr(mod, "META", {})

    out_path = (Path(args.out) if args.out
                else GOLDEN_DIR / f"{pdf.stem}-p{page:02d}.json")

    # Resolve atoms_path explicitly from ROOT so the CLI works from any cwd.
    atoms_path = ROOT / ".planning" / "extraction" / "atoms" / f"{pdf.stem}-p{page:02d}.atoms.json"

    print(f"Loading {pdf.name} page {page}...")
    builder = GoldenBuilder(pdf, page_num=page, atoms_path=atoms_path)
    print(f"  page: {builder.eng.width:.0f}x{builder.eng.height:.0f} pt | "
          f"chars={len(builder.eng.chars)} rows={len(builder.eng.rows)} "
          f"spans={len(builder.eng.spans)} blocks={len(builder.eng.blocks)} "
          f"rects={len(builder.eng.rects)}")

    golden = builder.build(structure, meta=meta)

    # Backup existing golden as draft (if present + different)
    if out_path.exists():
        DRAFT_DIR.mkdir(parents=True, exist_ok=True)
        (DRAFT_DIR / out_path.name).write_text(out_path.read_text(encoding="utf-8"),
                                                encoding="utf-8")

    builder.save(golden, out_path)
    print(f"\n✓ golden: {out_path}")
    print(f"  · structure nodes: {len(golden['structure'])}")
    print(f"  · kv_pairs: {len(golden['kv_pairs'])}")
    print(f"  · kv_pair_breakdown: {golden['diagnostics']['kv_pair_breakdown']}")


if __name__ == "__main__":
    main(sys.argv[1:])
