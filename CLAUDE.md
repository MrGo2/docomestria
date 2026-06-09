# docomestria

Structural Key-Information-Extraction (KIE) for Spanish business PDFs (bank contracts, loan
agreements). Tri-engine geometry: **pdfplumber + Docling + LiteParse v2**, reconciled into a
recursive hierarchical golden tree (section/array/table/kv).

## Two extraction worlds — don't conflate them

| World | Path | Purpose |
|---|---|---|
| **Production** | `src/docomestria/structural/` | The live extractor. Rule vocab: `D-2col`, `L-inline-split`, … |
| **Annotation** | `.planning/extraction/` | Research CRF+ILP pipeline (Capa 0–9). Rule vocab: `structured-table-cell`, … Golden-sample creation only. |

The `kie-*` agents operate on the **annotation** world. Everything else targets **production**.

## Orchestrate — don't do it yourself

This repo's read-heavy work is delegated. See the global standard in
`~/.claude/rules/common/orchestration.md`. Route to the right agent:

| Need | Agent |
|---|---|
| Production extraction bug (engine geometry) | `liteparse-expert` · `pdfplumber-expert` · `docling-expert` |
| Value exists but isn't paired (geometric/bbox) | `bbox-geometry-debugger` |
| New/changed candidate emitter (`candidates.py`) | `emitter-designer` |
| Unit tests for `structural/` | `extraction-test-writer` |
| Pre-commit regression check (5-PDF Azure DI + ParseBench) | `regression-runner` |
| Annotate a golden page | `golden-scaffolder` → build → `golden-reviewer` → `spec-patcher` |
| Annotate across many pages | `kie-orchestrator` (dispatches `kie-extractor`) |

Each agent returns a tight structured block (FINDINGS / CHANGES / PATCHED), not a transcript.
Run independent work as parallel `Agent` calls.

## Golden pipeline (4 stages)

`golden-scaffolder` (spec.py draft) → `PYTHONPATH=src python3 scripts/build_golden.py <spec>`
→ `golden-reviewer` (findings.json) → `spec-patcher` (apply mechanical fixes) → re-build.

## Key paths

- Production extractor: `src/docomestria/structural/` (classify · structure · candidates · scoring · extractor)
- Golden builder lib: `src/docomestria/golden/` · CLI `scripts/build_golden.py`
- Regression baseline: `.regression/baseline.json` (never `git stash --include-untracked` here)
- Engines: `src/docomestria/engines/` (liteparse · docling · pdfplumber)
