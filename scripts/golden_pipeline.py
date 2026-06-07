#!/usr/bin/env python3
"""golden_pipeline — orchestrates build → review → patch loop for one spec.

Phase 3 of the automation plan. Runs the existing pieces in sequence:

    spec.py (must exist) → build_golden → golden.json
                              ↓
                            review (golden-reviewer agent via Claude CLI)
                              ↓
                            findings.json
                              ↓
                       verdict == PASS / NEEDS_HUMAN → stop
                       verdict == FIX_REQUIRED       → patch spec → loop

Phase 4 (scaffolder) will add `--scaffold` mode. For now an existing spec.py
is required.

CLI:
    python3 scripts/golden_pipeline.py \\
        --spec scripts/specs/ikea_p02.py \\
        --pdf "/path/to/CONTRATO IKEA.pdf" --page 2 \\
        [--out-golden .planning/extraction/golden/foo-p02.json] \\
        [--max-iter 3] \\
        [--no-loop]               # just build+review once, no patch
        [--manual-review]         # print prompt, expect user to run the agent
        [--resume PATH]           # resume from an iteration log

Pure stdlib. Drives build_golden.py and spec_patcher.py as subprocesses and
spawns the golden-reviewer agent via `claude --agent`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Reuse the prompt builder + schema validator from the review wrapper.
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import golden_review  # noqa: E402  — sibling module
import golden_scaffold  # noqa: E402  — sibling module (Phase 4)

ROOT = SCRIPTS_DIR.parent
GOLDEN_DIR = ROOT / ".planning" / "extraction" / "golden"
ATOMS_DIR = ROOT / ".planning" / "extraction" / "atoms"
REVIEWS_DIR = ROOT / ".planning" / "extraction" / "reviews"
ITERATIONS_DIR = ROOT / ".planning" / "extraction" / "iterations"


# ----- helpers ---------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return "sha256:" + h.hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _findings_signature(findings: list[dict]) -> list[tuple]:
    """Comparable signature of findings for stuck detection.

    Compares on (type, severity, target) — ignoring evidence text + ids so two
    different runs with same root causes match.
    """
    sig = []
    for f in findings:
        fix = f.get("proposed_fix") or {}
        sig.append((f.get("type"), f.get("severity"),
                    fix.get("op"), fix.get("target")))
    sig.sort()
    return sig


def _format_breakdown(bd: dict) -> str:
    parts = []
    for k in ("3_eng", "2_eng", "1_eng", "0_eng", "empty"):
        v = bd.get(k, 0)
        if v:
            parts.append(f"{v} {k.replace('_eng', '-eng')}")
    return ", ".join(parts) or "0"


# ----- subprocess wrappers ---------------------------------------------------

def run_build(spec_path: Path, out_golden: Path) -> tuple[bool, dict, str]:
    """Run build_golden.py. Returns (ok, breakdown, stdout)."""
    env = {"PYTHONPATH": str(ROOT / "src")}
    # Merge with current env so PATH etc. survive.
    import os
    full_env = dict(os.environ)
    full_env.update(env)
    cmd = [sys.executable, str(SCRIPTS_DIR / "build_golden.py"),
           str(spec_path), "--out", str(out_golden)]
    res = subprocess.run(cmd, env=full_env, capture_output=True, text=True,
                         cwd=str(ROOT))
    if res.returncode != 0:
        return False, {}, (res.stdout or "") + "\n" + (res.stderr or "")
    breakdown = {}
    if out_golden.exists():
        try:
            golden = json.loads(out_golden.read_text())
            breakdown = golden.get("diagnostics", {}).get("kv_pair_breakdown", {})
        except Exception:
            pass
    return True, breakdown, res.stdout


def run_patcher(spec_path: Path, findings_path: Path) -> tuple[bool, int, int, str]:
    """Run spec_patcher.py in-place. Returns (ok, applied, skipped, stdout)."""
    cmd = [sys.executable, str(SCRIPTS_DIR / "spec_patcher.py"),
           "--spec", str(spec_path), "--findings", str(findings_path),
           "--out", str(spec_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    out = (res.stdout or "") + (res.stderr or "")
    applied = 0
    skipped = 0
    for line in out.splitlines():
        if line.startswith("✓ Applied"):
            try:
                applied = int(line.split()[2])
            except (IndexError, ValueError):
                pass
        elif line.startswith("⚠ Skipped"):
            try:
                skipped = int(line.split()[2])
            except (IndexError, ValueError):
                pass
    return res.returncode == 0, applied, skipped, out


def run_reviewer_agent(prompt: str, findings_out: Path, timeout: int = 600
                       ) -> tuple[bool, str]:
    """Invoke the golden-reviewer agent via `claude --agent`.

    Returns (ok, log). ok=True means the subprocess exited 0 AND the findings
    file exists. The agent itself writes the findings file (per its system
    prompt).
    """
    if shutil.which("claude") is None:
        return False, "claude CLI not found on PATH"
    cmd = [
        "claude",
        "--agent", "golden-reviewer",
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
    if not findings_out.exists():
        return False, f"findings file was not written: {findings_out}\n{log}"
    return True, log


# ----- iteration log ---------------------------------------------------------

def _log_path_for(pdf: Path, page: int) -> Path:
    ITERATIONS_DIR.mkdir(parents=True, exist_ok=True)
    return ITERATIONS_DIR / f"{pdf.stem}-p{page:02d}.iterations.json"


def _save_log(log_path: Path, log: dict) -> None:
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))


def _load_log(log_path: Path) -> dict:
    return json.loads(log_path.read_text())


# ----- core loop -------------------------------------------------------------

def run_pipeline(spec_path: Path, pdf: Path, page: int, out_golden: Path,
                 max_iter: int, no_loop: bool, manual_review: bool,
                 resume_log: dict | None) -> int:
    """Returns process exit code."""
    if not spec_path.exists():
        print(f"ERROR: spec not found: {spec_path}", file=sys.stderr)
        return 1
    if not pdf.exists():
        print(f"ERROR: PDF not found: {pdf}", file=sys.stderr)
        return 1

    atoms_path = ATOMS_DIR / f"{pdf.stem}-p{page:02d}.atoms.json"
    if not atoms_path.exists():
        print(f"ERROR: atoms not found: {atoms_path}", file=sys.stderr)
        print(f"  (run extract_atoms.py for this PDF/page first)", file=sys.stderr)
        return 1

    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    findings_out = REVIEWS_DIR / f"{pdf.stem}-p{page:02d}.findings.json"
    log_path = _log_path_for(pdf, page)

    started_wall = time.time()
    if resume_log:
        log = resume_log
        # Resume tracks elapsed via started_at; we re-compute total at end.
        prior_iters = log.get("iterations", [])
        start_iter = (prior_iters[-1]["iter"] + 1) if prior_iters else 1
        previous_sig = (_findings_signature(prior_iters[-1].get("_findings_raw", []))
                        if prior_iters and prior_iters[-1].get("_findings_raw") else None)
    else:
        log = {
            "pdf": str(pdf),
            "page": page,
            "spec_path": str(spec_path),
            "golden_path": str(out_golden),
            "findings_path": str(findings_out),
            "started_at": _now_iso(),
            "iterations": [],
            "final_status": "running",
            "total_seconds": 0.0,
        }
        start_iter = 1
        previous_sig = None

    final_status = "running"

    for i in range(start_iter, max_iter + 1):
        iter_record: dict = {"iter": i}

        # --- 1. BUILD --------------------------------------------------------
        ok, breakdown, build_log = run_build(spec_path, out_golden)
        iter_record["spec_hash"] = _sha256_file(spec_path)
        iter_record["golden_kv_breakdown"] = breakdown
        if not ok:
            iter_record["decision"] = "build_failed"
            iter_record["build_error"] = build_log[-500:]
            log["iterations"].append(iter_record)
            final_status = "build_failed"
            print(f"[iter {i}/{max_iter}] BUILD FAILED:\n{build_log}")
            break

        total_kv = sum(v for k, v in breakdown.items() if k != "footnote_ref")
        build_summary = f"{total_kv} KVs ({_format_breakdown(breakdown)})"

        # --- 2. REVIEW -------------------------------------------------------
        prompt = golden_review.build_agent_prompt(
            out_golden, pdf, atoms_path, page, findings_out)

        if manual_review:
            print(f"\n[iter {i}/{max_iter}] build: {build_summary}")
            print(f"\n--- MANUAL REVIEW REQUIRED ---")
            print(f"Run the golden-reviewer agent with this prompt:\n")
            print(prompt)
            print(f"\nExpected output: {findings_out}")
            print(f"\nResume with:")
            print(f"  python3 scripts/golden_pipeline.py --resume {log_path}\n")
            iter_record["decision"] = "manual_review_pending"
            log["iterations"].append(iter_record)
            final_status = "awaiting_manual_review"
            break

        # Remove any stale findings from prior run so we know the agent wrote.
        if findings_out.exists():
            findings_out.unlink()

        ok, review_log = run_reviewer_agent(prompt, findings_out)
        if not ok:
            print(f"[iter {i}/{max_iter}] build: {build_summary}")
            print(f"\n⚠ Reviewer agent failed. Falling back to manual mode.")
            print(f"\n--- error ---\n{review_log[-1000:]}\n")
            print(f"Run manually:\n")
            print(prompt)
            print(f"\nExpected output: {findings_out}")
            print(f"\nResume with:")
            print(f"  python3 scripts/golden_pipeline.py --resume {log_path}\n")
            iter_record["decision"] = "manual_review_pending"
            iter_record["reviewer_error"] = review_log[-500:]
            log["iterations"].append(iter_record)
            final_status = "awaiting_manual_review"
            break

        try:
            findings_doc = golden_review.validate_findings(findings_out)
        except SystemExit as e:
            iter_record["decision"] = "invalid_findings"
            iter_record["error"] = str(e)
            log["iterations"].append(iter_record)
            final_status = "invalid_findings"
            print(f"[iter {i}/{max_iter}] build: {build_summary} → review: INVALID FINDINGS: {e}")
            break

        summary = findings_doc.get("summary", {})
        verdict = summary.get("verdict")
        findings = findings_doc.get("findings", [])
        iter_record["findings_summary"] = {
            "high": summary.get("high", 0),
            "medium": summary.get("medium", 0),
            "low": summary.get("low", 0),
            "verdict": verdict,
        }
        # Keep raw findings for resume + stuck detection (private key)
        iter_record["_findings_raw"] = findings

        review_summary = (
            f"{summary.get('high',0)}H/{summary.get('medium',0)}M/"
            f"{summary.get('low',0)}L {verdict}"
        )

        # --- 3. DECIDE -------------------------------------------------------
        if verdict == "PASS":
            iter_record["decision"] = "done"
            print(f"[iter {i}/{max_iter}] build: {build_summary} → review: {review_summary}")
            log["iterations"].append(iter_record)
            final_status = "done"
            break

        if verdict == "NEEDS_HUMAN":
            iter_record["decision"] = "escalated_to_human"
            print(f"[iter {i}/{max_iter}] build: {build_summary} → review: {review_summary}")
            log["iterations"].append(iter_record)
            final_status = "escalated_to_human"
            break

        if no_loop:
            iter_record["decision"] = "no_loop_stop"
            print(f"[iter {i}/{max_iter}] build: {build_summary} → review: {review_summary}")
            log["iterations"].append(iter_record)
            final_status = "no_loop_stop"
            break

        if i == max_iter:
            iter_record["decision"] = "max_iter_reached"
            print(f"[iter {i}/{max_iter}] build: {build_summary} → review: {review_summary}")
            log["iterations"].append(iter_record)
            final_status = "max_iter_reached"
            break

        # Stuck detection
        current_sig = _findings_signature(findings)
        if previous_sig is not None and current_sig == previous_sig:
            iter_record["decision"] = "stuck_no_progress"
            print(f"[iter {i}/{max_iter}] build: {build_summary} → review: {review_summary} → stuck (same findings as previous iter)")
            log["iterations"].append(iter_record)
            final_status = "stuck_no_progress"
            break
        previous_sig = current_sig

        # --- 4. PATCH --------------------------------------------------------
        ok, applied, skipped, patch_log = run_patcher(spec_path, findings_out)
        iter_record["patches_applied"] = applied
        iter_record["patches_skipped"] = skipped
        if not ok:
            iter_record["decision"] = "patch_failed"
            iter_record["patch_error"] = patch_log[-500:]
            print(f"[iter {i}/{max_iter}] build: {build_summary} → review: {review_summary} → patch FAILED")
            print(patch_log)
            log["iterations"].append(iter_record)
            final_status = "patch_failed"
            break

        iter_record["decision"] = "patch"
        print(f"[iter {i}/{max_iter}] build: {build_summary} → review: {review_summary} → patch: {applied} applied" + (f", {skipped} skipped" if skipped else ""))
        log["iterations"].append(iter_record)
        # continue loop

    # --- finalisation --------------------------------------------------------
    log["final_status"] = final_status
    log["total_seconds"] = round(time.time() - started_wall + log.get("total_seconds", 0.0), 2)

    # Strip private fields before persisting.
    persisted = dict(log)
    persisted["iterations"] = [
        {k: v for k, v in it.items() if not k.startswith("_")}
        for it in log["iterations"]
    ]
    _save_log(log_path, persisted)

    # --- final console line -------------------------------------------------
    n_iters = len(log["iterations"])
    elapsed = log["total_seconds"]
    if final_status == "done":
        print(f"\n✓ Pipeline done in {n_iters} iteration(s) ({elapsed}s). Final golden: {out_golden}")
        return 0
    elif final_status == "no_loop_stop":
        print(f"\n✓ Pipeline stopped after 1 iteration ({elapsed}s, --no-loop). Findings: {findings_out}")
        return 0
    elif final_status == "escalated_to_human":
        print(f"\n⚠ Pipeline escalated_to_human after {n_iters} iteration(s). Review findings: {findings_out}")
        return 10
    elif final_status == "stuck_no_progress":
        print(f"\n⚠ Pipeline stuck_no_progress after {n_iters} iteration(s). Review findings: {findings_out}")
        return 11
    elif final_status == "max_iter_reached":
        print(f"\n⚠ Pipeline max_iter_reached ({max_iter}) without PASS. Review findings: {findings_out}")
        return 12
    elif final_status == "awaiting_manual_review":
        print(f"\n→ Awaiting manual review. Iteration log: {log_path}")
        return 20
    else:
        print(f"\n✗ Pipeline failed: {final_status}. See iteration log: {log_path}")
        return 13


# ----- CLI -------------------------------------------------------------------

def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", help="Path to existing spec .py (required unless --resume or --scaffold)")
    ap.add_argument("--pdf", help="Path to source PDF (required unless --resume)")
    ap.add_argument("--page", type=int, help="Page number (required unless --resume)")
    ap.add_argument("--out-golden", help="Output golden.json path (default: derived)")
    ap.add_argument("--max-iter", type=int, default=3, help="Max iterations (default 3)")
    ap.add_argument("--no-loop", action="store_true",
                    help="Run build+review once; do not patch or loop")
    ap.add_argument("--manual-review", action="store_true",
                    help="Skip `claude --agent` invocation; print prompt + expect "
                         "user to run agent and then `--resume`")
    ap.add_argument("--resume", help="Resume from an iteration log JSON path")
    ap.add_argument("--scaffold", action="store_true",
                    help="Generate a draft spec via the golden-scaffolder agent "
                         "(Opus) before entering the loop. Requires --pdf --page; "
                         "--spec is ignored / overwritten at "
                         "scripts/specs/<stem>_p<NN>.py.")
    args = ap.parse_args(argv)

    if args.resume:
        log = _load_log(Path(args.resume))
        spec_path = Path(log["spec_path"])
        pdf = Path(log["pdf"])
        page = int(log["page"])
        out_golden = Path(log["golden_path"])
        # Reset final_status to running so we re-evaluate.
        log["final_status"] = "running"
        # We can't recover previous_sig from persisted log (we stripped raw
        # findings) — rebuild from the latest findings file if present.
        findings_path = Path(log.get("findings_path", ""))
        if findings_path.exists() and log["iterations"]:
            try:
                doc = json.loads(findings_path.read_text())
                log["iterations"][-1]["_findings_raw"] = doc.get("findings", [])
            except Exception:
                pass
        return run_pipeline(spec_path, pdf, page, out_golden,
                            max_iter=args.max_iter, no_loop=args.no_loop,
                            manual_review=args.manual_review, resume_log=log)

    # Fresh run — required args depend on mode.
    if args.scaffold:
        missing = [n for n, v in (("--pdf", args.pdf), ("--page", args.page))
                   if v in (None, "")]
    else:
        missing = [n for n, v in (("--spec", args.spec), ("--pdf", args.pdf),
                                  ("--page", args.page)) if v in (None, "")]
    if missing:
        print(f"ERROR: missing required args: {', '.join(missing)}", file=sys.stderr)
        return 2

    pdf = Path(args.pdf)
    page = int(args.page)

    if args.scaffold:
        # Generate the draft spec first.
        _, _, scaffold_out = golden_scaffold._resolve_paths(
            args.pdf, page, args.spec)
        print(f"[scaffold] generating draft spec at {scaffold_out}")
        scaffold_rc = golden_scaffold.main([
            "--pdf", args.pdf, "--page", str(page),
            "--out", str(scaffold_out),
        ])
        if scaffold_rc != 0:
            print(f"ERROR: scaffolder failed with exit {scaffold_rc}", file=sys.stderr)
            return scaffold_rc
        spec_path = scaffold_out
    else:
        spec_path = Path(args.spec)
    if args.out_golden:
        out_golden = Path(args.out_golden)
    else:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        out_golden = GOLDEN_DIR / f"{pdf.stem}-p{page:02d}.json"

    return run_pipeline(spec_path, pdf, page, out_golden,
                        max_iter=args.max_iter, no_loop=args.no_loop,
                        manual_review=args.manual_review, resume_log=None)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
