# Engine capability catalog

> Reference for the **super-engine**. Each motor below is documented as
> "what it gives, what we use today, what we leave on the table".
> Goal: combine the pieces — none of the engines wins alone, but their
> *outputs are orthogonal* and complementary. The super-engine's job is
> to route each output to the right layer of the pipeline (see
> [`03-pipeline.md`](./03-pipeline.md)).

## Engine A — pdfplumber

**Family:** deterministic, parses the PDF content stream directly.
**Strength:** pixel-perfect geometry from vector ops; no ML noise.
**Weakness:** no semantic labels; greedy `find_tables()` fuses adjacent
boxes.

### A.1 Page-level outputs

| Attribute | What it is | Volume (p1 of banking_1414) |
|---|---|---|
| `page.rects`             | every `re` rectangle op | 361 |
| `page.lines`             | every line/rule op | 18 |
| `page.curves`            | bezier / arc ops | 0 |
| `page.chars`             | each character with font, size, color, x0/y0/x1/y1 | 3463 |
| `page.images`            | embedded raster images | 1 |
| `page.annotations`       | PDF form fields / sticky notes | 0 |
| `page.edges`             | derived edges (h+v rules merged) | 1462 |
| `page.horizontal_edges`  | derived horizontal rules | 734 |
| `page.vertical_edges`    | derived vertical rules | 728 |
| `page.cropbox`/`mediabox` | page bounds (with offset!) | — |
| `page.find_tables()`     | grouped tables (one big greedy result per region) | 2 |
| `page.extract_tables()`  | tables as `list[list[str]]` cell text matrix | 2 |
| `page.extract_text()`    | raw text, no layout | 1 string |

### A.2 Per-character output (chars)

Each `char` dict carries: `text`, `fontname`, `size`, `x0/y0/x1/y1`,
`top`/`bottom`/`doctop`, `width`, `height`, `upright`, `matrix`,
`ncs` (color space), `stroking_color`, `non_stroking_color`,
`adv` (advance width), `mcid`, `tag`.

**Implication:** we don't strictly need LiteParse for font metadata —
pdfplumber's `chars` already exposes bold via fontname. The reason
LiteParse v2 is preferred is that it groups chars into **spans of
contiguous text with the same font**, which is what we want
downstream.

### A.3 What we use today (in `engines/pdfplumber.py`)

- `page.rects` → all `VisualRect` objects with `bbox + rect_type`
- `page.find_tables()` → per-table `BBox` + `table_grid` + `cells`
- table-cell text matrix
- checkbox / signature-field heuristics from `_is_checkbox`,
  `_is_signature`, `_looks_filled`
- `_checkbox_filled_by_overlap` for filled-square detection

### A.4 What we leave on the table

| Output | Where it would help |
|---|---|
| `page.lines`, `horizontal_edges`, `vertical_edges` | Capa 3 (geometry) — explicit row/column separators |
| `page.chars` with `non_stroking_color` | Capa 4 (profile) — detect highlighted/coloured cells |
| `page.images` bbox | Capa 1 (noise filter) — skip logo regions |
| `page.annotations` | Form fields with explicit names (when present) |
| Per-cell `extract_tables()` text | Capa 4 (profile) — already-grouped cell content |
| `mediabox.lly` offset | Capa 0 (coords) — must subtract for top-left origin |

---

## Engine B — Docling (TableFormer + layout model)

**Family:** ML pipeline on the rasterized page (layout + table
structure + reading order).
**Strength:** semantic labels (`section_header`, `table`, `footnote`,
`page_footer`, `key_value_region`…), heading levels, cell-level
header flags, merged-cell spans.
**Weakness:** mega-fuses adjacent regions into one block, can swap
reading order on dense forms, slow.

### B.1 Block labels — **30 possible**, we see 6

```
TEXTUAL
  text             section_header   title            paragraph
  caption          footnote         list_item        formula
  code             reference        marker

STRUCTURAL
  table            chart            picture          document_index

FORM-SPECIFIC  ← gold mine for our use case
  form             key_value_region
  field_key        field_value      field_heading
  field_item       field_region     field_hint
  checkbox_selected   checkbox_unselected
  grading_scale    handwritten_text empty_value

NOISE
  page_header      page_footer

SPECIAL
  fillable
```

What we see today on BBVA pages:
`text, section_header, table, picture, page_header, page_footer`.

What is likely available but we miss because the wrapper skips it:
`key_value_region`, `field_key/value`, `checkbox_*`, `form`,
`form_area`, `footnote`, `list_item`, `title`.

### B.2 ContentLayer — **5 layers**, we use 2

```
✓ body       — real content
✓ furniture  — page-level decoration (logo, footer, vertical legal)
✗ background — watermarks
✗ invisible  — hidden OCR layer
✗ notes      — annotations
```

`furniture` is **the noise we are already filtering manually** (vertical
"BANCO BILBAO VIZCAYA…" + "Página X de Y" + "Mod. CS POLIZA…"). Drop
the `furniture` layer at ingest and we save N filtering rules.

### B.3 Per-block fields (after the wrapper's flattening)

```python
DoclingBlock {
    bbox, label, page,            # geometry + type
    text,                         # block content
    heading_level,                # SectionHeader: 1, 2, 3…  ← hierarchy tree
    content_layer,                # body/furniture/…
    self_ref,                     # internal ID (for parent/child chains)
    cells                         # tuple[tuple[str]] for table — we flatten
}
```

### B.4 What Docling actually exposes per *table cell* (we throw most away)

```python
TableCell {
    bbox,                                                  # ✓ used
    text,                                                  # ✓ used
    row_span, col_span,                                    # ✗ COLSPAN!
    start_row_offset_idx, end_row_offset_idx,              # ✗
    start_col_offset_idx, end_col_offset_idx,              # ✗
    column_header: bool,                                   # ✗ Docling says "this is a column header"
    row_header:    bool,                                   # ✗ ditto row header
    row_section:   str | None,                             # ✗ section name within table
    fillable:      bool,                                   # ✗ form field
}
```

**Immediate impact:** `col_span >= 2` solves case 4 ("A débito"
covering 2 sub-columns). `column_header=True` solves case 7 pattern
6 ("Sin nómina"/"Con nómina" bare sub-headers).

### B.5 Per-text `Formatting` flags

```python
Formatting {
    bold, italic, underline, strikethrough, script
}
```

Available on every `TextItem`. Today we ignore — LiteParse provides
the same and we use it from there. Useful as a **cross-engine
agreement signal**: if both engines say `bold=True` → confidence ↑.

### B.6 GroupLabel — coarse grouping above blocks

```
list   ordered_list   chapter    section    sheet
slide  form_area      key_value_area
comment_section       inline     picture_area
```

`form_area` and `key_value_area` are explicit **macro containers** —
Docling marks "this whole region is a KV form". We don't extract
groups today (the wrapper iterates `doc.iterate_items()` flat).

### B.7 PictureItem.annotations

Each picture can carry ML-generated alt-text. For bank logos: not
useful. For diagram-heavy PDFs: useful as caption. Cheap to extract.

### B.8 What we use today (in `engines/docling.py`)

- Labels: only `text / section_header / table / picture / page_footer
  / page_header` (everything else: dropped because we filter to
  `BODY ∪ FURNITURE`).
- `heading_level` is extracted but **not used downstream**.
- `cells` flattened to `tuple[tuple[str]]` — loses every per-cell
  flag listed in B.4.

### B.9 What we leave on the table — priority order

| Output | Layer | ROI |
|---|---|---|
| `key_value_region`, `field_key`, `field_value` | Capa 7 (pairing) | **highest** — direct KV detection |
| TableCell `column_header` / `row_header` | Capa 5 (role) | high — no need to infer headers |
| TableCell `col_span` / `row_span` | Capa 3 (geometry) | high — fixes case 4 |
| `furniture` layer auto-drop | Capa 1 (noise) | high — removes a hand-written filter |
| `checkbox_selected/unselected` | Capa 4 (profile) | medium — banking forms |
| SectionHeader `heading_level` actually used | Capa 8 (hierarchy) | medium — h1/h2/h3 tree |
| `Formatting.bold` cross-check | Capa 4/9 (validate) | medium — confidence boost |
| GroupLabel `form_area`, `key_value_area` | Capa 2 (container) | medium — macro framing |
| `fillable` flag on TableCell | Capa 4 (profile) | low — when present, useful |

---

## Engine C — LiteParse v2

**Family:** lightweight text extraction with per-span font metadata.
**Strength:** every text span as a clean `{text, bbox, font, size,
bold}` record — no ML, no mega-fusion, very fast.
**Weakness:** no tables, no rects, no semantic labels — just spans.

### C.1 Per-span output (from wrapper)

```python
LiteItem {
    text,             # contiguous text in same font
    bbox,             # exact bbox
    font_name,        # raw font name, e.g. 'Arial-BoldMT'
    font_size,        # pt
    page,             # 1-indexed
}
```

### C.2 What we use today (via `LiteParse.parse(...).get_page(n)`)

- `page.text_items` → flat list of spans.

### C.3 Possibilities not exposed today

- `is_bold(font_name)` derived in `structural/classify.py` — works.
- Add derived: `is_italic`, `is_oblique`, `font_family`, `weight_class`
  (300/400/600/700) from a font-name dict.
- Add derived: `case_class` (UPPER/lower/Title/mixed/none) — already
  in `view_boxes_p1.py`, move to `classify.py`.
- Add derived: `digit_ratio`, `has_currency`, `has_percent`, `is_date`
  — content-type tags per span.

LiteParse v2 itself probably exposes more (rotation, color, language
detection). Worth re-reading the lib docs and elevating those flags
into `LiteItem`.

### C.4 What LiteParse cannot do (intentional)

- Group spans into cells / tables → use pdfplumber rects.
- Detect logical hierarchy → use Docling labels + our size heuristic.
- Detect images / pictures → use Docling or pdfplumber.

---

## Cross-engine matrix — who feeds which layer

| Layer | pdfplumber | Docling | LiteParse v2 |
|---|---|---|---|
| **0 · Coords** (mediabox offset) | ✓ owner | — | — |
| **1 · Atoms** (raw spans/rects) | rects, lines, chars | text + label per block | spans + font |
| **1b · Noise filter** | logo bbox (images) | `furniture` layer (auto) | size < 7 heuristic |
| **2 · Containers** | outer rects | `table`, `form_area`, `key_value_area` blocks | — |
| **3 · Geometry grid** | h/v edges, find_tables | TableCell `col_span/row_span` | DBSCAN x/y fallback |
| **4 · Cell profile** | char colors (highlighted) | `checkbox_*`, `fillable`, `Formatting` | bold, case, size, digits |
| **5 · Cell role** | rect heuristics (signature/checkbox) | `section_header`, `field_key/value`, `column_header`, `row_header` | derived from profile |
| **6 · Column coherence** | x-band grouping | — | x-cluster of spans |
| **7 · Pairing (KV)** | row-rect alignment | `key_value_region`, `field_key`+`field_value` | case-contrast, header-projection |
| **8 · Hierarchy** | parent-rect containment | `SectionHeader.heading_level` (h1/h2/h3) | size ladder |
| **9 · Cross-validate** | rect-contains-text test | label agreement | font/bold cross-check |

**Read this matrix as:** each layer has 1-3 sources of evidence. The
super-engine takes the most reliable one for each layer and uses the
others as confirmation. None of the engines wins on its own — the
combination wins.

---

## Design principles — what each engine actually knows

Framework distilled from the cases documented in
[`04-cases.md`](./04-cases.md). **Document-agnostic** — do not
hard-code banking patterns. Each piece of logic must reference these
principles.

| Engine | Sees | Misses |
|---|---|---|
| **pdfplumber** | exact vector rects (`re` ops) + horizontal/vertical rules | tables with no borders; greedy `find_tables()` fusion of any region sharing outer borders |
| **Docling / TableFormer** | logical row×col matrix from ML on the rasterized page | mega-fuses adjacent regions; loses nested hierarchy; slow |
| **LiteParse v2** | text spans with `font_name + size + bbox + bold` flag | no table concept; just spans + positions |

The three are **orthogonal** — geometric precision (pdfplumber),
semantic hierarchy (LiteParse), ML robustness (Docling). None is
sufficient alone.

### Table spectrum (the world, not this PDF)

| Type | Outer rect | Internal dividers | Optimal detector |
|---|---|---|---|
| A. **Full grid** | yes | all drawn | pdfplumber `find_tables` |
| B. **Header rects + body full-width** | yes | header only | pdfplumber header + LiteParse projection on body |
| C. **Outer rect + text-positioned** | yes | none | pdfplumber outer + DBSCAN x on LiteParse |
| D. **No borders** | no | none | DBSCAN x + y-clustering on LiteParse |
| E. **Horizontal rules only** | partial | row separators | pdfplumber h-rules + x-clustering |

Cases 1–5 of [`04-cases.md`](./04-cases.md) map to B, B, B/C, D, C.
Type A is already covered.
