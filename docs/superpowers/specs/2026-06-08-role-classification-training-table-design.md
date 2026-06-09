# Role-Classification Training Table — Design

**Date:** 2026-06-08 (revised 2026-06-09 after Codex review)
**Branch:** `feature/structural-extraction`
**Author:** Carlos Lorenzo (brainstormed with Claude, reviewed by Codex)
**Status:** Approved — ready for implementation plan

## Goal

Convert the annotated goldens into a single flat table where **each row is one atomic
text item** carrying its 3-engine feature vector and its **golden role label**. This is
the training data for the next session, where the scoring weights
(`src/docomestria/structural/scoring.py`) are *learned* statistically instead of
hand-tuned.

This session builds the table only. **No model training, no measuring, no production
code changes.**

## Scope

- **In scope:** Problem (A) — **role classification** per item. One row per text item,
  one role label per row.
- **Out of scope (later sessions):** (B) pair scoring (is value V the value of key K?),
  (C) table structure (grouping items into a grid). Both reuse this loader later.

## Corpus contract

The goldens are **page-level JSONs** (one file per PDF page), not one file per document.
- Source glob: `.planning/extraction/golden/*.json` (15 documents → **66 page files**).
- The builder asserts the resolved file count and prints it; it **fails loudly** if the
  count is unexpectedly low (guards against a silently-empty glob).
- Each golden page-file has a sibling atoms file at
  `.planning/extraction/atoms/<stem>-p<NN>.atoms.json`.
- **Legacy format:** ~20 of the 66 page-files predate the `structure` tree and carry only
  top-level `sections`/`kv_pairs` (which lack per-engine evidence). These are **skipped
  with a loud report** this round — they cannot supply the feature vector — leaving ~46
  structure-format pages. Re-scaffolding the legacy pages is a follow-up. A structure-format
  golden missing its atoms file is a **hard error** (abort before writing), not a skip.

## Unit of a row

**One atomic text item = one row.** A KV pair produces **two** rows (the key text and the
value text are two distinct positioned items). Each table cell is its own row.

**Plus unannotated atoms → `noise`.** Every `atoms.spans` item on a page that does **not**
match any annotated golden item becomes a `noise` row. Rationale: at inference the
extractor sees *every* text span, including junk; if the `noise` class only contains
explicitly-annotated noise, the classifier never learns to reject the unannotated
background. An atom counts as "matched" if it is the source span of an emitted golden
item (matched by `liteparse.span_id` when present, else by bbox-overlap + `_contains`
text match). Unmatched-atom count is printed for sanity.

## Label taxonomy (7 roles)

Table cells collapse into the same `key`/`value` roles as standalone KVs — the role is
the same concept regardless of layout; *which* items form a table is structure (problem
C), not role. The `in_table` provenance column preserves that signal without splitting
the role set.

| Golden source (in `structure` tree) | Row(s) and role |
|---|---|
| `section` title text | 1 row → `section_header`, then recurse into children |
| `kv_group` | recurse into its `pairs` (no row for the group itself) |
| `kv_leaf` / `kv_pair` (and `kv_group.pairs[]`) | 2 rows → label = `key`, value = `value` |
| `table.title` | `section_header` (it titles the block) |
| `table` `columns[].label` / header cell | `table_header` |
| `table` row-label cell (left column) | `key` |
| `table` data cell | `value` |
| `prose_block` / `free_text_list` items | `prose` |
| `signature_placeholder` | `signature` |
| `noise` node **and** unmatched atoms | `noise` |

Roles: `section_header, key, value, table_header, prose, signature, noise`.

An item whose evidence resolves to an **unknown node/evidence shape** is **not silently
dropped** — the builder fails loudly listing the offending shape (see Schema variance).

## Feature vector (columns per row)

**Geometry** (normalised by `page_size_pt`, range 0–1): `x, y, w, h`

**Typography** (liteparse span): `font_size`, `font_size_ratio` (font_size ÷ page median
font_size over resolved-font items; if this item has no liteparse font, leave ratio
empty), `is_bold`, `case_class` one-hot → `case_upper, case_lower, case_title,
case_mixed` (normalise raw atom values UPPER/lower/Title/mixed/etc. to these four; an
unrecognised value sets all four to 0 and is counted).

**Content** — computed from the **item's own `text`**, not the joined span (a fused span
that carries both key and value must not give both rows the same content flags):
`digit_ratio, has_currency, has_date, has_iban, has_nif, has_percent, ends_colon,
len_chars, n_numeric_tokens`. The atoms content flags are still used as the
implementation reference, but recomputed per item text.

**Context** (from leaf evidence): `inside_rect, colon_present, engine_agreement (0–3),
pdfplumber_present, liteparse_present, docling_present, docling_column_header,
docling_row_header`, `compound_span` (1 when this item's key and value share a single
liteparse span_id — flags that font/bold are shared, not item-specific).

**Neighbour** (computed per page after sorting items by reading order):
- `is_centered` — item x-centre within a tolerance of the page x-centre (signals title)
- `gap_above`, `gap_below` — normalised vertical whitespace to the previous/next item
- `font_ratio_vs_below` — this item's font_size ÷ the item below's (>1 + bold = header)
- `bold_above_nonbold_below` — this item is bold and the item below is not

**Provenance** (not features; for spot-checking and later problems B/C): `pdf, page, text,
node_path, source_node_type, in_table, table_id, row_idx, col_id`.

### Why two additions over the original handoff list
- `font_size_ratio` beats raw `font_size`: absolute size says little; "1.4× the page
  median" is the strong title signal.
- `case_class` one-hot, not ordinal: avoids implying UPPER is "closer" to Title than to
  lower.

## How features are sourced

- Reuse `src/docomestria/golden/engine_data.py` — its loader (pdfplumber chars,
  LiteParse spans, Docling blocks) and its canonical text normalisers `_norm` / `_contains`
  (euro-glyph folding + whitespace-insensitive matching, both fixed in a prior session,
  SHAs `879da4f`, `f9d5a84`).
- Read each leaf's `evidence` block (already carries the 3-engine refs for `value` items).
- **Fused spans:** when a KV pair's key and value resolve to the **same** liteparse
  `span_id`, set `compound_span=1`, take font/bold from the shared span (legitimate —
  same span, same font), but compute all content features from each item's own text.
- **Key items** sometimes carry only `label_bbox` (no liteparse font/bold, no engine
  refs). Re-derive their features by locating the span via the `engine_data` matchers,
  but **fail-closed**: require bbox overlap with the item's geometry within an x/y
  tolerance, detect ambiguity (multiple candidate spans), and count + print unresolved
  keys rather than binding the wrong span.
- Join `atoms.spans` by `liteparse.span_id` for the reference content flags.
- **Schema variance — adapter matrix.** Real evidence shapes observed include:
  `evidence.{label,value}`, a single `evidence` (the value) + separate `label_bbox`,
  `evidence.path`, and `*_signal` variants (`text_signal`, `label_signal`,
  `title_signal`, `container_signal`). Implement an explicit adapter per known shape; an
  unrecognised shape is a **hard error** (lists the shape), never a silent skip.

## Missing-feature / CSV policy

- If an engine did not find an item, set its `*_present` flag to 0 and leave its numeric
  features as the empty string `""` (read back as NaN). The present-flags encode
  missingness — no imputation at this stage.
- **Byte-identical output policy:** fixed column order (declared once), bools encoded as
  `0`/`1`, floats at fixed precision (e.g. 4 decimals), `\n` newline dialect, empty
  string `""` as the only missing sentinel. Same goldens in → byte-identical CSV out.
- **Deterministic row order:** sort by `pdf, page, node_path, row_idx, col_id, y, x`
  (the `node_path` and table indices break ties that bare `y,x` cannot — multi-column
  pages, same-line KV splits, table cells).

## Output

- **Format:** CSV — at this size (~few thousand rows) Parquet is premature optimisation;
  CSV is eyeball-inspectable, `git diff`-friendly, pandas-readable.
- **Path:** `.planning/extraction/training/role_table.csv` (annotation world, beside
  goldens and atoms). Write to a sibling temp path and atomically rename on success so a
  mid-run failure never leaves a partial CSV.

## Runtime / dependencies

- Plain Python. `csv` (stdlib) + reuse of `engine_data.py`. pandas optional, only for the
  class histogram. **No** scikit-learn / numpy / torch — that is the next (training)
  session.
- **No agents at runtime.** The engines already ran; their output is frozen in the atoms.
  The builder is deterministic code, runs in seconds over 66 pages.

## Tests (TDD)

Small fixtured tests, each a golden node → its expected row(s). Lock before running the
full corpus. Cover at minimum:
- a `kv_leaf` → 2 rows (key, value);
- a **fused-span** KV → `compound_span=1` with *different* content features per row;
- a `key`-only-`label_bbox` item → re-derivation resolves (and an ambiguous one → counted
  unresolved, not mis-bound);
- a `kv_group` with `pairs` → all pairs emitted;
- an unmatched atom → a `noise` row;
- an unknown evidence shape → hard error.

## Definition of done

A script `scripts/build_training_table.py` that:
1. Walks all 66 golden page-files' `structure` trees, joining atoms features, and emits
   `noise` rows for unmatched atoms.
2. Emits one row per atomic text item: `[3-engine feature vector] → [role label]`.
3. Writes `.planning/extraction/training/role_table.csv` (atomic rename).
4. Prints the class histogram (count per role), the unmatched-atom count, and the
   unresolved-key count.
5. Is re-runnable and byte-identical-deterministic.

**Verification:** row count ≈ (annotated items + unmatched atoms) across 66 pages; class
histogram printed; spot-check 3 rows against the rendered PDF page in the viewer
(`PYTHONPATH=src python3 scripts/view_goldens.py --port 8772`).
