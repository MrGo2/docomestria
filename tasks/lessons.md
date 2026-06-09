# Lessons

## Golden pipeline — orchestrate via Agent tool, not the batch scripts (2026-06-07)

`golden_pipeline_batch.py` / `golden_pipeline.py` / `golden_scaffold.py` shell out to
`claude --agent ...` subprocesses. Run from inside a Claude Code session they **fail
silently**: orphaned children outlive a parent kill, logs stay empty, no spec/golden is
written. Burned Opus tokens for nothing on doc 25356487E.

**Do instead:** dispatch `golden-scaffolder` and `golden-reviewer` via the Agent tool
directly (parallel, one per page). Only `build_golden.py` is safe to run inline.

## spec_patcher.py can't apply reviewer findings (2026-06-07)

Applied 0/12 patches on 25356487E — every finding skipped: `fix_value missing 'value'`,
`add_kv needs target kv_group id`, `update_y_hint requires kv-pair target, got id`.

**Do instead:** resume the original `golden-scaffolder` agent via SendMessage with the
findings path — it edits the spec with judgment and rebuilds. Patcher is only good for
purely mechanical y_hint/x_hint shifts that carry full params.

## Triage under-weights cover pages (2026-06-07)

`page_triage.py` scores p01/p02 as `low_priority` because they lack pdfplumber tables,
but they hold the richest KV in CaixaBank contracts (parties, vehicle, financial terms,
signatures). Always include them regardless of triage verdict.
