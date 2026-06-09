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
   docling blocks, visual rects, chars}`. **Keep the full feature schema** — `evaluate_oof`
   indexes a fixed column set derived from `training_table.FIELDS`
   (`role_classifier.py:31,83`), so columns cannot be dropped or it `KeyError`s. For the
   two live-uncomputable, **0.0-importance** columns (`docling_column_header`/`row_header`)
   emit a constant `0` rather than dropping them. Reuse `fusion.py` geometric helpers
   (`_best_docling_block`, `_smallest_containing_rect`, `_find_cell`) — note their hidden
   precondition: rects must be **sorted by area first** so "smallest containing rect" holds
   (`fusion.py:129`). Pull `docling_content_layer` / `rect_type` directly from the raw
   `DoclingBlock`/`VisualRect` (not via the lossy `FusedItem`). `is_bold` from `font_name`
   (reuse `classify.is_bold`); `case_class` from text; **`colon_present` = a real colon
   test** (fixing the golden quirk).
3. **Label transfer** — attach golden roles to live items, reproducing the **current golden
   role-table semantics, including atom-noise generation**. Two label sources, mirroring the
   golden builder:
   - *Annotated roles* (key/value/section_header/table_header/signature/prose): match each
     live item to a golden annotated item by **normalized-text + bbox-overlap ≥ 0.30**
     (reuse `_overlap_frac` `training_table.py:122`, `_norm` `engine_data.py:25`). This
     overlap match is the **primary** disambiguator — `span_id` is NOT a unique key (it is
     a LiteParse list index shared across key/value/header splits; 202 page/spans map to
     multiple roles, hence `compound_span`), so it is at most a weak hint.
   - *Noise* (the largest class, 2117/2296 from atoms): live items that match **no** golden
     annotated item become `noise` — exactly as `noise_items` (`training_table.py:381`)
     labels unconsumed atoms today. So every live item is labeled (a real role or noise);
     there is no silently-dropped bucket.
   Track and report **coverage of the annotated (non-noise) roles** — the failure mode is a
   real key/value drifting out of overlap and being mislabeled `noise`.
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

1. Build the live-feature table for the golden PDFs and transfer golden roles (annotated
   roles by overlap match; unmatched → noise, per the label policy above).
2. **Coverage floor** (guards against real roles being mislabeled `noise`): ≥ 90% of golden
   **annotated** (non-noise) items align overall, and ≥ 70% per annotated role. Below floor
   → gate **FAILS** independent of macro-F1 (the label set has silently drifted).
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
