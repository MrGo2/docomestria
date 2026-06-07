#!/usr/bin/env python3
"""golden_scaffold — generate a draft spec.py from atoms + PDF via the
golden-scaffolder agent (Opus).

Phase 4 of the automation plan. Replaces manual spec writing for new pages.

Workflow:
    1. Resolves atoms.json path from PDF stem + page (same convention as
       golden_review.py and golden_pipeline.py).
    2. Builds the agent prompt with explicit inputs (atoms path, PDF path,
       output spec path).
    3. Invokes `claude --agent golden-scaffolder` as subprocess.
    4. After the agent writes the spec, validates it:
        - Parses with `ast.parse`
        - Has `PDF`, `PAGE`, `META`, `STRUCTURE` module-level names
        - Smoke-runs `build_golden.py` on it (must exit 0)
    5. Prints summary: spec path, KV count, % populated.

CLI:
    python3 scripts/golden_scaffold.py \\
        --pdf "/path/to/contract.pdf" --page 2 \\
        [--out scripts/specs/<stem>_p<NN>.py] \\
        [--prompt-only]   # print prompt without invoking (debugging)

Default output path: scripts/specs/<sanitized_pdf_stem>_p<NN>.py
Pure stdlib.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path  # noqa: I001

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
ATOMS_DIR = ROOT / ".planning" / "extraction" / "atoms"
SPECS_DIR = SCRIPTS_DIR / "specs"


# ----- path resolution -------------------------------------------------------

def _sanitize_stem(stem: str) -> str:
    """Convert 'CONTRATO PRESTAMO COMERCIO 2' → 'contrato_prestamo_comercio_2'."""
    s = stem.lower()
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _resolve_paths(pdf_arg: str, page: int, out_arg: str | None
                    ) -> tuple[Path, Path, Path]:
    pdf = Path(pdf_arg)
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")
    atoms = ATOMS_DIR / f"{pdf.stem}-p{page:02d}.atoms.json"
    if not atoms.exists():
        raise SystemExit(
            f"Atoms not found: {atoms}\n"
            f"  Run: PYTHONPATH=src python3 scripts/extract_atoms.py "
            f"\"{pdf}\" --page {page}"
        )
    if out_arg:
        out = Path(out_arg)
    else:
        SPECS_DIR.mkdir(parents=True, exist_ok=True)
        out = SPECS_DIR / f"{_sanitize_stem(pdf.stem)}_p{page:02d}.py"
    return pdf, atoms, out


# ----- prompt ----------------------------------------------------------------

def build_agent_prompt(pdf: Path, atoms: Path, page: int, out: Path) -> str:
    """Compose the prompt for the golden-scaffolder agent."""
    return f"""Scaffold a draft golden spec.py for the page below, per your instructions.

INPUTS
- pdf:     {pdf}
- page:    {page}
- atoms:   {atoms}

OUTPUT
- spec:    {out}

Steps:
1. Inspect atoms.spans sorted by y to learn the page's visual structure
   (use the python -c snippet in your system prompt; do NOT cat the whole
   atoms file).
2. Read the PDF page {page} with Read (pages={page}) for visual layout.
3. Identify the structural skeleton: sections, repeated blocks, tables,
   prose, footer noise.
4. Match against pattern library helpers (_patterns.py) — prefer helpers
   when the layout fits canonically.
5. Write the spec to {out} as a single self-contained Python module with
   PDF/PAGE/META/STRUCTURE constants.
6. Smoke-test by running:
     cd {ROOT} && PYTHONPATH=src python3 scripts/build_golden.py {out}
   The build must exit 0. If it fails, fix the spec and retry.
7. Print the one-line summary as your final stdout line.

Quality bar: 80%+ structural coverage, 0 hallucinated values. Better to
omit an ambiguous field than to invent one. The reviewer/patcher loop
downstream will polish.
"""


# ----- spec validation -------------------------------------------------------

REQUIRED_NAMES = {"PDF", "PAGE", "META", "STRUCTURE"}


def validate_spec_ast(spec_path: Path) -> dict:
    """Parse the spec with `ast.parse` and confirm required names exist.

    Returns a dict with module-level info. Raises SystemExit on failure.
    """
    if not spec_path.exists():
        raise SystemExit(f"Agent did not write spec file: {spec_path}")
    src = spec_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src, filename=str(spec_path))
    except SyntaxError as e:
        raise SystemExit(f"Spec has syntax error: {e}") from e
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    missing = REQUIRED_NAMES - names
    if missing:
        raise SystemExit(
            f"Spec missing required module-level names: {sorted(missing)}"
        )
    return {"names": sorted(names), "source_bytes": len(src.encode("utf-8"))}


def smoke_build(spec_path: Path) -> tuple[bool, str, dict]:
    """Run build_golden.py on the spec. Returns (ok, log, golden_doc_or_empty)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [sys.executable, str(SCRIPTS_DIR / "build_golden.py"), str(spec_path)]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True,
                         cwd=str(ROOT))
    log = (res.stdout or "") + "\n--- stderr ---\n" + (res.stderr or "")
    if res.returncode != 0:
        return False, log, {}
    # Try to load the produced golden for summary stats.
    # build_golden.py writes to .planning/extraction/golden/<stem>-p<NN>.json
    # We parse the PDF/PAGE out of the spec to know where.
    try:
        spec_src = spec_path.read_text()
        # Extract PDF + PAGE via ast
        tree = ast.parse(spec_src)
        pdf_val, page_val = None, None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if not isinstance(t, ast.Name):
                        continue
                    if t.id == "PDF" and isinstance(node.value, ast.Constant):
                        pdf_val = node.value.value
                    elif t.id == "PAGE" and isinstance(node.value, ast.Constant):
                        page_val = node.value.value
        if pdf_val and page_val:
            pdf_stem = Path(pdf_val).stem
            golden_path = (
                ROOT / ".planning" / "extraction" / "golden"
                / f"{pdf_stem}-p{int(page_val):02d}.json"
            )
            if golden_path.exists():
                return True, log, json.loads(golden_path.read_text())
    except Exception:
        pass
    return True, log, {}


# ----- agent invocation ------------------------------------------------------

def run_scaffolder_agent(prompt: str, spec_out: Path, timeout: int = 900
                          ) -> tuple[bool, str]:
    """Invoke the golden-scaffolder agent via `claude --agent`.

    Returns (ok, log). ok=True means the subprocess exited 0 AND the spec
    file exists. The agent itself writes the spec (per its system prompt).
    """
    if shutil.which("claude") is None:
        return False, "claude CLI not found on PATH"
    cmd = [
        "claude",
        "--agent", "golden-scaffolder",
        "--print",
        "--output-format", "text",
        "--add-dir", str(ROOT),
        prompt,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True,
                             cwd=str(ROOT), timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"claude agent timed out after {timeout}s"
    log = (res.stdout or "") + "\n--- stderr ---\n" + (res.stderr or "")
    if res.returncode != 0:
        return False, f"claude exited {res.returncode}\n{log}"
    if not spec_out.exists():
        return False, f"spec file was not written: {spec_out}\n{log}"
    return True, log


# ----- summary ---------------------------------------------------------------

def print_summary(spec_path: Path, golden: dict) -> None:
    print()
    print("=== Scaffold summary ===")
    print(f"  Spec:          {spec_path}")
    kvs = golden.get("kv_pairs", []) if golden else []
    total = len(kvs)
    populated = sum(1 for kv in kvs if (kv.get("value") or "").strip())
    breakdown = golden.get("diagnostics", {}).get("kv_pair_breakdown", {})
    pct = (100.0 * populated / total) if total else 0.0
    print(f"  KV pairs:      {total} ({populated} populated, {total - populated} empty) — {pct:.0f}% populated")
    if breakdown:
        bd = ", ".join(f"{v} {k.replace('_eng', '-eng')}"
                       for k, v in breakdown.items() if v)
        print(f"  Breakdown:     {bd}")
    structure = golden.get("structure", []) if golden else []
    print(f"  Top nodes:     {len(structure)}")
    noise = golden.get("noise", []) if golden else []
    print(f"  Noise nodes:   {len(noise)}")


# ----- CLI -------------------------------------------------------------------

def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdf", required=True, help="Path to source PDF")
    ap.add_argument("--page", type=int, required=True, help="Page number")
    ap.add_argument("--out", help="Output spec.py path "
                                   "(default: scripts/specs/<stem>_p<NN>.py)")
    ap.add_argument("--prompt-only", action="store_true",
                    help="Print the agent prompt and exit (for debugging)")
    args = ap.parse_args(argv)

    pdf, atoms, out = _resolve_paths(args.pdf, args.page, args.out)

    prompt = build_agent_prompt(pdf, atoms, args.page, out)

    if args.prompt_only:
        print(prompt)
        return 0

    if out.exists():
        print(f"⚠ Spec already exists at {out} — agent will overwrite.")
        # Remove stale spec so we know the agent wrote.
        out.unlink()

    ok, agent_log = run_scaffolder_agent(prompt, out)
    if not ok:
        print("✗ Scaffolder agent failed.\n", file=sys.stderr)
        print(agent_log, file=sys.stderr)
        return 1

    # AST validation
    try:
        validate_spec_ast(out)
    except SystemExit as e:
        print(f"✗ Spec AST validation failed: {e}", file=sys.stderr)
        print(f"  Agent log tail:\n{agent_log[-1000:]}", file=sys.stderr)
        return 2

    # Smoke build
    ok, build_log, golden = smoke_build(out)
    if not ok:
        print(f"✗ Smoke build failed:\n{build_log}", file=sys.stderr)
        return 3

    print(f"\n✓ Scaffold OK: {out}")
    print_summary(out, golden)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
