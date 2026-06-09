# Roadmap to build the super-engine

Six steps from current state to fully-integrated CRF + ILP pipeline.

## 1. Lift the Docling wrapper (`engines/docling.py`)

- Emit `key_value_region`, `field_key`, `field_value`, `checkbox_*`
  as their own block kinds.
- Keep `TableCell` rich (don't flatten to `tuple[str]`). Preserve
  `col_span`, `row_span`, `column_header`, `row_header`, `row_section`,
  `fillable` — see [`02-engines.md` §B.4](./02-engines.md#b4-what-docling-actually-exposes-per-table-cell-we-throw-most-away).
- Expose `furniture` layer separately so callers can drop it
  unconditionally.
- Expose `Formatting.bold` per text item for the cross-engine agreement
  signal in Capa 9.

## 2. Lift the LiteParse wrapper (`engines/liteparse.py`)

- Add `case_class`, `digit_ratio`, `is_bold` flags computed once at
  span ingestion.
- Hoist the derived flags currently sitting in
  `scripts/view_boxes_p1.py` (`case_class`) into `LiteItem` so every
  consumer sees the same values.
- Optionally surface `is_italic`, `font_family`, `weight_class` from a
  font-name dictionary.

## 3. Add pdfplumber side-outputs

- Return `lines`, `horizontal_edges`, `vertical_edges`, `images`
  alongside the existing `rects` / `find_tables` outputs.
- Apply the mediabox offset (`mediabox.lly` subtraction) at the wrapper
  layer so every downstream consumer sees a top-left origin —
  [`03-pipeline.md` Capa 0](./03-pipeline.md#layered-pipeline).
- Surface `char.non_stroking_color` for highlighted-cell detection.

## 4. Build the super-engine module (`structural/super_engine.py`)

- Implement Capa 0 → Capa 9 sequentially per
  [`03-pipeline.md`](./03-pipeline.md).
- Each layer is a **pure function with explicit inputs/outputs** —
  enables unit testing and snapshot diffing.
- Score role assignment and pairs with the templates of
  [`01-model.md` §A.4](./01-model.md#a4-role-classification-as-weighted-templates)
  and [§A.6](./01-model.md#a6-pair-scoring).
- Resolve the global pair assignment with the ILP of
  [§A.7](./01-model.md#a7-ilp-joint-resolution) using `pulp` + CBC.
- Emit the JSON schema of
  [`03-pipeline.md`](./03-pipeline.md#output-schema-per-page) per page.

## 5. Validation set

- Snapshot the per-page JSON for **page 2 and page 3 of `BBVA_0608`**
  plus the **five cases on `banking_1414` page 1** as ground truth.
- Each snapshot becomes a fixture; tests assert that the super-engine
  emits an equivalent structure.
- Extend with new fixtures whenever a new failure mode is documented in
  [`04-cases.md`](./04-cases.md).

## 6. Diff harness

- Any code change must re-emit the per-page JSON and compare against
  the ground truth.
- Deviations require human review — surfaced via the visual debugger
  at `scripts/view_boxes_p1.py` (port 8770).
- Tie the harness into CI so structural regressions break the build
  before they reach production.
