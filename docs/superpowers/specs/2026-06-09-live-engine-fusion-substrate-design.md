# Job A — Production Live-Feature Pipeline & Retrain (v3)

**Date:** 2026-06-09
**Branch:** `feature/structural-extraction`
**Status:** Design — pending review
**Supersedes** the v1/v2 "fusion substrate" framing (see *Reframe* below). Filename kept
for git continuity; the project is now the live-feature pipeline + retrain.

## Purpose

Build the **live feature pipeline** that computes role-classification features for
production PDFs directly from the three engines, **retrain** the role classifier on those
live-computable features (labeled from the golden annotations), and validate it with the
model's own cross-validation. The output is a role classifier trained on **exactly the
features production computes** — ready to wire into the live extractor (separate follow-on).

## Reframe — why v3 differs from v1/v2

v1/v2 tried to reproduce the offline *golden* features live so the **existing** 0.88 model
would run unchanged. Two Codex reviews showed the golden feature construction is deeply
coupled to the atoms/annotation world and even encodes **quirks the model relies on** — e.g.
`colon_present` is `1` even when no colon exists (286/381 golden cases;
`golden/cell_linker.py:81` emits `{present: False}`, but `signal_features`
`golden/training_table.py:114` counts any dict as present). Faithfully reproducing that —
bugs included — is intricate and wrong-headed.

**Decision (user-approved): don't match golden. Build clean live features, retrain on them,
measure honestly.** The production model *should* train on what production computes, not on
golden-only artifacts.

## Scope

### In scope
1. **Live char emitter** — `engines/pdfplumber.py`: per-page chars/words with bboxes. The
   pdfplumber engine currently exposes only `extract_visual_rects`; char/word output is
   needed for a real colon flag, per-item pdfplumber presence, and char-bbox geometry.
2. **Live feature builder** — per-item features for a live PDF from `{liteparse spans,
   docling blocks, visual rects, chars}`. Same feature **schema** as the current model
   where live-computable; **drop** features that can't be computed live **and** have ~0
   importance (`docling_column_header`/`row_header` = 0.0 importance in the model report).
   Reuse `fusion.py` geometric helpers (`_best_docling_block`, `_smallest_containing_rect`,
   `_find_cell`) and pure golden helpers by import; pull `docling_content_layer` /
   `rect_type` directly from the raw `DoclingBlock`/`VisualRect` (not via the lossy
   `FusedItem`). `is_bold` from `font_name` (reuse `classify.is_bold`); `case_class` from
   text; **`colon_present` = a real colon test** (fixing the golden quirk).
3. **Label transfer** — attach golden truth roles to live items. LiteParse is deterministic
   for a given PDF, so a live span maps to its golden role by span identity, with a
   normalized-text + bbox-overlap ≥ 0.30 fallback (reuse `_overlap_frac`
   `training_table.py:122`, `_norm` `engine_data.py:25`). Track and report **coverage**
   (aligned share, per role and per page).
4. **Retrain + evaluate** — run `evaluate_oof(df)` (GroupKFold-by-pdf — the exact protocol
   that produced 0.88, `role_classifier.py:67`) on the live-feature table → pooled-OOF
   macro-F1 + per-role. Fit the final model on all rows for the artifact.

### Out of scope (follow-on "A-wiring")
- Production model loader under `src/`; replacing `classify()` with model inference.
- 7→5 role-vocabulary mapping (`signature`/`table_header` have no `ItemKind`);
  `candidates.py` changes.
- Regression-benchmark (5-PDF Azure DI + ParseBench) before/after.

## Architecture

```
src/docomestria/
├── engines/pdfplumber.py   (CHANGE — add char/word extraction)
├── fusion.py               (REUSE helpers — geometric matching; untouched)
├── live_features.py        (NEW — build_live_feature_table(engine outputs) → rows)
├── golden/training_table.py(REUSE pure helpers by import; NOT modified)
└── training/role_classifier.py (REUSE — evaluate_oof + fit_final_model)
scripts/
└── build_live_feature_table.py / train_live_role_classifier.py  (NEW — gate + artifact)
```

The golden builder is **not modified** (no byte-parity guard needed). We import its pure,
already-reusable helpers; we do not fork or rewrite them.

### Data flow
```
PDF → engines: liteparse spans + docling blocks + visual rects + NEW chars
    → live_features.build(...)              → per-item live features            (NEW)
    → label transfer (golden roles)         → labeled live-feature table        (NEW)
    → evaluate_oof (GroupKFold)             → pooled-OOF macro-F1 + per-role     (gate)
    → fit_final_model(all rows)            → production-ready model artifact
```

## Acceptance gate (definition of done)

1. Build the live-feature table for the golden PDFs and transfer golden roles.
2. **Coverage floor** (guards against a biased subset): ≥ 90% of golden labeled items
   align overall, and ≥ 70% per role. Below floor → gate **FAILS** (the score would be on
   an unrepresentative subset), independent of macro-F1.
3. `evaluate_oof` pooled macro-F1 **≥ 0.85**, and **every role F1 > 0.5** (all usable).
4. Report: per-role F1, coverage table, and feature-importance readout (to confirm live
   features carry the signal — and that no alignment artifact leaks).

The model fit on all aligned rows is the deliverable artifact for A-wiring.

## Risks

1. **Live feature quality < golden → lower macro-F1.** Char-bbox geometry, a corrected
   colon flag, and live engine pairing may yield a weaker (or simply different) model.
   `evaluate_oof` measures this directly and honestly; the importance/coverage report
   localizes any weak feature. If < 0.85, we fix the emitter/feature, not the metric.
2. **Alignment coverage.** Too few live items matching golden labels shrinks/biases the
   training set. The coverage floor in the gate guards this explicitly.
3. **Engine availability at inference.** Some pages may lack a Docling block or pdfplumber
   chars; features must degrade gracefully via the `*_present` flags (the model already
   trained across varied presence).

## Testing
- **Unit:** char emitter (fixtured page → chars/words+bbox); live feature builder
  (fixtured engine outputs → expected feature row, incl. item-in-cell, over-signature-rect,
  missing-engine); label-transfer matcher (live span ↔ golden role, incl. no-match).
- **Integration:** the gate — live table → `evaluate_oof` ≥ 0.85 + coverage floor met.

## Open questions for review
- Acceptance: 0.85 macro-F1 + per-role > 0.5 — right bar, or 0.86?
- Coverage floor: 90% overall / 70% per role — sensible, or tune?
- Reuse golden helpers by import vs copy — recommendation: import the pure ones
  (`_overlap_frac`, `_norm`, `signal_features` sub-helpers, `is_bold`); don't fork.
