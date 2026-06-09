# Cases — evidence from real BBVA contracts

Eight concrete failure cases collected during the visual-debugging
session on `banking__bbva_loan_1414.pdf` and `BBVA_0608-01491495_DOC2_CONTRATO.pdf`.
Every design choice in [`01-model.md`](./01-model.md) and
[`03-pipeline.md`](./03-pipeline.md) traces back to one of these cases.

Visual debugger: `scripts/view_boxes_p1.py` at `http://localhost:8770/`.

## Case 1 — Rect-height filter too aggressive (banking_1414 p1)

**Symptom.** User-marked region (27.5, 398.5, 218.5×52) on page 1 is a
2-column × 3-row sub-table (header bold + 2 data rows). pdfplumber **does
draw** all 6 cells, but my filter (`w>50 AND h>20`) dropped the data rows
because they're 12pt and 16.5pt tall.

**Confirmed in viewer (scripts/view_boxes_p1.py).**
- pdfplumber raw rects in zone:
  - `y=399 h=24.0` × 2 cells  (header — kept)
  - `y=423 h=16.5` × 2 cells  (row 1 — DROPPED)
  - `y=439 h=12.0` × 2 cells  (row 2 — DROPPED)
- LiteParse v2 content is correct (bold title + bold first row + plain
  second row).
- Docling fuses the whole region into its single 11×8 table → no help.
- pdfplumber `find_tables()` reports 18 rows in one big P2 table → no help.
- `cluster_subtables()` sees S3 as `1×2` (just the header) because data
  rows were never in the input.

**Fix to consider.**
- Lower the rect filter to `h >= 8` (or `h >= text_median_height * 0.5`).
- Re-run `cluster_subtables()` and check sub-table count on the BBVA set.
- Risk: many tiny glyph-bound rects could leak in — keep `w >= 50` and
  add a "must contain ≥1 LiteParse text span" gate.

**Related areas to revisit at the same time.**
- `cluster_subtables` edge-tolerance (`EDGE_TOL=4.0`) and gap rules — may
  need a per-pdf calibration after the new rects come in.
- Numeric-content classification (`annotate_boxes_with_content`) — small
  sub-tables like this one are exactly where the `NUM`/`txt` signal would
  pay off, but only if they're detected first.
- Inline-KV LABEL classification (commit dc541e4) — verify the new
  granular sub-tables don't regress the banking-form fix.

**Trigger.** Don't act until we've collected ≥2-3 related findings from
this debugging session; fix them together in one structural-pass commit.

## Case 2 — Same root cause as case 1

**Second confirming case** — same root cause as case 1.

User-marked region (28, 452, 219.5×55.5). Identical structure: 2×3
sub-table.

- pdfplumber rects (all dropped by `h>20` except middle row):
  - `y=453.8 h=16.5` × 2  (header — DROPPED)
  - `y=470.2 h=24.8` × 2  (row 1 — kept)
  - `y=495.0 h=12.8` × 2  (row 2 — DROPPED)
- LiteParse content: `COMISIONES POR OTRAS OPERACIONES` / `IMPORTE`
  → `Por Consultas en Cajeros...` / `0,60` → `Por emisión de
  duplicados` / `4,00`

Same failure mode → reinforces the fix (lower `h>=8`, gate by ≥1
LiteParse text inside).

## Case 3 — Header-projection for full-width body rows

**Symptom.** User-marked region (27.5, 509.5, 221×153.5) — INTERESES
rates table — has a 3-column header row of explicit rects but every
body row is drawn as a **single full-width rect** even though the text
is visually arranged in 3 columns by absolute x-position.

**Evidence.**
- Raw rects (all kept; header row h=19.5, body rows h≥24):
  - `y=510 h=19.5`  → 3 cells `[w=83][w=58][w=78]`  ← 3-col header ✓
  - `y=529 h=24.0`  → 1 cell  `w=219.8`            ← body row 1
  - `y=553 h=30.0`  → 1 cell  `w=219.8`            ← body row 2
  - `y=583 h=52.5`  → 1 cell  `w=219.8`            ← body row 3
  - `y=636 h=27.7`  → 1 cell  `w=219.8`            ← body row 4
- LiteParse content is positioned in 3 implicit columns (concept,
  numeric rate, clause-reference) but no vertical rules separate them.
- pdfplumber `find_tables()` → folds into the big P2 table.
- Docling → fuses into single 11×8 (loses the rate→clause mapping).
- `cluster_subtables()` → reports `S?: 4×1` (4 rows, 1 col) — wrong
  column count.

**Fix to consider.**
- When a "row" rect spans the full width of a preceding header that has
  N>1 cells, project the header's column boundaries onto the body row's
  bbox and emit N "virtual cells" per body row.
- Assign each LiteParse span inside the body rect to its column by
  testing which virtual cell contains its center.
- This is a generic "header-projected body" pattern likely present in
  other rate-table PDFs (e.g. mortgage contracts).

**Related areas to revisit at the same time.**
- Schema: virtual cells need a flag so the consumer knows they're
  projected, not drawn (debugging trace).
- The 3-engine fusion in `structural` may need an explicit
  `column_index` source field ("from header projection") for
  audit logs.

## Case 4 — Text-positioned tables with no internal rects

**Symptom.** User-marked region (248, 397.5, 327.5×165) — "Comisión por
retirada de efectivo mediante tarjeta" rate table on the right side of
page 1. Real structure is **5 effective columns** (1 label + 2 super
columns × 2 sub columns) with **multi-row headers (colspan)** and ~6
body rows. The PDF draws only **3 outer rects**:
- `y=399 h=36   x=249 w=166`  ← left header strip
- `y=399 h=163  x=415 w=161`  ← entire right half, no subdivisions
- `y=435 h=128  x=249 w=166`  ← entire left body, no rows

Everything inside is **pure text-positioning** — column boundaries and
row boundaries exist only as absolute x/y of LiteParse spans.

**Reconstructed structure (from LiteParse).**
- Super-header row: `Comisión por retirada…` (col-label super) +
  `A débito` (cols 2-3 colspan) + `A crédito` (cols 4-5 colspan)
- Sub-header row: `%` `Mínimo` `%` `Mínimo`
- 6 body rows with 4 numeric values each, e.g. `Cajeros Grupo BBVA en
  España → 0,00 0,00 4,00 4,00`, including one row that's literally
  `Nota 1 Nota 2 Nota 1 Nota 2` instead of numbers.

**Why every engine fails here.**
- pdfplumber `find_tables()` → folds the 3 outer rects into P2.
- Docling → 11×8 single table absorbs it.
- `cluster_subtables()` → treats outer rects as 2 single-cell clusters.
- LABEL/VALUE classify can't distinguish columns because the rect grid
  doesn't expose them.

**Fix to consider (multi-step, larger than h>20 filter).**
1. **Detect numeric column bands** by 1-D clustering on `\d+,\d+`
   token x-centres (DBSCAN on x). Output: ordered list of column
   x-ranges.
2. **Detect header band** as the contiguous bold-span region above the
   first numeric row, project header text onto the column bands to
   assign labels (handle colspan when a bold span covers >1 column).
3. **Detect rows** by y-clustering of value/label spans; row label =
   bold-or-regular span in col 1.
4. **Schema:** emit virtual cells with a `from_text_position=true`
   flag and a per-column-band confidence (separation strength).

**Related areas to revisit at the same time.**
- This pattern is common in banking, insurance, telecom rate sheets —
  worth a dedicated motor (`E6_TEXT_GRID`?) in `candidates`.
- LiteParse already gives us bold + position; no new engine needed.
- The 4-engine fusion may need a precedence rule: when a region has
  no rect grid, the text-positioned cells should not be suppressed
  by an enclosing pdfplumber/docling "table".

## Case 5 — Parent-rect + top-edge bold title = SECTION

**Symptom.** User-marked region (26, 379.5, 553×391.5) is the parent
container for cases 1–3 above. The pdfplumber outer rect
(`552.8×389 @ (26.3, 381)`) already exists; the title
**"Condiciones económicas"** is a single bold span at `y=382`,
`size=11pt`, sitting **1.3pt below the rect's top edge**.

**Typographic hierarchy (page 1).**
- **Section title**:  bold, `size=11`, 1 line, on top edge of parent
- **Sub-section headers** (U1/U2/U3/U4 first row): bold, `size=9`, on
  top edge of each sub-rect
- Ratio `title_size / subheader_size = 1.22` → reliable hierarchy cue
- All section/sub titles use the same font family (`Arial-BoldMT`)

**What this enables.** The structural extractor can emit a nested
`section → subsections → rows` output instead of a flat KV list, e.g.:

```json
{
  "section": "Condiciones económicas",
  "subsections": [
    { "title": "Comisión anual por emisión…",  "rows": [...] },
    { "title": "COMISIONES POR OTRAS OPERACIONES", "rows": [...] },
    { "title": "INTERESES",                     "rows": [...] },
    { "title": "Comisión por retirada de efectivo…", "rows": [...] }
  ]
}
```

**Detection algorithm.**
1. For each outer rect (parent candidate), find bold spans within
   `top_edge ± 5pt`.
2. If exactly one such span exists AND its `font_size >= 1.15 *
   median_font_size_inside_rect` → mark as **section title**.
3. The remaining content of the rect splits into sub-rects (cases 1–3
   above) → each sub-rect's own top-edge bold span = sub-section title.

**Related areas to revisit at the same time.**
- The existing `structural` schema (v0.9.0) already has
  `sections / subsections` — verify the nesting matches this
  parent-rect-driven model and reuse it.
- Multi-column layouts (left/right in same parent, as here) need a
  column-split step before sub-rect enumeration (split parent at the
  vertical gap between U3 and U4 → cols).
- This is *the* unifying pattern for the BBVA form and likely for
  most Spanish banking/insurance forms — high-priority improvement.

## Case 5b — Title-above parent + virtual sub-sections inside one rect

**Symptom.** User-marked the `Titulares` block: 1 parent rect (552.8×184
@ (25.5, 144)) with **no internal rects** dividing the 3 visual
sub-sections (left column / right column / bottom strip). The section
title sits **above** the parent rect, not inside it.

**Evidence (page 1).**
- `y=130.6 x=280  "Titulares"  bold 9pt`  ← title, **outside** parent
- `y=144.0  parent rect 552.8×183.8` ← single outer, no sub-rects
- Inside the parent, three bold sub-headers position the children:
  - `y=146.5 x=33   "Datos Identificativos"`  (child 1, left col)
  - `y=146.5 x=306  "Datos Identificativos"`  (child 2, right col)
  - `y=300.1 x=267  "Datos Operativos"`       (child 3, bottom strip)
- 2-column split is **pure text positioning** (x=33 vs x=306, ~273pt
  apart, no vertical rule).
- Outlier: `y=151 x=11 size=5.5pt` carries the full bank legal
  footnote (`BANCO BILBAO VIZCAYA ARGENTARIA, S.A. …`) — noise that
  would derail naïve clustering. Filter by `size >= 7` for structure
  detection.

**Two new sub-patterns vs case 5 (Condiciones económicas).**
1. **Title OUTSIDE parent.** Detection must look both
   `top_edge ± 5pt` AND `top_edge − 15pt..top_edge` for the section
   title.
2. **Virtual sub-sections.** With no rect divisors, sub-sections must
   be inferred from **bold-header positions**:
   - Group bold headers with the same `font_size` and same `y` →
     they're peers in a **column-split** (left/right cols).
   - A bold header alone on a later `y` (gap > 80pt) → starts a new
     **horizontal slice** (bottom strip).

**Fix to consider.**
- Generalise the parent→title detection to:
  ```
  candidates = bold spans where y ∈ [parent_top − 15, parent_top + 5]
               AND size >= 1.15 * median_size_inside_parent
               AND size >= 7  (drop tiny legal text)
  ```
- Add a sub-section pass that doesn't depend on inner rects:
  cluster bold-headers by `(y_band, font_size)` → each cluster = a
  sub-section row; same `y_band` with distinct `x_band` = columns.
- Tiny-size spans (<7pt) should be classified as `footnote/legal`
  and excluded from structure detection (but kept for full-text
  output).

**Related areas to revisit at the same time.**
- The 2-column split here uses the same x-band logic as case 4
  (text-positioned tables). Unify into a single
  `infer_columns_from_text()` step that handles both.
- Three "Datos Identificativos" / "Datos Operativos" headers all use
  size=9 — sub-section level. Section title is also size=9 →
  the parent-relative ratio heuristic (1.15×) doesn't help here.
  Use **position** (title above parent, peers inside) instead of
  size to rank them. Re-evaluate case 5's ratio heuristic.

## Case 6 — Case-contrast as a KV signal (lowercase label → UPPER value)

**Symptom.** Page 2 of `BBVA_0608-01491495_DOC2_CONTRATO.pdf` —
section `TITULARES` → sub-section `Sus Datos Personales` → 4 rows of
KV pairs, none of them inside a drawn row-rect. The label/value
relationship is signalled exclusively by **case contrast** on the same
y-band:

```
y=230.7  x=191.8  lower  "Primer apellido"     →  y=229.4  x=276.7  UPPER  "PRIETO"
y=245.1  x=191.8  lower  "Segundo apellido"    →  y=245.2  x=276.7  UPPER  "ALVAREZ"
y=259.5  x=191.8  lower  "Nombre"              →  y=259.4  x=246.0  UPPER  "JULIA"
y=273.9  x=191.8  UPPER  "NIF"                 →  y=273.7  x=216.0  UPPER  "011075308A"
y=312.3  x=191.8  lower  "Domicilio fiscal"    →  y=312.7  x=266.2  UPPER  "CENERA, 42"
y=341.1  x=191.8  lower  "Código postal"       →  y=341.2  x=266.2  none   "33600"
y=355.5  x=191.8  lower  "Plaza"               →  y=355.4  x=224.3  UPPER  "MIERES DEL CAMINO"
```

Every label is `size=10 lower` (regular), every value is `size=10
UPPER` (regular). Same y (Δ<1pt), label x≈192, value x≥216.

**Why this matters.**
- It is **orthogonal** to the bold/rect signals. Neither pdfplumber
  rects nor Docling matrix nor bold-flag exposes these pairs. Only
  LiteParse + case classification reveals the structure.
- It generalises case 5 (parent rect with virtual sub-sections inside)
  to the **leaf level**: each KV row is itself a virtual cell pair.
- Works in printed banking/insurance/government forms across Spanish
  templates where the convention is `Etiqueta: VALOR`.

**Hierarchy already proven on page 2 (typographic ladder).**

| Role | Signal |
|---|---|
| SECTION   | `size=14 bold UPPER` (TITULARES) |
| SECTION-intro | `size=10 bold UPPER` (IDENTIFICACIÓN…) |
| SUB-SECTION | `size=10 bold lower` (Sus Datos Personales) |
| FIELD LABEL | `size=10 regular lower` |
| FIELD VALUE | `size=10 regular UPPER` (or numeric) |
| Page footer | `size=8 bold` |
| Legal footnote | `size=5.5` |

The combination `(font_size, bold, case)` is a 6-class classifier with
zero ML — distinguishes every element of the document hierarchy on
this page.

**Detection algorithm.**
1. For each pair of LiteParse spans `(a, b)` with:
   - `same font_size`
   - `|a.y − b.y| ≤ 2pt`  (same y-band)
   - `a.x + a.w < b.x`     (a is left of b)
   - `a.case == lower` AND `b.case in {UPPER, none}`
   - distance `b.x − (a.x + a.w) ≤ 40pt`
2. Emit a KV candidate `(label=a, value=b)` with HIGH confidence.
3. Multiple values on the same row (rate tables) → emit one KV per
   value, with `column_index` from x-band.

**Edge cases observed.**
- Bold-UPPER labels (`NIF`) → relax label rule to `case in {lower,
  UPPER}` when value is also UPPER but **numeric** (IDs, codes).
- A small label (`Nombre` w=35) → value (`JULIA` w=27) overlap-free
  → use first-non-whitespace x as alignment anchor, not full bbox.

**Related areas to revisit at the same time.**
- The classifier already in `structural/classify.py` uses bold + colon
  + size. Add case as a 4th signal with explicit `case_score`.
- Number-only values (`33600`, `0,60`) — extend the `case` test to
  also accept `none + has_digits` as valid value.
- Cross-validate with sub-section title (`Sus Datos Personales`) —
  KV pairs only belong to a sub-section if their y is within the
  sub-section's y-band (between sub-header y and next sub-header /
  end-of-rect).

## Case 7 — Variable-layout sections, multi-cell values, composite labels

**Symptom.** Page 3 of `BBVA_0608` is **one single section**
("Condiciones Económicas del Préstamo", `size=14`) whose internal grid
**changes column count mid-section**: 2-col → 3-col → 2-col across
three vertical bands.

Each row carries two nested rects: an **outer row rect** (w=383) plus
an **inner value rect** (w=215, x=346). When the layout switches to
3-col (bands "Sin nómina"/"Con nómina"), the inner rect splits into
two value rects (w=107 each at x=346 and x=453).

**6 new sub-patterns observed.**

1. **Variable column count per band.** Same section, different layouts:
   ```
   BAND A (y=111-394):  2-col  (label | value)
   BAND B (y=395-545):  3-col  (label | "Sin nómina" | "Con nómina")
   BAND C (y=546-627):  2-col  (label | value)
   ```
   Detection: re-infer column boundaries **per band** by re-running
   the column algorithm on each contiguous vertical slice.

2. **Multi-cell value (compound KV).** Row 6 "Comisión de Apertura":
   ```
   value spans (same y-band):
     "2,3000 %"  none      x=354.3
     "Mínimo"    lower     x=423.5
     "0,00"      none      x=484.1
     "euros"     lower     x=515.4
   ```
   The alternation `numeric/qualifier/numeric/unit` signals a compound
   value: `{valor: "2,3000%", minimo: "0,00 euros"}`.

3. **Multi-line wrapped value (rows 7-8).** Same value-column x-band,
   three consecutive y-rows (y=277.5, 289.5, 301.5), no new label in
   between: concatenate as a single value string `"1,0000% máximo,
   con un mínimo de 11,50 euros en concepto de coste administrativo
   de cancelación."`.

4. **Composite label (rows 7, 8).** "Comisión de Cancelación" +
   "Anticipada Total" / "Anticipada Parcial" — two spans in the
   label x-band on consecutive y. Concatenate; the full label is
   what defines the KV.

5. **Parenthetical clarifier (rows 1, 4, 11).** Directly under a
   label, span starting with `(` in `lower` regular:
   - `"(Importe en letra y número)"`
   - `"(mediante Abono en Cuenta)"`
   - `"(Importe Total + Intereses + Gastos)"`
   → attach as `label_disambiguation`, do not emit as a separate pair.

6. **Bare sub-header (no bold, no rect).** "Sin nómina"/"Con nómina"
   appear at y=405 as `lower` regular spans, not bold, with no rect
   of their own. They define columns for the rows below. Detection:
   spans that **align x-wise with the numeric columns** of the next
   row(s), and immediately precede a value band.

**Confirms case 6 extension.**
Most values on this page are numeric (`case=none`), not UPPER text.
The KV signal becomes:
```
label  : case == 'lower' AND bold
value  : case in {UPPER, none, mixed} AND (has_digits OR len_letters < 4)
```

## Case 8 — Per-cell profile + column coherence

**Idea.** Today we annotate **sub-table clusters** with content stats
(numeric %, dominant case). We should annotate **each pdfplumber rect**
with the same profile and use it for two things:

1. **Cell role classification** (per rect):
   ```
   role(cell) = function of(
     bold_ratio       ∈ [0, 1],
     case_dominant    ∈ {UPPER, Title, lower, mixed, none},
     digit_ratio      ∈ [0, 1],
     n_spans          ∈ ℕ,
     font_size_median ∈ pt,
   )
   ```
   Candidate roles: `LABEL`, `VALUE_NUMERIC`, `VALUE_TEXT`, `HEADER`,
   `SUB_HEADER`, `EMPTY`, `CLARIFIER`, `FOOTER`.

2. **Column coherence** (per x-band):
   - Group rects by x-range (allow ±4pt tolerance).
   - Compute the role distribution of cells in that column.
   - **Coherent column**: ≥80% of cells share the same role →
     promote it: "this is the label column", "this is the value
     column", "this is the % column".
   - **Mixed column**: emit each cell as standalone, no column-level
     inference.

**Why this matters.**
- Lets us trust LiteParse hints more: when the cell profile says
  `numeric value`, but the engine guess says `label`, flag the
  conflict for the ILP resolver.
- Solves the "header projection" case (case 3): the value column
  inherits its column-header from the first rect in its x-band that
  has `role=HEADER`.
- Catches the bare sub-header (case 7 pattern 6): a span not in a
  rect that aligns x-wise with a coherent numeric value column =
  column-header.
- Detects "label" vs "value" columns on page 3 page-wide:
  - col [177.8..345.8]: 100% LABEL (every cell is `bold lower`)
  - col [345.8..561]:   100% VALUE (every cell numeric or UPPER)

**Sketch.**
```python
def profile_cell(rect, spans_inside) -> dict:
    cases  = Counter(s.case_class for s in spans_inside)
    bolds  = sum(1 for s in spans_inside if s.is_bold)
    digits = sum(c.isdigit() for s in spans_inside for c in s.text)
    chars  = sum(len(s.text) for s in spans_inside)
    return {
        "n_spans": len(spans_inside),
        "case_dom": cases.most_common(1)[0][0] if cases else "empty",
        "bold_ratio": bolds / max(1, len(spans_inside)),
        "digit_ratio": digits / max(1, chars),
        "size_median": median(s.font_size for s in spans_inside),
        "role": guess_role(...),
    }

def column_bands(rects, tol=4):
    bands = []
    for r in rects:
        key = (round(r.x / tol) * tol, round((r.x + r.w) / tol) * tol)
        bands.setdefault(key, []).append(r)
    return bands  # {(x0, x1): [rects]}

def column_coherence(band_rects):
    roles = Counter(r["role"] for r in band_rects)
    top, n = roles.most_common(1)[0]
    return top if n / len(band_rects) >= 0.8 else None
```

**Related areas to revisit at the same time.**
- The existing `classify.py` already does per-LiteItem classification.
  Per-cell is an aggregation step on top — add to `structural/structure.py`.
- The viewer should expose this as a layer: "cell roles" coloured by
  role, with the column-coherence verdict shown per band.
- Cross-engine: when pdfplumber says "this is a cell" but the cell
  profile says `EMPTY` → it's a decorative rect, drop it (echoes the
  6-step validation rule).
