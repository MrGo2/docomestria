# Live Engine-Fusion Substrate — Design

**Date:** 2026-06-09
**Branch:** `feature/structural-extraction`
**Status:** Design — pending review

## Purpose

Produce, for every text item on a **live** PDF, the same fused three-engine "signal"
that today exists **only offline** in the golden/research world. This signal is the
shared input substrate that the trained Job A role classifier — and later Job B
(pairing) and Job C (tables) — need to run in production.

This project delivers the substrate and **proves it is faithful** by running the Job A
model on live-fused inputs and confirming the model's accuracy survives. It does **not**
wire the model into the live extractor; that is a separate follow-on ("A-wiring").

## Background — why this is needed

The production extractor (`src/docomestria/structural/extractor.py`) runs the three
engines, then calls `classify(lite_items)` (`structural/classify.py`) using **only
LiteParse's output**. Docling blocks and pdfplumber rects join *later*
(`detect_structure`), and only for tables/sections — never fused per item at classify
time.

The Job A model needs ~40 features (`golden/training_table.py:17-42`) built from a
per-item fused signal dict `{liteparse, docling, pdfplumber, rect, colon_signal,
engine_agreement}`. That fusion is built **only** in the golden builder, from pre-cached
`atoms.json` files (`golden/cell_linker.py:64-88`, `golden/engine_data.py:107-131`,
`golden/structural.py:39-43`). **Production has no equivalent.** Feature parity verdict
from the feasibility investigation: **MISSING**.

So "wiring A into production" is mostly *building this fusion layer*. The role classifier
plugs in trivially once it exists.

## Scope

### In scope
1. **Shared join core** — extract the per-item engine-join logic out of the golden world
   into one input-agnostic module operating on **in-memory engine outputs** (not atoms
   files).
2. **Golden refactor** — make the golden builder call the shared core. Behavior-preserving:
   the regenerated golden training table must match a committed baseline fixture.
3. **Live fusion layer** — `build_signals(lite_items, docling_blocks, plumber_rects)` →
   per-item fused signals, calling the shared core.
4. **Acceptance harness** — for the golden PDFs, run the **live** fusion path → shared
   feature builder → trained model → score against golden truth roles. Gate: macro-F1 ≥ 0.86.

### Out of scope (follow-on "A-wiring" project)
- Production model loader under `src/`.
- Replacing `classify()` with model inference.
- The 7→5 role-vocabulary mapping (`signature`/`table_header` have no `ItemKind` today).
- `ItemKind`/`ClassifiedItem` changes; downstream `candidates.py` consumers.
- The regression-benchmark (5-PDF Azure DI + ParseBench) production before/after.

This project **ends** when live-fused features prove the model holds ≥ 0.86.

## Architecture

New sibling package, same repo / same branch:

```
src/docomestria/
├── structural/   (exists — live extractor)
├── engines/      (exists — liteparse, docling, pdfplumber)
├── golden/       (exists — offline research world)
├── training/     (exists — Job A model)
└── fusion/       (NEW)
    ├── join.py        # the shared join core (input-agnostic)
    ├── signals.py     # build_signals(...) live entry point
    └── ...
```

### Entry point (the boundary)
```
build_signals(lite_items, docling_blocks, plumber_rects) -> list[ItemSignal]
```
One clean function. Everything downstream (Job A features, later B/C) consumes its output.

### Shared join core
The core is what both callers share. It takes **in-memory** engine outputs (LiteParse
spans, Docling blocks/cells, pdfplumber rects) and emits, per item, the signal dict shape
`signal_features` already expects: `{liteparse, docling, pdfplumber, rect, colon_signal,
engine_agreement}`.

- **Golden caller:** the golden builder reads its cached engine outputs from `atoms.json`
  as it does today, then feeds them to the shared core (instead of its own inline join).
- **Live caller:** `build_signals` feeds the engines' live in-memory outputs to the same core.

One implementation, two callers → drift minimized by construction (the reason for the
"extract & share" decision).

### Reusable feature functions (already input-agnostic — share as-is)
Per the feasibility investigation, these in `golden/training_table.py` take plain
dicts/bboxes and are reusable at inference:
`signal_features` (:95), `content_flags` (`golden/text_features.py:37`), `_overlap_frac`
(:122), `_bbox_center`/`_point_in_bbox` (:135-141), `find_enclosing_block` (:144),
`find_enclosing_cell` (:178), `signature_rect_bboxes` + `_is_signature` (:162),
`point_in_any_bbox` (:174), `_onehot_case` (:87), `_item_to_partial_row` (:424), and the
page-level/neighbour loop in `build_page_rows` (:501-560).

The **only** piece not reusable as-is is the **signal construction (engine join)** — today
atoms-file-coupled. That is precisely what the shared join core replaces.

## Data flow

```
PDF → [3 engines: liteparse, docling, pdfplumber]   (exists)
    → build_signals(...)            → per-item fused signals      (NEW)
    → shared feature builder        → feature rows                (shared from golden)
    → [acceptance harness] trained model → predicted roles → score vs golden truth
```

## Acceptance gate (definition of done)

Validation harness over the golden PDFs:
1. Run the **live** fusion path (`build_signals` from live engine outputs) → features.
2. Load the trained model (`.planning/extraction/training/role_model.pkl`).
3. Predict roles; score macro-F1 against the golden truth roles, same metric/label order
   as `role_model_report.json`.

**PASS if macro-F1 ≥ 0.86** (the 0.88 offline baseline minus a small tolerance for
live-vs-golden differences). On failure, the harness reports which features/items diverge
from the golden-path features so the join can be fixed until it holds.

The harness loads the model only as a **test rig** — this is not the production loader
(that is out of scope / A-wiring).

## Behavior-preserving guard

After the golden refactor, regenerate the golden training table with the shared core and
assert it matches a **committed baseline fixture** pinned to an immutable SHA — never a
relative git ref (a moving baseline silently passes). This protects the training data we
already trust. Any intended difference must be documented and the fixture re-pinned
deliberately.

## Risks

1. **Live item set vs golden-anchored items.** Training features were derived from golden
   atoms with fail-closed bbox matching (`training_table.py:192-228`); the live join pairs
   engines without golden anchors, so the live *set of items* (raw LiteParse spans) may not
   align 1:1 with golden truth items. The acceptance gate (score vs golden truth on golden
   PDFs) is designed to catch exactly this. Mitigation if it fires: an item-alignment step
   matching live spans to golden truth by bbox for the harness only.
2. **Feature-distribution drift.** Even with shared join code, live vs golden inputs may
   differ in edge cases (missing engine, OCR variance). The gate measures this end-to-end;
   the per-feature divergence report localizes it.
3. **Model packaging.** The `.pkl` lives in `.planning/extraction/training/` (research dir),
   not under `src/`, and the sklearn pin is inconsistent across `pyproject.toml` extras
   (`>=1.7.2,<2` vs `>=1.3,<2`). For *this* project the harness reads it in place with an
   sklearn-version check; relocation/packaging + a versioned loader is A-wiring's concern.

## Testing

- **Unit:** shared join core — fixtured engine outputs (LiteParse spans + Docling blocks +
  pdfplumber rects) → expected per-item signals. Cover the join edge cases (item in no
  block, item in a table cell, item over a signature rect, engine missing).
- **Integration:** the acceptance harness as a test — live-fusion features → model →
  macro-F1 ≥ 0.86 on the golden set.
- **Regression guard:** golden-table byte-parity vs the committed baseline fixture.

## Open questions for review
- Tolerance: is 0.86 the right pass bar, or stricter (0.87) / looser (0.85)?
- Should the shared join core live in `fusion/` (live-owned) or `golden/` (research-owned)
  with `fusion/` importing it? (Recommendation: `fusion/`, since it is the production-facing
  substrate and golden becomes a caller.)
