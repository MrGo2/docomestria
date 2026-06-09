# Structural Extraction — Strategy

Companion to `structural-extraction-handoff.md`. Captures the fusion strategy
agreed after validating each engine against LABORAL.pdf and PATRIMONIAL.pdf
(both Spanish PNJ judicial documents) plus the Azure DI baseline.

## TL;DR

Three engines, three roles, **all combined** through a candidate-emitter
pipeline. No engine is dropped, no engine is the single source of truth.

| Engine | Best at | Weakness |
|---|---|---|
| **Docling** | Tables with clear grid — fuses multi-line labels, splits label/value columns, marks spanned cells as titles | Misses tables without drawn borders; doesn't split inline `label: value` |
| **LiteParse** | Granular text + format (bold/regular, font_size) per item, exact Y/X bbox | No semantic structure, no table awareness |
| **pdfplumber** | Visual containers: table boundaries, sub-header rect boxes, cell layout | Joins multi-line content into single cells, loses bold/regular signal |

The combination beats Azure DI on the exact failure modes we observed.

## Validated baseline — Azure DI failure profile by document type

Five Spanish PDFs benchmarked: two PNJ judicial forms (LABORAL, PATRIMONIAL)
and three BBVA banking contracts (Tarjeta, Repsol+Crédito, Préstamo Personal).

| PDF | Pages | Azure KV | Precision | Recall | Dominant mode |
|---|---:|---:|---:|---|---|
| LABORAL | 1 | 16 | 81% | high | RowShift |
| PATRIMONIAL | 4 | 38 | 75% | high | Cascading row-shift |
| BBVA3 Tarjeta | 5 | 40 | 55% | mid | TableHeaderAsKey |
| BBVA4 Repsol | 12 | 37 | 40-50% | low | DenseFeeTable + ColumnReplica |
| BBVA5 Préstamo | 16 | **10** | 90% | **very low** | TableSwallowsKVs |

Trade-off pattern: **Azure trades recall for precision on contracts**. BBVA5
emitted only 10 pairs in 16 pages, missing TAE, cuota, comisiones, IBAN —
the load-bearing fields a user needs. Confidence stays 0.94–0.99 even on
wrong pairs, so confidence is not a usable filter.

### Failure modes (rolling — verified in at least one of the five PDFs)

**From judicial PDFs:**

1. **SubHeaderAsValue** — `CCC:` → `Situaciones`,
   `Capacidad Economica:` → `DGP - Consulta DNI` (next section's title).
2. **CascadingRowShift** — in vertical two-line lists, `service[N].status`
   gets paired with `service[N+1].label`, cascading through ~7 pairs.
3. **MultiLineLabelFragmented** — `Razón Social/Convenio/Régimen:` broken
   because the label spans two bold rows with the value between.
4. **EmptyValueMispaired** — Empty value reported as next item's text.

**Added from banking contracts:**

5. **TableHeaderAsKey** — column headers (`CUOTA ANUAL`, `IMPORTE`, `Nota 1`)
   promoted to keys; values are arbitrary nearby cells (BBVA3, BBVA4).
6. **TwoColumnFormReplication** — Titular 1 / Titular 2 forms emit duplicate
   keys (`Nombre y apellidos` ×4 in BBVA4) with no column metadata.
7. **TableSwallowsKVs** — Azure detected page 3 of BBVA5 as a table and
   emitted **zero** KV pairs for it, silently omitting ~15-20 critical fields.
8. **DenseFeeTable as KV** — 2D matrices (rows × columns of numeric fees)
   shredded into fragmentary single-cell pairs (BBVA4 #19, #20, #24, #32).
9. **PolygonContentInconsistency** — value's bbox correctly covers line X but
   the extracted *string* concatenates tokens from outside the bbox (BBVA4
   KV #1: bbox covers "NIF QUE COMIENCEN" but text fuses with the prior
   line's `N.I.F.: X3669812R`). **Dangerous**: passes naive bbox validation.
10. **CertSerialAsKV** — Digital-signature footer (`Número de serie`,
    `Fecha de Certificación`) extracted as KV. Useful or noise depending on
    use case; unique to signed docs.

### What Azure gets right on contracts that we MUST replicate

**ProseSuppressionWin** — On BBVA3 pages 2-5 (dense clauses with many inline
`:`) Azure correctly emitted 0 KV pairs. On BBVA4 pages 2-10 (9 pages of
Condiciones Generales prose) also 0 KV. This is a feature, not a bug:
contract clauses contain colons inside sentences that are NOT key-value
markers. Our extractor must implement an equivalent suppression.

## Engine roles — validated on PATRIMONIAL `Servicios Consultados` (11×2)

```
Docling row 1: ['AEAT - Consulta Percepciones:',         '0001 Operación Correcta. No existen datos.']
Docling row 5: ['DFNavarra - Consulta Capacidad Economica:', '0001 Operación Correcta. No existen datos.']
```

Docling's TableFormer **already fused the two-line bold label into one cell**
and paired it with the regular value. This is exactly the output we want.
Zero post-processing needed.

```
Docling row 0: ['Servicios Consultados', 'Servicios Consultados']
Docling row 1: ['DGP - Consulta DNI',    'DGP - Consulta DNI']
```

Cells where `col[0] == col[1]` are visually-spanned cells = section titles,
**not** KV pairs. Clean rule. Same signal solves LABORAL's `Situaciones`.

## Where Docling alone is NOT enough

```
Docling LABORAL "Datos Petición" table (4×1):
  row 1: 'Nº Procedimiento : 987-15'      ← label and value in one cell
  row 2: 'Nº Documento : X6573514E'       ← idem
```

When a table has a single column but the cell text contains `:`, the label and
value are inside the same string. Docling does not split them. We need an
**in-item split rule** that finds `:` inside a label and emits two halves.

Other gaps Docling alone cannot cover:
- PDFs without drawn tables (forms with free-floating labels)
- Items outside any detected table (paragraph KV pairs)
- Empty values that need to be detected by absence (no regular item on same Y)

LiteParse + pdfplumber fill these.

## Architecture — candidate emitter pipeline

```
src/docomestria/structural/
  models.py         ← frozen dataclasses (DONE)
  classify.py       ← TITLE / LABEL / VALUE / BODY per LiteItem (DONE)
  structure.py      ← hierarchy: sections, boxes, table boundaries
  candidates.py     ← 4 emitters, each producing PairCandidate with evidence
  scoring.py        ← weighted features → confidence, dedupe, conflict resolve
  extractor.py      ← orchestrator: engines → classify → structure → candidates → scoring
```

### Candidate emitters (each emits PairCandidate with `rule` + `features`)

```
E1. emit_from_docling_tables(docling_blocks)
    For each Docling table with 2 columns:
      for each row:
        if col[0] == col[1]: SKIP (spanned title — emit Section instead)
        else: emit candidate(label=col[0], value=col[1], rule="D-2col")

E2. emit_from_in_item_split(classified_items)
    For each LABEL item whose text contains ':' NOT at the very end:
      emit candidate(label=text_before_colon, value=text_after_colon,
                     rule="L-inline-split")
    Also applied to Docling 1-col cells.

E3. emit_from_horizontal_pair(classified_items, structure)
    For each LABEL item with no value already paired by E1/E2:
      find VALUE items on same Y (±3pt), to the right (X > label.right)
      emit candidate(label, value, rule="L-horizontal")
    Skip items that fall inside Docling tables already emitted by E1.

E4. emit_from_vertical_pair(classified_items, structure)
    For each LABEL item with no horizontal partner:
      find VALUE items directly below (Y+h ±5pt), X-aligned to label.left
      emit candidate(label, value, rule="L-vertical")
    Skip items already inside Docling-handled tables.
```

### Structure layer (separate from emitters)

```
S1. Sections from Docling section_header (lvl=1, 2, 3) — open until next
S2. Furniture filter from Docling content_layer=furniture — exclude from KV
S3. Pictures from Docling label=picture — exclude bbox region
S4. Boxes from pdfplumber rect_type=box (sub-header bars inside tables)
S5. Table boundaries fused from Docling tables ∪ pdfplumber tables (IoU)
S6. Prose suppression — added after BBVA findings: detect dense-paragraph
    regions and mark all items inside as no-KV-emission. Triggers:
      - 3+ consecutive Docling text blocks
      - LiteParse items with avg > 8 words and ≥1 period each
      - Inside a Docling section labelled with "Condiciones Generales",
        "Cláusula", or recognised clause-prefix patterns ("I.1", "a)", etc.)
    Items remain classified (TITLE/LABEL/VALUE) but candidates.py skips them.
S7. Two-column form detection — when a section has two parallel columns of
    same-label items (Titular 1 / Titular 2), record the column index on
    each emitted Pair so downstream can disambiguate `Nombre[col=1]` vs
    `Nombre[col=2]`. Detection: cluster LABEL items by X, find symmetric
    pairs around the page midline.
S8. Dense table detection — for Docling/pdfplumber tables with N×M cells
    (M ≥ 3, neither column matches LABEL/VALUE 2-col shape), classify as a
    *data matrix*. Don't emit as KV; expose as `Table(rows, cols, headers)`
    in the StructuralExtraction so the caller can read it as tabular data.
```

Structure feeds the emitters: `inside_docling_table?`, `inside_subheader_box?`,
`current_section_title`, etc. Stored on each `PairCandidate.features`.

### Scoring (single rule-based scorer)

```
score = base[rule] + bonuses - penalties

base:
  D-2col          0.80   (TableFormer is reliable on what it detects)
  L-inline-split  0.75   (':' inside a bold item is a strong lexical signal)
  L-horizontal    0.70   (well-defined geometry)
  L-vertical      0.55   (more ambiguous)

bonuses:
  label ends with ':'                    +0.10
  same engine confirmed by 2+ candidates +0.10
  value classified VALUE (not UNKNOWN)   +0.05
  inside known section                   +0.03

penalties:
  candidate crosses sub-header box       -0.30
  value is BODY (footer/small text)      -0.20
  label and value differ in font_size    -0.05

confidence band:
  >= 0.80  HIGH
  0.50–0.79  MEDIUM
  < 0.50  LOW (still emitted for inspection)
```

Each Pair carries `evidence: tuple[str, ...]` listing every rule that
contributed — auditable end-to-end.

## Dedup & conflict resolution

A single label may be reached by multiple emitters with different values. The
scorer:

1. Groups candidates by (label_text, label_bbox).
2. If one candidate scores ≥ 0.20 above the others → emit it, discard rest.
3. If scores are within 0.20 → emit the highest-scoring, mark `evidence` with
   "tied-with: <rule>" so downstream can inspect.

## What we will NOT do

- No regex for value typing (no "this is a NIF").
- No LLM in the structural extractor (the LLM lives in `pipeline/` and runs
  *after* structural extraction, on the cleaned text).
- No learned weights yet — the scoring weights above are hand-picked starting
  points. ParseBench + the Azure-comparison PDFs will tell us how to tune.

## Open questions (carry from v0.7.0 handoff)

| # | Question | Where decided |
|---|---|---|
| Q1 | bold without `:` → label or not? | E3/E4 emit candidates; scoring penalises |
| Q2 | items outside any box → apply pairing? | E3/E4 still run; structure provides scope |
| Q3 | Docling label conflict with LiteParse format | Both contribute; classify uses LiteParse, structure uses Docling |
| Q4 | Tables seen by Docling but not pdfplumber | E1 still runs on Docling-only tables; no penalty |

## Implementation status (v0.7.0 MVP — shipped)

All eight planned stages plus extensions delivered. Final pair counts:

| PDF | Pairs | HIGH | Regression | Notes |
|---|---:|---:|---|---|
| LABORAL | 15 | 15 | 12/12 ✅ | Full Respuesta table + Datos Petición |
| PATRIMONIAL | 36 | 36 | 8/8 ✅ | 4 pages, all Servicios + Datos Personales |
| BBVA3 Tarjeta | 21 | 21 | — | 14 form pairs + 5 interest + 2 inline |
| BBVA4 Repsol+Crédito | 34 | 34 | — | Form + interest + inline + multipage |
| BBVA5 Préstamo | 25 | 25 | — | TAE Sin/Con + Cuota + Comisiones |

Modules under `src/docomestria/structural/`:

- `models.py` — frozen dataclasses + enums
- `classify.py` — ItemKind detection from font + position
- `structure.py` — sections, tables, sub-sections, prose / furniture /
  picture regions, shadow-table dedup
- `candidates.py` — five emitters (D-2col / L-inline-split / L-horizontal
  / L-twocol-form / L-vertical reserved)
- `scoring.py` — rule-based scorer, dedup, Confidence bands
- `extractor.py` — `structural_extract(pdf_path)` public API

Validation scripts under `scripts/`:

- `download_parsebench_sample.py` — 15 ParseBench PDFs + ground truth
- `run_engines_on_sample.py` — idempotent engine runner
- `build_comparison_view.py` — side-by-side PDF + engine outputs HTML view
- `validate_classify.py` / `validate_structure.py` / `validate_extract.py`
- `build_index.py` — INDEX.md summary table

## Remaining work for v0.7.1 / v0.8.0

1. **Multi-colon item split** — `'Tipo Identificación: NIF PERSONA FISICA
   N.I.F.: 009786573G'` currently splits on first colon only; should
   split into 2 pairs using right-column labels as boundary hints.
2. **pdfplumber off-page shadow guard** — drop pdfplumber tables whose
   bbox.top is below the bottom-most LiteParse Y on the page. Requires
   carrying page heights through the model.
3. **L-vertical emitter** — label-above-value-below geometric pairing
   for layouts that have no grid. Reserved slot is wired in scoring.
4. **Unit tests** — pytest suite per module mirroring `tests/`.
5. **Documented public API** — README + sphinx-style docstrings on the
   `structural_extract` entry point.
6. **ParseBench broad eval** — current validation uses 5 hand-curated
   Spanish PDFs; broader runs against ParseBench's table/text/layout
   splits will surface failure modes in other document domains.

## Validated counter-examples (always-on regression set)

When candidates.py / scoring.py change, these specific cases must hold.

**Judicial (PNJ):**
- LABORAL `CCC:` → empty value (not "Situaciones")
- LABORAL `Razón Social/Convenio/Régimen:` → "RGIMEN ESPECIAL TRABAJADORES AUTNOMOS"
- LABORAL `Situaciones` → Section/Title (not value of CCC:)
- PATRIMONIAL `AEAT - Consulta Percepciones:` → "0001 Operación Correcta. No existen datos."
- PATRIMONIAL `Datos Personales` → SubHeader (not value of anything)
- PATRIMONIAL `Capacidad Economica:` (first occurrence) → "0001..." (NOT "DGP - Consulta DNI")
- PATRIMONIAL p1 `Nº Procedimiento: 987/2015` → in-item split into label + value

**Banking (BBVA) — must extract:**
- BBVA3 `Contrato Núm.:` → "0182 - 0539 - 0615 - 00000028350350"
- BBVA3 `Límite de Crédito:` → "900,00"
- BBVA3 `Sistema de reembolso:` → "TOTAL"
- BBVA5 `Primer apellido:` → "PRIETO" (and discriminate from Titular 2 column)
- BBVA5 `Fecha Entrada en Vigor:` → "29-03-2021"
- BBVA5 dense table p3 — must surface TAE Sin/Con nómina, Cuota, Comisiones
  as `Table` with row/col labels (Azure dropped them entirely).
- BBVA4 `Tipo Identificación:` → "NIF QUE COMIENCEN CON X Y Z"
  (not fused with `N.I.F.: X3669812R` from the line above).

**Banking (BBVA) — must NOT emit:**
- BBVA3 pages 2-5 prose clauses → zero KV pairs (Azure suppressed correctly)
- BBVA4 pages 2-10 Condiciones Generales → zero KV pairs
- BBVA5 cover page bold disclaimer ("Tómese su tiempo y léalo atentamente…")
  → classify as BODY, not LABEL (currently misclassified by classify.py)
- BBVA3 `b) Pago Aplazado:` (clause heading) → not a KV pair, even though
  it ends with `:` (followed by sentence prose, not a value)

## Open issue — classify.py needs an update

Validated on BBVA: current classify.py mis-labels two patterns as LABEL:

1. **Bold prose paragraphs** — `Tómese su tiempo y léalo atentamente...` etc.
   Bold + same-size + no colon + multi-line sentence → should be BODY.
2. **Clause-introducer colons** — `b) Pago Aplazado: Esta modalidad permite,
   a su vez, las siguientes...` Bold ends-with-colon + followed by sentence
   prose → not a KV; should be marked as `CLAUSE_HEADING` (new kind) and
   skipped from pairing.

Both detected by S6 (prose suppression) at structure.py time, OR upgraded
in classify.py via a heuristic: if a "LABEL" item is followed within ±20pt
by 2+ same-page items whose text contains sentence-end punctuation, downgrade
to BODY/CLAUSE_HEADING. To be done before candidates.py work.
