# Anti-patterns — what NOT to do

Consolidated from the design discussions and the eight cases in
[`04-cases.md`](./04-cases.md). Consult before introducing any new
heuristic.

## Engine-level anti-patterns

- **Do not hard-code "banking" or doc-type-family rules at the engine
  level.** Document-family specifics belong in `doctype`
  post-processing, not in structure detection.
- **Do not trust a single engine's verdict without cross-validation.**
  Every emitted structural decision must reference at least two of
  pdfplumber / Docling / LiteParse — see Capa 9 in
  [`03-pipeline.md`](./03-pipeline.md#layered-pipeline).
- **Do not filter rects on absolute size thresholds** (`h>20`)
  instead of relative-to-text-median or "contains a LiteParse span".
  Cases 1 and 2 in [`04-cases.md`](./04-cases.md#case-1--rect-height-filter-too-aggressive-banking_1414-p1)
  are direct evidence.
- **Do not treat Docling's matrix as authoritative on column/row
  counts.** It fuses aggressively; cases 1, 3 and 4 demonstrate.
- **Do not detect titles by font-size ratio alone.** Case 5b has equal
  size for title and sub-headers; position is the decisive signal in
  that case.

## Pair-emission anti-patterns

- **Do not emit KV across different `font_size`.** That is typically a
  header → content relation, not a pair.
- **Do not emit KV inside a paragraph.** The BBVA-description block at
  y=415-440 on page 2 is 3 lines of lower-case body text with no
  contrast and must not generate spurious pairs. Use the
  `paragraph_break_between` penalty of
  [`01-model.md` §A.3](./01-model.md#per-edge-weight-functions).
- **Do not assume one label maps to one value.** Multi-column bands
  (case 7 pattern 1) emit one pair per column with a `column_index`
  tag.

## Reading-order anti-patterns

- **Do not flatten Docling output and discard `content_layer`.**
  `furniture` must be dropped at ingest, not after structure detection
  — see [`02-engines.md` §B.2](./02-engines.md#b2-contentlayer--5-layers-we-use-2).
- **Do not collapse `TableCell` into `tuple[tuple[str]]`.** Every
  per-cell flag listed in [`02-engines.md` §B.4](./02-engines.md#b4-what-docling-actually-exposes-per-table-cell-we-throw-most-away)
  is lost.

## Container-detection anti-patterns

- **Do not let an outer rect absorb the nested sub-grids it
  contains.** When ≥2 text-inferred sub-grids fit inside a drawn rect,
  the sub-grids win and the rect becomes a container, not a leaf cell.
  This is the ILP precedence exception documented in
  [`03-pipeline.md`](./03-pipeline.md#ilp-precedence-rule-global-resolver).
- **Do not use `find_tables()` greedy output without sanity checks.**
  pdfplumber regularly produces one huge table per region that fuses
  unrelated sub-tables.

## Calibration anti-patterns

- **Do not jump to deep learning before reaching ≥200 labelled
  pairs.** Logistic regression over the heuristic feature vectors
  outperforms small neural models in this volume range — see
  [`01-model.md` §A.9](./01-model.md#a9-calibration-of-weights).
- **Do not tune weights against a single PDF.** The five-PDF Azure DI
  benchmark (LABORAL, PATRIMONIAL, BBVA 3/4/5) is the minimum
  regression set.

## Documentation anti-patterns

- **Do not split a finding into incremental notes spread across
  multiple files.** Group related symptoms in a single case in
  [`04-cases.md`](./04-cases.md) so the design implication is visible.
- **Do not skip the visual debugger.** Hypotheses about overlap,
  alignment, and bbox containment must be verified visually before
  they become code. The debugger at `scripts/view_boxes_p1.py`
  (port 8770) is the contract surface.
