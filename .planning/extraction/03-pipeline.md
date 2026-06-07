# Pipeline layers — the super-engine spec

The super-engine is a sequential, layered pipeline that materialises
the mathematical model of [`01-model.md`](./01-model.md) end-to-end
using the engines surveyed in [`02-engines.md`](./02-engines.md).

## Layered pipeline

```
Input:  pdf_path, page_num

Capa 0 · Normalise coordinates
        pdfplumber.mediabox.lly  →  subtract from every y
        all engines now agree on top-left origin

Capa 1 · ATOMS
        spans      ←  LiteParse v2  (with bold + size + case + digit_ratio)
        rects      ←  pdfplumber    (drop w<50 OR contains 0 spans)
        blocks     ←  Docling       (drop content_layer == furniture)

Capa 2 · CONTAINERS
        parents ← Docling key_value_area / form_area / table  ∪  outer pdfplumber rects
        each parent gets: bbox, child rects, child blocks, child spans

Capa 3 · GEOMETRY GRID per container
        cols   ← pdfplumber vertical_edges  ∨  rect right-edges  ∨  DBSCAN x of values
        rows   ← pdfplumber horizontal_edges ∨  rect top/bottom    ∨  span y-cluster
        merged ← Docling TableCell.col_span / row_span (overrides)

Capa 4 · CELL PROFILE per (row, col)
        for each cell:
          spans     ← LiteParse inside cell
          bold      ← any span bold?  OR Docling Formatting.bold?  (agree → HIGH)
          case      ← _case_class(text)
          digits    ← digit_ratio
          size      ← median font_size
          checkbox  ← Docling checkbox_selected/unselected if present

Capa 5 · CELL ROLE
        for each cell:
          if Docling labels column_header / row_header → use it (HIGH)
          elif bold + lower → LABEL or SUB_HEADER (by container depth)
          elif bold + UPPER → HEADER
          elif starts_with "(" + lower → CLARIFIER
          elif digit_ratio > 0.25 or case in {none, UPPER+numeric} → VALUE_NUMERIC
          elif UPPER → VALUE_TEXT
          elif empty → EMPTY

Capa 6 · COLUMN COHERENCE
        for each column x-band:
          dominant_role = max role across cells in band
          if dominant_role count ≥ 0.8 → promote ("this is the LABEL column")
          else mixed (each cell standalone)

Capa 7 · PAIRING
        priority order (HIGH → LOW confidence):
          1. Docling field_key + field_value adjacent → direct pair
          2. Same row, label-col → value-col (rect-aligned)
          3. Same y-band, lower → UPPER (case-contrast)
          4. Row in multi-col with column_header → emit N pairs
          5. Multi-line wrap: concat consecutive y in same column band

Capa 8 · HIERARCHY
        sections: Docling section_header with heading_level
        attach each pair to its enclosing section by y-range
        when Docling level conflicts with our size-ladder → log + use majority

Capa 9 · CROSS-VALIDATE
        per emitted pair:
          - rect contains span? +
          - Docling label agrees with our role? +
          - font/bold cross-engine? +
        confidence = HIGH if ≥2 of 3 agree
        confidence = LOW  if 1 or 0 agree

Output:  JSON per the schema below
```

## 6-step bottom-up detection logic (table-grid view)

The geometry-grid steps (Capa 2 + Capa 3) decompose into a finer-grained
bottom-up procedure. Each step references the engine that owns it.

```
1. ATOMS:    LiteParse spans
             ├─ size >= 7  → for STRUCTURE detection
             └─ size <  7  → keep for CONTENT only (legal footnotes)

2. COLUMNS:  vertical scaffolding, prefer in this order
             ├─ vertical rules from pdfplumber          (most precise)
             ├─ right-edges of pdfplumber header cells
             ├─ DBSCAN on x-centers of numeric tokens `\b\d[\d.,/\-]*\b`
             └─ x-alignment of bold labels across rows

3. ROWS:     horizontal scaffolding, prefer in this order
             ├─ horizontal rules from pdfplumber        (most precise)
             ├─ top/bottom edges of pdfplumber rects
             ├─ y-clustering of LiteParse spans
             └─ bold→regular transitions (header→body boundary)

4. CONTAINER: parent rect
             ├─ smallest pdfplumber outer rect enclosing the cells
             ├─ Docling 'table' block when no rects exist
             └─ polygon = union(cells) + bold sub-headers + section title

5. TITLE:    bold span attached to container
             ├─ y ∈ [parent.top − 15, parent.top + 5]   (above OR top edge)
             ├─ font_size >= 1.15 × median size inside parent  (when ratio applies)
             ├─ single span, no peers at same y (title vs column-header)
             └─ exclude size < 7 (legal text)

6. VALIDATE: cross-check
             ├─ every pdfplumber cell must contain >=1 LiteParse span,
             │   else it's decorative (skip)
             ├─ LiteParse-inferred cells must align across >=3 rows,
             │   else it's noise (skip)
             └─ Docling matrix = sanity check for rows×cols,
                 disagreement >25% → mark candidate as LOW confidence
```

## ILP precedence rule (global resolver)

```
precision rank:  drawn_rects > docling_matrix > text_inferred

CRITICAL exception:
  If a drawn rect encloses >=2 sub-grids inferred from text/clustering,
  the SUB-GRIDS WIN — the outer rect becomes the container, not a cell.

  This breaks:
    - case 3 (P2 swallows everything: header + body rows + signature box)
    - case 5 (1 parent rect, 3 virtual children)
    - any Docling mega-fusion (single big table absorbing nested grids)
```

The ILP itself is the global pair-resolution program defined in
[`01-model.md` §A.7](./01-model.md#a7-ilp-joint-resolution). This
precedence rule governs the **container detection** step (Capa 2) and
overrides the default "trust the drawn geometry" ordering when nested
sub-grids are evidenced.

## Engines to add to the pipeline

- **E6_TEXT_GRID** — handles table types C, D, parts of B (see
  [`02-engines.md`](./02-engines.md#table-spectrum-the-world-not-this-pdf)).
  Pure LiteParse input (bold-flag + numeric x-cluster + y-cluster). No
  rects required.
- **E7_HEADER_PROJECTION** — handles type B. Detects "header drawn,
  body full-width", projects the header's column boundaries onto each
  body row to emit virtual cells.
- **SECTION_INFER** — handles the parent + title + sub-sections macro
  pattern (cases 4 and 5 in [`04-cases.md`](./04-cases.md)). Emits a
  nested `section → subsections → rows` tree instead of a flat KV list.

---

## Output schema (per page)

```jsonc
{
  "pdf": "...", "page": N, "page_size_pt": [W, H],
  "atoms_summary": {
    "lite_spans": ..., "rects": ..., "docling_blocks": ...,
    "noise_dropped": ...
  },
  "sections": [
    {
      "title": "...",
      "title_signal": {"size":14, "bold":true, "case":"Title",
                       "docling_level":1, "docling_label":"section_header"},
      "title_bbox": {...},
      "container_bbox": {...} | null,
      "bands": [
        {
          "y_range": [y0, y1],
          "layout": "2-col" | "3-col" | "free-text",
          "columns": [
            {"x_range":[x0,x1], "role":"LABEL"|"VALUE_NUMERIC"|...,
             "column_header": "Sin nómina" | null,
             "coherence": 0.95}
          ],
          "rows": [
            {"row_id":"r1", "y_range":[y0,y1],
             "cells":[ {"col":0, "text":"...", "role":"LABEL",
                        "bbox":{...}, "bold":true, "case":"lower",
                        "docling_label":"field_key"|null,
                        "compound_parts":[...]|null} ],
             "clarifiers":["(...)"]}
          ]
        }
      ]
    }
  ],
  "kv_pairs": [
    {"label":"...", "value":"...", "section":"...", "band":"BAND_A",
     "column_header": null, "row_y": ..., "rule": "rect-aligned" |
     "case-contrast" | "header-projection" | "docling-field-pair",
     "confidence": "HIGH" | "MEDIUM" | "LOW",
     "evidence": {
       "rect_id": ..., "docling_block_id": ...,
       "label_span_id": ..., "value_span_ids": [...]
     }}
  ],
  "noise": [
    {"text":"...", "bbox":{...}, "reason":"furniture_layer"|"size<7"|"page_footer"}
  ],
  "diagnostics": {
    "engines": {
      "pdfplumber": {"rects":..., "lines":..., "tables":..., "checkboxes":...},
      "docling":    {"blocks":..., "labels":{...},
                     "section_headers":..., "tables":...,
                     "key_value_regions":..., "field_keys":...,
                     "checkboxes_selected":...},
      "liteparse":  {"spans":..., "bold":..., "cases":{...}}
    },
    "column_coherence": [...],
    "agreement": {
      "section_titles":  {"docling_matches_ours": N, "total": M},
      "cell_bold_flags": {"agree": N, "disagree": M}
    }
  }
}
```
