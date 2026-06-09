# Job A — Role Classifier: Design Spec

**Date:** 2026-06-09
**Branch:** `feature/structural-extraction`
**Status:** Approved design, pending Codex review → implementation plan

---

## 1. Context & Goal

We are building a **fusion / reconciliation engine**: a model that takes the raw signals of
all three engines (pdfplumber + Docling + LiteParse) — geometry, typography, content, and
cross-engine agreement — and identifies document structure better than any single engine.

That engine is built as **three separate learned jobs**, not one:

| Job | Question | Status |
|---|---|---|
| **A — Role ID** | What *is* this text item? `section_header / key / value / table_header / prose / signature / noise` | **This spec** |
| B — Pairing | Is *this* value the value of *that* key? | Later (consumes A) |
| C — Table structure | How do these cells form a grid? | Later (consumes A) |

**Hard dependency:** B and C both consume A's role labels, so A is foundational and built
first. B and C are independent of each other and may run in parallel worktrees once A lands.
A joint structured model was considered and rejected — too data-hungry, not interpretable,
undebuggable at our corpus size (~4.7K rows, 7 classes).

**This spec covers Job A only.** Goal: a model that labels each text item with one of 7
roles using fused tri-engine features, and **beats raw Docling-label-alone**.

### Production target (not this session's scope)
The eventual home for the trained model is `src/docomestria/structural/classify.py` (item
typing), **not** `scoring.py` — `scoring.py` scores KV-pair candidates per emitter and has no
per-role weight slot. This session produces the trained model + report as a research artifact;
wiring it into `classify.py` is Job-A phase 2.

---

## 2. Scope

**In scope**
- Enrich the training table with the high-value Docling/rect feature bundle (Section 4).
- Train a role classifier from `role_table.csv` (Section 5).
- Produce a leakage-free evaluation report + persisted model (Section 6).
- Keep the whole chain one-command and re-runnable (Section 8).

**Out of scope**
- Job B (pairing) and Job C (table structure).
- Wiring the model into `classify.py` (Job-A phase 2).
- Re-running any engine / re-extraction — all engine output is already cached on disk.
- The remaining lower-value dropped signals (edge density, value_extent boundary,
  fill colors) — deferred to a later iteration, added only if the confusion matrix demands.

---

## 3. The Data

- **File:** `.planning/extraction/training/role_table.csv` — 4 668 rows × 45 cols, built
  deterministically by `python3 scripts/build_training_table.py` from 46 golden pages.
- **Label column:** `role` ∈ {`section_header`, `key`, `value`, `table_header`, `prose`,
  `signature`, `noise`}.
- **Class histogram (imbalanced):** noise 2296 (49%), key 908, value 907, section_header 214,
  prose 173, table_header 139, signature 31.
- **Provenance columns — EXCLUDED from features** (leak the answer or aren't real signals):
  `pdf, page, text, node_path, source_node_type, in_table, table_id, row_idx, col_id`.
  `pdf` is retained as the **grouping key** for the train/test split (Section 5).
- **Current feature columns (X):** geometry `x,y,w,h`; typography `font_size,
  font_size_ratio, is_bold, case_upper/lower/title/mixed`; content `digit_ratio, has_currency/
  date/iban/nif/percent, ends_colon, len_chars, n_numeric_tokens`; context `inside_rect,
  colon_present, engine_agreement, pdfplumber/liteparse/docling_present,
  docling_column/row_header, compound_span`; neighbour `is_centered, gap_above, gap_below,
  font_ratio_vs_below, bold_above_nonbold_below`.
- **Missing values:** empty string `""` (read as NaN). ~56 keys have no typography
  (`liteparse_present=0`); many rows have empty neighbour/font features. The model must
  tolerate NaN (Section 5 model choice does, natively).

---

## 4. Step 1 — Feature Enrichment (before training)

**Rationale:** the single most predictive signal — Docling's per-block layout label — is
currently dropped by the builder. Training without it produces a weak model we'd have to
redo. We enrich first.

**Key fact (verified):** all the new signals are **already persisted on disk** in
`.planning/extraction/atoms/*.atoms.json` at `atoms.blocks[].*`. No engine re-run. Verified
across 69 files / 2903 Docling blocks:
- `label` populated on every block — `text` 1991, `list_item` 209, `section_header` 192,
  `picture` 153, `checkbox_unselected` 111, `page_header` 91, `page_footer` 75,
  `checkbox_selected` 44, `footnote` 16, `table` 15, `caption` 6.
- `heading_level` on 192 blocks (the section_headers); `content_layer` on all 2903.
- Block fields: `label, content_layer, bbox, text, formatting, heading_level, self_ref, cells`.

### Features to add
Capture each via a **bbox join** — match every item to its enclosing Docling block using the
existing helper `find_enclosing_docling_block` (`src/docomestria/structural/engine_data.py`).
No new extraction.

| New column | Source | Encoding | Why |
|---|---|---|---|
| `docling_label` | `block.label` | categorical (one-hot or ordinal) | Near-twin of the target — `page_footer`→noise, `section_header`→section_header, `list_item`/`text`→prose |
| `docling_heading_level` | `block.heading_level` | integer, NaN if absent | Separates headers + encodes hierarchy depth |
| `docling_content_layer` | `block.content_layer` | categorical (body/furniture) | `furniture` = headers/footers/marginalia → noise |
| `rect_is_signature_field` | pdfplumber rect classification (`engines/pdfplumber.py`) | boolean | Tall-thin bottom-of-page rect ≈ direct `signature` oracle |

### Silent-zero bug to fix (same pass)
`docling_column_header` / `docling_row_header` are currently **forced to 0** for re-derived
and noise rows (in `training_table.py` `rederive_signal` / `noise_items`), so those existing
features are partly garbage. Fix: attempt the real enclosing-cell Docling lookup on those
paths instead of hardcoding 0.

### Determinism
Enrichment reads only cached atoms + the existing golden signals. `build_training_table.py`
stays deterministic and re-runnable; re-running regenerates an enriched `role_table.csv`
with the same command and no engine calls.

---

## 5. Step 2 — Training

### Model
**`sklearn.ensemble.HistGradientBoostingClassifier`.**
- Handles NaN **natively** — no imputation of our `""` gaps; the `*_present` flags stay
  meaningful.
- Captures **interactions** (bold AND uppercase AND top-of-page — the combination, which a
  linear model can't without hand-crafted terms).
- Yields **feature importances** (permutation importance) to steer the next enrichment round.
- Zero extra dependencies; fast at this corpus size.

Linear/logistic regression was rejected: the "portable readable weights" argument died once
we agreed the model ships into `classify.py` as a model object, not into `scoring.py`
constants. (A logistic baseline may be added later purely for a directional-story readout if
desired — not in the first run.)

### Baseline to beat
**Raw Docling-label → role majority map.** Compute, on the training folds, the most-common
`role` for each `docling_label` value; predict that on the test fold. This is the "just copy
Docling" baseline. If the fused model can't beat its macro-F1, the fusion adds nothing — and
we will have *learned* that. This also neutralizes the leakage worry around using
`docling_label` as a feature (Section 7).

### Train/test split
**`sklearn.model_selection.GroupKFold(n_splits=5)`, grouped by `pdf`.** Never a random row
split: rows on the same page share neighbour and page-median-derived features
(`gap_above`, `font_size_ratio`, …), so a row split leaks page context into the test set and
inflates the score. Grouping by `pdf` guarantees a page's rows never straddle the split.
Report cross-validation mean ± std across folds.

### Class imbalance
noise ≈ 49%; signature only 31 samples. Use `class_weight="balanced"` (sample weights) so
minority roles aren't drowned. Signature recall is expected to be weak (31 samples) — we
report it honestly rather than hide it; improving it is a later-iteration concern.

---

## 6. Step 3 — Report (definition of "done")

A re-runnable `scripts/train_role_classifier.py` that produces:

1. **Per-class precision / recall / F1 / support** — for all 7 roles.
2. **Macro-F1** — the headline number (equal weight to all roles).
3. **Confusion matrix** — to see *what* confuses with what (expected: key↔value,
   section_header↔table_header). Drives the next enrichment round.
4. **vs-Docling-baseline delta** — model macro-F1 minus baseline macro-F1. The justification
   number for the whole fusion approach.
5. **Permutation feature importances** — ranked, to target the next features.

**Banned:** reporting raw accuracy as a headline — misleading at 49% noise (an all-noise
predictor scores 49%).

### Artifacts (output location)
Under `.planning/extraction/training/`:
- `role_model.pkl` — persisted fitted model (refit on all data after CV reporting).
- `role_model_report.md` (+ `.json`) — the metrics above, human- and machine-readable.
- `role_model_confusion.csv` — confusion matrix.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **Leakage from `docling_label`** ("model just copies Docling") | Correcting Docling using the other engines is the *point*. Measured via the beat-Docling baseline (Section 5) — if the model can't beat copy-Docling, we learn the fusion is worthless. |
| **Circularity** (goldens labelled by copying Docling) | Goldens went through human review (golden-reviewer / spec-patcher). The baseline delta also exposes any residual tautology. |
| **Feature noise** (a wrong Docling label) | Safe: a tree gives a useless feature ~0 importance, and *learns to correct* a systematically-wrong one using the other features. Worst case is harmless. |
| **Label noise** (a mis-tagged `role`) | The real danger — corrupts ground truth. Defended by the golden review pipeline; handoff measured label leakage at 2.2% (labels sound). The 46→66 re-scaffold further improves this. |
| **Row-split leakage** | GroupKFold by `pdf` (Section 5). |
| **Signature underfit** (31 samples) | Reported honestly; `class_weight="balanced"`; deferred improvement. |

---

## 8. Re-runnability

The full chain stays one command each:
```
PYTHONPATH=src python3 scripts/build_training_table.py        # → enriched role_table.csv
PYTHONPATH=src python3 scripts/train_role_classifier.py       # → model + report
```
When the **46→66-page golden re-scaffold** lands (separate worktree `docomestria-rescaffold`),
retrain by re-running both. No code changes required.

---

## 9. Future (out of this spec)

- **Job-A phase 2:** wire `role_model.pkl` into `src/docomestria/structural/classify.py`.
- **Job B (pairing)** and **Job C (table structure)** — own training tables, own models,
  parallel worktrees, each consuming A's role labels.
- Lower-value dropped signals (edge density, value_extent boundary type, fill colors) — added
  only if the confusion matrix shows the model needs them.

---

## 10. Verification

Done when:
- `build_training_table.py` emits `role_table.csv` with the 4 new feature columns populated
  (non-trivial coverage, not all-NaN) and the docling-header silent-zero bug fixed.
- `train_role_classifier.py` runs end-to-end and writes the three artifacts.
- The report shows per-class P/R/F1, macro-F1, confusion matrix, feature importances, and a
  **positive vs-Docling-baseline delta** (or, if negative, that result is surfaced, not hidden).
- Both scripts are deterministic and re-runnable from a clean checkout.
