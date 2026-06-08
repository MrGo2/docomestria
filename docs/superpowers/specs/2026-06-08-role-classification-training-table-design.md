# Role-Classification Training Table — Design

**Date:** 2026-06-08
**Branch:** `feature/structural-extraction`
**Author:** Carlos Lorenzo (brainstormed with Claude)
**Status:** Approved — ready for implementation plan

## Goal

Convert the 15 annotated goldens (66 pages) into a single flat table where **each row
is one atomic text item** carrying its 3-engine feature vector and its **golden role
label**. This is the training data for the next session, where the scoring weights
(`src/docomestria/structural/scoring.py`) are *learned* statistically instead of
hand-tuned.

This session builds the table only. **No model training, no measuring, no production
code changes.**

## Scope

- **In scope:** Problem (A) — **role classification** per item. One row per text item,
  one role label per row.
- **Out of scope (later sessions):** (B) pair scoring (is value V the value of key K?),
  (C) table structure (grouping items into a grid). Both reuse this loader later.

## Unit of a row

**One atomic text item = one row.** A `kv_leaf` produces **two** rows (the key text and
the value text are two distinct positioned items). Each table cell is its own row.

## Label taxonomy (7 roles)

Table cells collapse into the same `key`/`value` roles as standalone KVs — the role is
the same concept regardless of layout; *which* items form a table is structure (problem
C), not role.

| Golden source (in `structure` tree) | Row(s) and role |
|---|---|
| `section` title text | 1 row → `section_header`, then recurse into children |
| `kv_leaf` / `kv_pair` | 2 rows → label = `key`, value = `value` |
| `table` column header cell | `table_header` |
| `table` row-label cell (left column) | `key` |
| `table` data cell | `value` |
| `prose_block` / `free_text_list` items | `prose` |
| `signature_placeholder` | `signature` |
| `noise` | `noise` |

Roles: `section_header, key, value, table_header, prose, signature, noise`.

## Feature vector (columns per row)

**Geometry** (normalised by `page_size_pt`, range 0–1): `x, y, w, h`

**Typography** (liteparse): `font_size`, `font_size_ratio` (font_size ÷ page median
font_size), `is_bold`, `case_class` one-hot → `case_upper, case_lower, case_title,
case_mixed`

**Content** (atoms.spans, joined by `liteparse.span_id`): `digit_ratio, has_currency,
has_date, has_iban, has_nif, has_percent, ends_colon, len_chars, n_numeric_tokens`

**Context** (from leaf evidence): `inside_rect, colon_present, engine_agreement (0–3),
pdfplumber_present, liteparse_present, docling_present, docling_column_header,
docling_row_header`

**Neighbour** (computed per page after sorting items by reading order — y then x):
- `is_centered` — item x-centre within a tolerance of the page x-centre (signals title)
- `gap_above`, `gap_below` — normalised vertical whitespace to the previous/next item
  (a header "breathes")
- `font_ratio_vs_below` — this item's font_size ÷ the item below's (>1 + bold = header)
- `bold_above_nonbold_below` — this item is bold and the item below is not

**Provenance** (for spot-checking, not a feature): `pdf, page, text`

### Why two additions over the handoff's list
- `font_size_ratio` beats raw `font_size`: absolute size says little, "this line is 1.4×
  the page median" is the strong title signal.
- `case_class` one-hot, not ordinal: avoids implying UPPER is "closer" to Title than to
  lower.

## How features are sourced

- Reuse `src/docomestria/golden/engine_data.py` — its loader (pdfplumber chars,
  LiteParse spans, Docling blocks) and its canonical text normalisers `_norm` / `_contains`
  (euro-glyph folding + whitespace-insensitive matching, both fixed this session).
- Read each leaf's `evidence` block (already carries the 3-engine refs for `value` items).
- **Key items** sometimes carry only `label_bbox` (no liteparse font/bold, no engine
  refs). Re-derive their features by locating the span via bbox/text against atoms using
  the `engine_data` matchers.
- Join `atoms.spans` by `liteparse.span_id` to pull the content flags.
- Handle **schema variance** across goldens: some carry `evidence.label`/`evidence.value`,
  others a single `evidence` (the value) plus a separate `label_bbox`. Support both shapes.

## Missing-feature policy

If a given engine did not find an item, set its `*_present` flag to 0 and leave its
numeric features empty (NaN in CSV). The present-flags already encode missingness — no
imputation at this stage.

## Output

- **Format:** CSV — at this size (~few thousand rows) Parquet is premature optimisation;
  CSV is eyeball-inspectable, `git diff`-friendly, and pandas-readable.
- **Path:** `.planning/extraction/training/role_table.csv` (annotation world, beside
  goldens and atoms).
- Deterministic and re-runnable: same goldens in → byte-identical CSV out (stable row
  ordering by pdf, page, reading order).

## Runtime / dependencies

- Plain Python. `csv` (stdlib) + reuse of `engine_data.py`. pandas optional, only for the
  class histogram. **No** scikit-learn / numpy / torch — that is the next (training)
  session.
- **No agents at runtime.** The engines already ran; their output is frozen in the atoms.
  The builder is deterministic code, runs in seconds over 66 pages.

## Tests (TDD)

A small fixtured test: one golden node (e.g. a `kv_leaf`) → its expected row(s). Lock the
walk + feature extraction before running over the full corpus. Include a `key`-only-
`label_bbox` fixture to lock the re-derivation path.

## Definition of done

A script `scripts/build_training_table.py` that:
1. Walks all 15 goldens' `structure` trees, joining atoms features.
2. Emits one row per atomic text item: `[3-engine feature vector] → [role label]`.
3. Writes `.planning/extraction/training/role_table.csv`.
4. Prints the class histogram (count per role).
5. Is re-runnable and deterministic.

**Verification:** row count ≈ sum of labelled items across 66 pages; class histogram
printed; spot-check 3 rows against the rendered PDF page in the viewer
(`PYTHONPATH=src python3 scripts/view_goldens.py --port 8772`).
