#!/usr/bin/env python3
"""golden_pipeline_batch — run golden_pipeline.py over many pages of one PDF.

Phase 5 of the automation plan. Wraps the single-page orchestrator into a
parallel batch driver that consumes the triage file produced by the structural
pass.

CLI:
    python3 scripts/golden_pipeline_batch.py \\
        --pdf "/path/to/contract.pdf" \\
        [--pages 1,2,3,4]              # override triage extract_pages
        [--scaffold]                    # use scaffolder for pages without spec
        [--max-iter 3]                  # passed through to each per-page run
        [--parallel 4]                  # max concurrent per-page pipelines
        [--skip-existing]               # don't re-run pages with valid golden
        [--force]                       # opposite: re-run even if golden exists
        [--manual-review]               # pass through (each page exits at review)
        [--no-loop]                     # pass through (build+review once)

Outputs `.planning/extraction/batch/<pdf_stem>.batch.json` plus a console
summary table.

Pure stdlib. Uses concurrent.futures.ThreadPoolExecutor — each worker calls
`golden_pipeline.py` as a subprocess so the parallelism is process-bound, not
GIL-bound.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
TRIAGE_DIR = ROOT / ".planning" / "extraction" / "triage"
GOLDEN_DIR = ROOT / ".planning" / "extraction" / "golden"
ITERATIONS_DIR = ROOT / ".planning" / "extraction" / "iterations"
BATCH_DIR = ROOT / ".planning" / "extraction" / "batch"
SPECS_DIR = SCRIPTS_DIR / "specs"

# Exit codes from golden_pipeline.py (mirrors that script's docstring)
RC_TO_STATUS = {
    0: "done",
    10: "escalated",
    11: "stuck",
    12: "max_iter",
    13: "failed",
    20: "awaiting_manual_review",
}


# ----- helpers ---------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _triage_path_for(pdf: Path) -> Path:
    return TRIAGE_DIR / f"{pdf.stem}.triage.json"


def _sanitise_stem(stem: str) -> str:
    """Same sanitisation rules as golden_scaffold.py."""
    stem = stem.strip().lower()
    safe = []
    for ch in stem:
        if ch.isalnum():
            safe.append(ch)
        elif ch in (" ", "-", "_"):
            safe.append("_")
    out = "".join(safe).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out


# Known short aliases for hand-curated specs (precede sanitised stem).
_STEM_ALIASES: dict[str, list[str]] = {
    "contrato_ikea": ["ikea"],
    "contrato_prestamo_comercio_2": ["prestamo_comercio"],
    "laboral": ["laboral"],
    "patrimonial": ["patrimonial"],
    "bbva_0539_01547731_doc2_contrato": ["bbva_0539"],
    "bbva_0544_01547787_doc2_contrato": ["bbva_0544"],
    "bbva_0608_01491495_doc2_contrato": ["bbva_0608"],
    "bbva_0686_01516762_doc2_contrato": ["bbva_0686"],
    "contrato_tarjeta_3": ["tarjeta_3"],
    "contrato_tarjeta_mediamrket": ["tarjeta_mediamrket"],
}


def _spec_path_for(pdf: Path, page: int) -> Path:
    """Resolve spec path for (pdf, page).

    Prefers existing files matching known short aliases (ikea_p02.py); falls
    back to the sanitised-stem convention used by the scaffolder
    (contrato_ikea_p02.py).
    """
    sanitised = _sanitise_stem(pdf.stem)
    candidates: list[str] = []
    for alias in _STEM_ALIASES.get(sanitised, []):
        candidates.append(f"{alias}_p{page:02d}.py")
    candidates.append(f"{sanitised}_p{page:02d}.py")
    for name in candidates:
        p = SPECS_DIR / name
        if p.exists():
            return p
    # Default to the scaffolder-style path (for `--scaffold` to write into).
    return SPECS_DIR / candidates[-1]


def _golden_path_for(pdf: Path, page: int) -> Path:
    return GOLDEN_DIR / f"{pdf.stem}-p{page:02d}.json"


def _iter_log_path_for(pdf: Path, page: int) -> Path:
    return ITERATIONS_DIR / f"{pdf.stem}-p{page:02d}.iterations.json"


def _parse_pages(s: str) -> list[int]:
    out: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def _load_triage_pages(pdf: Path) -> list[int]:
    tp = _triage_path_for(pdf)
    if not tp.exists():
        return []
    try:
        doc = json.loads(tp.read_text(encoding="utf-8"))
    except Exception:
        return []
    return list(doc.get("summary", {}).get("extract_pages", []) or [])


def _golden_is_valid(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 16:
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(doc.get("kv_pairs") is not None or doc.get("structure"))


def _read_iter_log_summary(pdf: Path, page: int) -> dict:
    """Extract final_status + iterations count from per-page iteration log."""
    p = _iter_log_path_for(pdf, page)
    if not p.exists():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    iters = doc.get("iterations") or []
    last = iters[-1] if iters else {}
    return {
        "final_status": doc.get("final_status"),
        "iterations": len(iters),
        "last_decision": last.get("decision"),
        "last_findings_summary": last.get("findings_summary"),
    }


def _count_kvs(golden_path: Path) -> int:
    if not golden_path.exists():
        return 0
    try:
        doc = json.loads(golden_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    return len(doc.get("kv_pairs") or [])


# ----- per-page worker -------------------------------------------------------

def _build_cmd(pdf: Path, page: int, spec_path: Path, scaffold: bool,
               max_iter: int, manual_review: bool, no_loop: bool) -> list[str]:
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "golden_pipeline.py"),
        "--pdf", str(pdf), "--page", str(page),
        "--max-iter", str(max_iter),
    ]
    if scaffold and not spec_path.exists():
        cmd.append("--scaffold")
    else:
        cmd.extend(["--spec", str(spec_path)])
    if manual_review:
        cmd.append("--manual-review")
    if no_loop:
        cmd.append("--no-loop")
    return cmd


def _run_one_page(pdf: Path, page: int, *, scaffold: bool, max_iter: int,
                  manual_review: bool, no_loop: bool, skip_existing: bool,
                  force: bool) -> dict:
    started = time.time()
    spec_path = _spec_path_for(pdf, page)
    golden_path = _golden_path_for(pdf, page)
    rec: dict = {
        "page": page,
        "spec_path": str(spec_path),
        "golden_path": str(golden_path),
        "started_at": _now_iso(),
    }
    # Skip logic
    if skip_existing and not force and _golden_is_valid(golden_path):
        rec["status"] = "skipped_existing"
        rec["kv_count"] = _count_kvs(golden_path)
        rec["seconds"] = round(time.time() - started, 2)
        rec["finished_at"] = _now_iso()
        return rec

    # Needs scaffolder?
    needs_scaffold = scaffold and not spec_path.exists()
    if not needs_scaffold and not spec_path.exists():
        rec["status"] = "no_spec"
        rec["error"] = f"spec not found: {spec_path} (pass --scaffold to generate)"
        rec["seconds"] = round(time.time() - started, 2)
        rec["finished_at"] = _now_iso()
        return rec

    cmd = _build_cmd(pdf, page, spec_path, scaffold, max_iter,
                     manual_review, no_loop)
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(ROOT),
            timeout=max_iter * 900 + 300,  # generous: scaffold can be slow
        )
        rc = res.returncode
        stdout = res.stdout or ""
        stderr = res.stderr or ""
    except subprocess.TimeoutExpired as e:
        rc = 124
        stdout = ""
        stderr = f"batch worker timeout: {e}"

    rec["exit_code"] = rc
    rec["status"] = RC_TO_STATUS.get(rc, "failed")
    rec["stdout_tail"] = stdout[-2000:]
    rec["stderr_tail"] = stderr[-1000:]
    rec["kv_count"] = _count_kvs(golden_path)

    # Pull final_status + iterations from the iteration log if it exists.
    log_summary = _read_iter_log_summary(pdf, page)
    if log_summary:
        rec.update({
            "iterations": log_summary.get("iterations"),
            "iter_final_status": log_summary.get("final_status"),
            "last_findings_summary": log_summary.get("last_findings_summary"),
        })

    rec["seconds"] = round(time.time() - started, 2)
    rec["finished_at"] = _now_iso()
    return rec


# ----- summary helpers -------------------------------------------------------

_BUCKETS = {
    "done": "pages_done",
    "skipped_existing": "pages_skipped",
    "escalated": "pages_escalated",
    "stuck": "pages_stuck",
    "max_iter": "pages_max_iter",
    "awaiting_manual_review": "pages_manual_review",
    "no_spec": "pages_failed",
    "failed": "pages_failed",
}


def _summarize(pdf: Path, recs: list[dict], started: str,
               finished: str) -> dict:
    pages_attempted = sorted(r["page"] for r in recs)
    buckets: dict[str, list[int]] = {v: [] for v in set(_BUCKETS.values())}
    per_page: dict[str, dict] = {}
    total_kv = 0
    total_seconds = 0.0
    for r in recs:
        status = r.get("status", "failed")
        bucket = _BUCKETS.get(status, "pages_failed")
        buckets[bucket].append(r["page"])
        per_page[str(r["page"])] = {
            "status": status,
            "iterations": r.get("iterations"),
            "kv_count": r.get("kv_count", 0),
            "seconds": r.get("seconds", 0.0),
            "exit_code": r.get("exit_code"),
            "spec_path": r.get("spec_path"),
            "golden_path": r.get("golden_path"),
            "iter_final_status": r.get("iter_final_status"),
            "last_findings_summary": r.get("last_findings_summary"),
            "error": r.get("error"),
        }
        total_kv += int(r.get("kv_count") or 0)
        total_seconds += float(r.get("seconds") or 0.0)
    return {
        "pdf": str(pdf),
        "started_at": started,
        "finished_at": finished,
        "pages_attempted": pages_attempted,
        **{k: sorted(v) for k, v in buckets.items()},
        "per_page": per_page,
        "totals": {
            "pages": len(pages_attempted),
            "kv": total_kv,
            "seconds": round(total_seconds, 2),
        },
    }


def _fmt_pages(ps: list[int]) -> str:
    if not ps:
        return "—"
    return ", ".join(f"p{p:02d}" for p in ps)


def _fmt_dur(secs: float) -> str:
    secs = int(secs)
    m, s = divmod(secs, 60)
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _print_console_report(pdf: Path, summary: dict, summary_path: Path) -> None:
    print()
    print(f"✓ Batch summary for {pdf.name}:")
    print(f"  Pages attempted:     {len(summary['pages_attempted']):>3}  ({_fmt_pages(summary['pages_attempted'])})")
    print(f"  Done:                {len(summary['pages_done']):>3}  ({_fmt_pages(summary['pages_done'])})")
    if summary.get("pages_skipped"):
        print(f"  Skipped (existing):  {len(summary['pages_skipped']):>3}  ({_fmt_pages(summary['pages_skipped'])})")
    if summary.get("pages_manual_review"):
        print(f"  Awaiting review:     {len(summary['pages_manual_review']):>3}  ({_fmt_pages(summary['pages_manual_review'])})")
    if summary.get("pages_escalated"):
        print(f"  Escalated to human:  {len(summary['pages_escalated']):>3}  ({_fmt_pages(summary['pages_escalated'])})")
    if summary.get("pages_stuck"):
        print(f"  Stuck:               {len(summary['pages_stuck']):>3}  ({_fmt_pages(summary['pages_stuck'])})")
    if summary.get("pages_max_iter"):
        print(f"  Max-iter reached:    {len(summary['pages_max_iter']):>3}  ({_fmt_pages(summary['pages_max_iter'])})")
    if summary.get("pages_failed"):
        print(f"  Failed:              {len(summary['pages_failed']):>3}  ({_fmt_pages(summary['pages_failed'])})")
    print(f"  Total KVs:           {summary['totals']['kv']:>3}")
    print(f"  Total time:          {_fmt_dur(summary['totals']['seconds'])}")
    print(f"  Full report:         {summary_path.relative_to(ROOT)}")


# ----- main ------------------------------------------------------------------

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Run golden_pipeline.py across all extract-verdict pages of one PDF.",
    )
    ap.add_argument("--pdf", required=True, help="Path to the source PDF")
    ap.add_argument("--pages", help="Comma/range list of pages (overrides triage)")
    ap.add_argument("--scaffold", action="store_true",
                    help="Use scaffolder for pages without an existing spec")
    ap.add_argument("--max-iter", type=int, default=3,
                    help="Max iterations per page (default 3)")
    ap.add_argument("--parallel", type=int, default=4,
                    help="Max concurrent per-page pipelines (default 4)")
    skip_grp = ap.add_mutually_exclusive_group()
    skip_grp.add_argument("--skip-existing", action="store_true",
                          help="Skip pages with a valid golden already")
    skip_grp.add_argument("--force", action="store_true",
                          help="Re-run even if a valid golden exists")
    ap.add_argument("--manual-review", action="store_true",
                    help="Pass --manual-review to each page run")
    ap.add_argument("--no-loop", action="store_true",
                    help="Pass --no-loop to each page run")
    args = ap.parse_args(argv)

    pdf = Path(args.pdf)
    if not pdf.exists():
        print(f"ERROR: PDF not found: {pdf}", file=sys.stderr)
        return 1

    if args.pages:
        pages = _parse_pages(args.pages)
        if not pages:
            print(f"ERROR: --pages parsed to empty list", file=sys.stderr)
            return 2
        page_source = "explicit"
    else:
        pages = _load_triage_pages(pdf)
        if not pages:
            print(f"ERROR: no triage extract_pages for {pdf.name} "
                  f"and no --pages given.\n"
                  f"  Expected: {_triage_path_for(pdf)}", file=sys.stderr)
            return 2
        page_source = "triage"

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = BATCH_DIR / f"{pdf.stem}.batch.json"

    print(f"[batch] PDF: {pdf}")
    print(f"[batch] Pages ({page_source}): {pages}")
    print(f"[batch] Parallel: {args.parallel}")
    if args.skip_existing:
        print(f"[batch] Skip existing: yes")
    if args.force:
        print(f"[batch] Force re-run: yes")
    if args.scaffold:
        print(f"[batch] Scaffold for new pages: yes")
    if args.manual_review:
        print(f"[batch] Manual review mode: yes (each page will exit at review)")

    started_iso = _now_iso()
    started_wall = time.time()

    recs: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
        futures = {
            ex.submit(
                _run_one_page, pdf, p,
                scaffold=args.scaffold, max_iter=args.max_iter,
                manual_review=args.manual_review, no_loop=args.no_loop,
                skip_existing=args.skip_existing, force=args.force,
            ): p
            for p in pages
        }
        for fut in cf.as_completed(futures):
            page = futures[fut]
            try:
                rec = fut.result()
            except Exception as e:  # pragma: no cover — worker shouldn't raise
                rec = {
                    "page": page,
                    "status": "failed",
                    "error": f"worker raised: {e!r}",
                    "seconds": 0.0,
                }
            recs.append(rec)
            short = rec.get("status", "?")
            kv = rec.get("kv_count", 0)
            secs = rec.get("seconds", 0.0)
            print(f"[batch] page {page:>3} → {short:<22} kv={kv:<3} ({secs}s)")

    finished_iso = _now_iso()
    finished_wall = time.time()
    summary = _summarize(pdf, recs, started_iso, finished_iso)
    summary["totals"]["wall_seconds"] = round(finished_wall - started_wall, 2)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _print_console_report(pdf, summary, summary_path)

    # Exit code: 0 only if every attempted page is done or skipped.
    if (summary["pages_failed"] or summary["pages_stuck"]
            or summary["pages_max_iter"]):
        return 13
    if summary["pages_manual_review"] or summary["pages_escalated"]:
        return 10
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
