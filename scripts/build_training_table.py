#!/usr/bin/env python3
"""Build the role-classification training table from all golden page-files.

Usage:  python3 scripts/build_training_table.py
Output: .planning/extraction/training/role_table.csv  (+ printed histogram)
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from docomestria.golden.training_table import FIELDS, build_page_rows, write_csv  # noqa: E402

GOLDEN_DIR = ROOT / ".planning" / "extraction" / "golden"
ATOMS_DIR = ROOT / ".planning" / "extraction" / "atoms"
OUT_DIR = ROOT / ".planning" / "extraction" / "training"
OUT = OUT_DIR / "role_table.csv"
MIN_EXPECTED_PAGES = 50  # corpus is 66 page-files; fail loud if the glob is near-empty


def _has_structure(golden: dict) -> bool:
    """True for structure-format goldens (a non-empty `structure` tree).

    Legacy goldens carry only top-level `sections`/`kv_pairs` (no per-engine
    evidence) and must be skipped — walking them would emit nothing and turn
    every atom on the page into noise.
    """
    return isinstance(golden.get("structure"), list) and len(golden["structure"]) > 0


def main() -> int:
    golden_files = sorted(GOLDEN_DIR.glob("*.json"))
    if len(golden_files) < MIN_EXPECTED_PAGES:
        print(f"ERROR: only {len(golden_files)} goldens under {GOLDEN_DIR} "
              f"(expected >= {MIN_EXPECTED_PAGES}). Aborting.", file=sys.stderr)
        return 1

    all_rows = []
    totals = {"unresolved_keys": 0, "noise_atoms": 0, "pages": 0}
    legacy_skipped: list[str] = []
    missing_atoms: list[str] = []
    for gp in golden_files:
        golden = json.loads(gp.read_text(encoding="utf-8"))
        if not _has_structure(golden):
            legacy_skipped.append(gp.name)
            continue
        atoms_path = ATOMS_DIR / f"{gp.stem}.atoms.json"
        if not atoms_path.exists():
            missing_atoms.append(gp.name)   # a STRUCTURE golden with no atoms = error
            continue
        atoms = json.loads(atoms_path.read_text(encoding="utf-8"))
        rows, diag = build_page_rows(golden, atoms)
        all_rows.extend(rows)
        totals["unresolved_keys"] += diag["unresolved_keys"]
        totals["noise_atoms"] += diag["noise_atoms"]
        totals["pages"] += 1

    # deterministic global order
    all_rows.sort(key=lambda r: (
        str(r["pdf"]), int(r["page"]) if str(r["page"]).isdigit() else 0,
        r["node_path"], str(r["row_idx"]), str(r["col_id"]),
        r["y"] if r["y"] != "" else 9.9, r["x"] if r["x"] != "" else 9.9,
    ))

    # A structure-format golden with no atoms is a hard error — abort before
    # writing so we never emit a partial table.
    if missing_atoms:
        print(f"ERROR: {len(missing_atoms)} structure goldens have no atoms file:",
              file=sys.stderr)
        for n in missing_atoms:
            print(f"  - {n}", file=sys.stderr)
        return 1
    if totals["pages"] == 0:
        print("ERROR: no structure-format goldens processed; nothing to write.",
              file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(all_rows, OUT)

    hist = Counter(r["role"] for r in all_rows)
    print(f"\nWrote {len(all_rows)} rows from {totals['pages']} pages -> {OUT}")
    print("Class histogram:")
    for role in ["section_header", "key", "value", "table_header",
                 "prose", "signature", "noise"]:
        print(f"  {role:<16} {hist.get(role, 0)}")
    other = set(hist) - {"section_header", "key", "value", "table_header",
                         "prose", "signature", "noise"}
    for role in sorted(other):
        print(f"  {role:<16} {hist[role]}  (UNEXPECTED)")
    print(f"\nunresolved_keys={totals['unresolved_keys']}  "
          f"noise_atoms={totals['noise_atoms']}")
    if legacy_skipped:
        print(f"\nSKIPPED {len(legacy_skipped)} legacy goldens (no `structure` tree — "
              f"re-scaffold to include them):")
        for n in legacy_skipped:
            print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
