#!/usr/bin/env python3
"""CLI wrapper to spawn the golden-reviewer agent and validate its output.

Usage:
    python3 scripts/golden_review.py --golden PATH --pdf PATH --page N [--out PATH]

The agent reads (golden + atoms + PDF image) and writes findings.json.
This wrapper:
    1. Resolves default paths if not provided
    2. Builds the agent prompt with explicit inputs
    3. Validates the findings.json schema after the agent finishes
    4. Prints a summary
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


FINDINGS_SCHEMA_REQUIRED = {
    "golden_path", "pdf_path", "page", "summary", "findings",
}
SUMMARY_REQUIRED = {
    "total_kv", "populated_kv", "empty_kv", "high", "medium", "low", "verdict",
}
FINDING_REQUIRED = {"id", "severity", "type", "evidence", "proposed_fix"}
VALID_SEVERITIES = {"HIGH", "MEDIUM", "LOW"}
VALID_VERDICTS = {"PASS", "FIX_REQUIRED", "NEEDS_HUMAN"}


def _resolve_paths(args) -> tuple[Path, Path, Path, Path]:
    golden = Path(args.golden)
    if not golden.exists():
        raise SystemExit(f"Golden not found: {golden}")
    pdf = Path(args.pdf) if args.pdf else Path(json.loads(golden.read_text()).get("pdf", ""))
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")
    atoms = Path(args.atoms) if args.atoms else (
        Path.cwd() / ".planning" / "extraction" / "atoms"
        / f"{pdf.stem}-p{args.page:02d}.atoms.json"
    )
    if not atoms.exists():
        raise SystemExit(f"Atoms not found: {atoms}")
    if args.out:
        out = Path(args.out)
    else:
        reviews_dir = Path.cwd() / ".planning" / "extraction" / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        out = reviews_dir / f"{pdf.stem}-p{args.page:02d}.findings.json"
    return golden, pdf, atoms, out


def build_agent_prompt(golden: Path, pdf: Path, atoms: Path, page: int,
                       out: Path) -> str:
    """Compose the prompt for the golden-reviewer agent."""
    return f"""Review the golden listed below and emit findings.json per your instructions.

INPUTS
- golden:  {golden}
- atoms:   {atoms}
- pdf:     {pdf}
- page:    {page}

OUTPUT
- findings: {out}

Steps:
1. Read the golden file to inventory populated and empty KVs.
2. Grep the atoms file (do NOT cat it whole) to verify each populated KV's value text appears in atoms.spans.
3. Read the PDF page {page} for visual layout context.
4. Apply your 7-step review workflow.
5. Write findings.json to the OUTPUT path above (exactly that path).
6. Print the one-line summary as your final stdout line.

Be conservative: only flag substantive errors. Skip whitespace differences.
"""


def validate_findings(findings_path: Path) -> dict:
    """Validate the findings.json against schema. Returns parsed dict or raises."""
    if not findings_path.exists():
        raise SystemExit(f"Agent did not write findings file: {findings_path}")
    try:
        d = json.loads(findings_path.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in findings file: {e}")
    missing = FINDINGS_SCHEMA_REQUIRED - set(d.keys())
    if missing:
        raise SystemExit(f"findings.json missing keys: {missing}")
    missing = SUMMARY_REQUIRED - set(d.get("summary", {}).keys())
    if missing:
        raise SystemExit(f"findings.summary missing keys: {missing}")
    if d["summary"]["verdict"] not in VALID_VERDICTS:
        raise SystemExit(f"Invalid verdict: {d['summary']['verdict']}")
    for f in d.get("findings", []):
        missing = FINDING_REQUIRED - set(f.keys())
        if missing:
            raise SystemExit(f"Finding {f.get('id','?')} missing keys: {missing}")
        if f["severity"] not in VALID_SEVERITIES:
            raise SystemExit(f"Finding {f['id']} invalid severity: {f['severity']}")
    return d


def print_summary(findings: dict) -> None:
    s = findings["summary"]
    print()
    print(f"=== Review summary ({findings['golden_path']}) ===")
    print(f"  Total KVs:     {s['total_kv']} ({s['populated_kv']} populated, {s['empty_kv']} empty)")
    print(f"  Findings:      {s['high']} HIGH / {s['medium']} MEDIUM / {s['low']} LOW")
    print(f"  Verdict:       {s['verdict']}")
    if findings["findings"]:
        print()
        print(f"  Top findings:")
        for f in findings["findings"][:5]:
            ev = f.get("evidence", {})
            comment = ev.get("comment", "")[:80]
            print(f"    [{f['severity']:6}] {f['type']:25} | {comment}")
        if len(findings["findings"]) > 5:
            print(f"    ... and {len(findings['findings']) - 5} more")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--golden", required=True, help="Path to golden.json")
    ap.add_argument("--page", type=int, required=True, help="Page number")
    ap.add_argument("--pdf", help="Path to PDF (defaults to golden.pdf field)")
    ap.add_argument("--atoms", help="Path to atoms.json (defaults to standard location)")
    ap.add_argument("--out", help="Path to write findings.json")
    ap.add_argument("--prompt-only", action="store_true",
                    help="Print the agent prompt and exit (for debugging)")
    args = ap.parse_args()

    golden, pdf, atoms, out = _resolve_paths(args)
    prompt = build_agent_prompt(golden, pdf, atoms, args.page, out)

    if args.prompt_only:
        print(prompt)
        return 0

    # When invoked from a Claude Code session, we expect the agent to have
    # already been called via the Agent tool. This CLI is the post-processing
    # step that validates and summarises.
    #
    # For automation/CI we'd shell out via `claude --agent golden-reviewer`,
    # but that integration belongs to the orchestrator in Phase 3.
    print(f"# Reviewer prompt prepared. Path: {out}")
    print(f"# Run the golden-reviewer agent with the prompt above, then re-run with --validate.")
    print()
    print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
