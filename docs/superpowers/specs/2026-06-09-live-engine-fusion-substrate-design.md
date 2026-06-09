# Live Engine-Fusion Substrate — Design (v2, post-review)

**Date:** 2026-06-09
**Branch:** `feature/structural-extraction`
**Status:** Design — pending review (rewritten after Codex review of v1 found 3 blockers)

## Purpose

Produce, for every text item on a **live** PDF, the same fused three-engine "signal"
the trained Job A role classifier consumes — a signal that today exists **only offline**
in the golden builder. Then **prove faithfulness** by rebuilding the feature table from
the live path and re-running the model's own cross-validation, requiring macro-F1 ≥ 0.86
(offline baseline 0.88).

This delivers the substrate and its proof. It does **not** wire the model into the live
extractor (separate follow-on, "A-wiring").

## Why v1 was wrong (review corrections)

A Codex review + re-investigation corrected three false assumptions:

1. **A fusion layer already exists and ships in production** — `src/docomestria/fusion.py`
   `fuse_from_engines(lite_items, docling_blocks, visual_rects) -> FusedItem` (used by
   `pipeline/_stream.py:98,136`, `pipeline/pipeline.py:158`). **But it is VisualRect-only.**
   `FusedItem` (`models.py:111`) carries `font_size`, `docling_label/heading_level`, an
   enclosing-box id — and **none** of the model's strongest signals: no `is_bold`, no
   `case_class`, no `colon_present`, no char-based `engine_agreement` (the model's #2
   feature, importance 0.21). Wrapping it would feed the model ~6 blank/wrong features, so
   the live score would not reflect 0.88. → **build new**, do not wrap.

2. **A live engine capability is missing entirely.** `colon_present` and the pdfplumber
   side of `engine_agreement` are computed from pdfplumber **raw characters**
   (`golden/engine_data.py:64`, `golden/cell_linker.py:82`). The production pdfplumber
   engine (`engines/pdfplumber.py`) exposes **only** `extract_visual_rects` — **no live
   char/word extraction exists.** Adding it is work item #1.
   - Note: `value_extent` is **not** a model feature (annotation artifact) — we do **not**
     need it. Only `colon_present` + per-item pdfplumber char/word *presence* are needed.

3. **The v1 acceptance gate was invalid.** `role_model.pkl` is refit on **all** rows
   (`role_classifier.py:111`); the 0.8799 is pooled out-of-fold from
   `evaluate_oof(df, n_splits=5, random_state=0)` under GroupKFold-by-pdf
   (`role_classifier.py:67`). Scoring the .pkl on the golden PDFs is in-sample (inflated),
   not comparable. The faithful gate **rebuilds the feature table from the live path and
   re-runs `evaluate_oof`** — never scores the .pkl.

## Scope

### In scope
1. **Live char emitter** — add char/word extraction to `engines/pdfplumber.py` (per-page
   chars/words with bbox), so `colon_present` and pdfplumber per-item presence exist
   outside the atoms cache.
2. **Shared feature-row function** — factor the pure per-item signal→feature-row
   computation out of `golden/training_table.py:build_page_rows` into a shared function
   (new `src/docomestria/feature_rows.py`), imported by **both** the golden builder and the
   live path. Golden behavior must be preserved (byte-parity, below).
3. **Live signal-builder** — new `src/docomestria/live_signals.py`:
   `build_signals(lite_items, docling_blocks, visual_rects, chars) -> list[signal]`
   producing per-item signal dicts shaped exactly like the golden ones. Reuses `fusion.py`'s
   geometric matching for the parts it covers (Docling block via IoU, containing rect,
   table cell) and **adds** the missing fields: `is_bold` (from `font_name` via
   `classify.is_bold`), `case_class` (from text), `colon_present` + pdfplumber presence
   (from chars), `engine_agreement` (count of the three engines per item),
   `rect_is_signature_field` (from `VisualRect.rect_type == "signature_field"`).
4. **Alignment + faithful gate harness** — align live LiteParse spans to golden truth roles
   (normalized-text + bbox overlap ≥ 0.30, reusing `_overlap_frac` `training_table.py:122`
   and `_norm` `engine_data.py:25`); build the feature table via the live path; run
   `evaluate_oof`; assert macro-F1 ≥ 0.86. On failure, emit a per-feature divergence report
   (live table vs golden table for aligned items) to localize the drift.

### Out of scope (follow-on "A-wiring")
- Production model loader under `src/`; replacing `classify()` with model inference.
- 7→5 role-vocabulary mapping (`signature`/`table_header` have no `ItemKind`); `ItemKind`/
  `candidates.py` changes.
- Regression-benchmark (5-PDF Azure DI + ParseBench) production before/after.

This project **ends** when the live-path feature table holds macro-F1 ≥ 0.86 under
`evaluate_oof`.

## Architecture

```
src/docomestria/
├── engines/pdfplumber.py   (CHANGE — add char/word extraction)
├── fusion.py               (REUSE — geometric matching; ships in pipeline, untouched)
├── feature_rows.py         (NEW — shared pure signal→feature-row fn)
├── live_signals.py         (NEW — build_signals(...): live golden-shaped signals)
├── golden/training_table.py(REFACTOR — call shared feature_rows; behavior-preserving)
└── training/role_classifier.py (REUSE — evaluate_oof for the gate)
```

### Data flow
```
PDF → engines: liteparse spans + docling blocks + visual rects + NEW chars
    → live_signals.build_signals(...)        → per-item golden-shaped signals   (NEW)
    → feature_rows (shared)                   → feature table                    (shared)
    → [gate] align to golden truth → evaluate_oof (GroupKFold) → macro-F1 ≥ 0.86
```

The engine-**join** legitimately differs between golden (atoms + annotation anchors) and
live (engine geometry + chars); that is expected. What is **shared** is the downstream
signal→feature computation — the part that must be identical to avoid drift.

## Acceptance gate (definition of done)

1. For the golden PDFs, build per-item signals via the **live** path (`build_signals`).
2. Align each live item to a golden truth role (norm-text + overlap ≥ 0.30); unmatched
   live items are excluded from scoring (reported, not silently dropped).
3. Build the feature table from these live signals via the shared `feature_rows`.
4. Run `evaluate_oof(df)` (GroupKFold-by-pdf, the same protocol that produced 0.88).
5. **PASS if pooled-OOF macro-F1 ≥ 0.86.** On failure, the divergence report names which
   features differ from the golden-path table for aligned items.

The harness lives under `scripts/` (and a thinned integration test); it does **not** load
the refit `.pkl`.

## Behavior-preserving guard

The only golden change is extracting a pure feature-row function and having
`build_page_rows` call it. After the refactor, regenerate the golden training table and
assert byte-parity against a **committed baseline fixture** pinned to an immutable SHA
(never a relative git ref). Any intended diff must be documented and the fixture re-pinned.

## Risks

1. **Char-derived feature parity (primary).** `colon_present` and the pdfplumber share of
   `engine_agreement` are rebuilt live from a new char emitter; they may not match the
   golden values, and `engine_agreement` is the #2 feature. The gate is designed to catch
   exactly this; the divergence report localizes it. This is the main reason the gate could
   return < 0.86 and send us back to the emitter.
2. **Docling per-cell header flags absent live.** `docling_column_header`/`row_header` are
   per-cell in golden but `DoclingBlock` has no per-cell header info, so they would be
   blank live. **Impact: negligible** — both features have **0.0 importance** in the model
   report. We leave them blank and document it.
3. **Alignment ambiguity.** Live LiteParse spans are not 1:1 with golden annotated items.
   The matcher (norm-text + overlap ≥ 0.30) mirrors `rederive_signal`/`noise_items`; items
   with no match are excluded from the gate score and reported, so the gate stays honest
   about coverage.

## Testing
- **Unit:** char emitter (fixtured page → chars/words with bbox); `build_signals`
  (fixtured engine outputs → expected signal dict, covering item-in-no-block, item-in-cell,
  item-over-signature-rect, missing-engine); the shared `feature_rows` (signal → row).
- **Integration:** the gate harness — live feature table → `evaluate_oof` ≥ 0.86 on the
  golden set.
- **Regression guard:** golden-table byte-parity vs the committed baseline fixture.

## Open questions for review
- Pass bar 0.86 — right tolerance, or 0.87 (stricter) / 0.85 (looser)?
- Shared feature fn at `src/docomestria/feature_rows.py` (neutral root) vs inside `golden/`
  — recommendation: neutral root, since live is not "golden."
- Char emitter: extend `engines/pdfplumber.py` in place vs a sibling `engines/pdfplumber_chars.py`
  — recommendation: in place, it's the same engine boundary.
