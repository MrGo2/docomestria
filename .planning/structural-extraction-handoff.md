# Structural Extraction v0.7.0 — Handoff

Branch: `feature/structural-extraction` (in both `docomestria` and `docomestria-studio` repos)

## Context

After v0.6.4, agreed approach: build `structural_extract(pdf)` that produces
auto-discovered key-value pairs and hierarchical structure WITHOUT any
semantic interpretation, LLM, or regex-based type guessing.

Only 3 signals are allowed:

1. **Position** — pdfplumber rects (boxes, table cells)
2. **Structure** — Docling labels (section_header, table, list_item, text, picture, page_footer)
3. **Format** — LiteParse font_name (bold/regular/italic) and font_size

## Agreed pairing logic (priority order)

### Rule 1 — pair inside a single cell
If a pdfplumber table cell contains exactly 2 LiteParse items:
- bold + regular → (label=bold, value=regular)
- HIGH confidence if bold ends in `:`

### Rule 2 — horizontal pair (same row)
If a bold item and a regular item share the same Y (±3pt) and the regular is
to the right of the bold:
- → (label=bold, value=regular)
- HIGH confidence if bold ends in `:`

### Rule 3 — vertical pair (label above value)
If a bold item has no value to its right but a regular item sits directly below
(Y+height ±5pt) with similar X-start:
- → (label=bold, value=regular)
- MEDIUM confidence (more ambiguous)

## Agreed hierarchy

Five levels of structural nesting:

1. **Document** — Docling section_header level=1 → doc title
2. **Section** — Docling section_header level≥2 → opens a section; everything
   until next header belongs to it
3. **Box** — pdfplumber rect of type "box". Top-of-box bold+larger item = box
   title; rest = box contents
4. **Sub-section inside a table** — A table row containing a single bold item
   whose font_size > rest of the rows → sub-header. Subsequent rows belong to
   this sub-section until the next sub-header
5. **Cell** — pdfplumber table cell. Cell with 1 regular item = atomic value;
   cell with 1 bold + N regular = label + values; cell with 2+ same-weight
   items = multi-value

## Open questions to resolve with user (next session)

User said he will provide real PDFs with manual annotations marking which items
are key-values, which are tables, what the hierarchy is — so we can iterate
against ground truth rather than guess.

### Q1 — bold WITHOUT `:` followed by regular
Should we treat it as a pair (more coverage, less precision) or only count
bold+`:` as a label?
- Option A: yes with medium confidence
- Option B: no — only bold+`:`

### Q2 — items outside any box or cell (free-floating text)
Should we apply Rules 2-3 anyway, or skip?
- Option A: extract if rules fire
- Option B: ignore — only items inside structure

### Q3 — Docling section_header vs LiteParse format conflict
If Docling says "section_header" but the item is small regular text in
LiteParse, who wins?
- Option A: Docling (semantic structure trumps)
- Option B: LiteParse (real visual format trumps)
- Option C: only when both agree

### Q4 — tables detected by Docling but NOT pdfplumber (no drawn lines)
Should we extract them using X-clustering on item centroids? Or skip?
- Option A: skip — only pdfplumber-confirmed tables
- Option B: try X-clustering for column boundaries

## Output target

```python
StructuralExtraction(
    pages=[Page(number=..., sections=[Section(...), Box(...), Table(...)])],
    pairs=[Pair(label=..., value=..., source_cell=..., source_box=..., confidence=..., evidence=[...])],
)
```

Every Pair carries explicit `evidence` list (which rules fired) for auditability.

## Garantías to preserve

- Reproducible 100% (no ML, no LLM, no random)
- No hallucination (only emit what the 3 signals confirm)
- Auditable (every decision has a `source`)
- Fast (<100ms post-fusion)
- Offline
- Schema-free (works on any PDF)

## Garantías NOT promised

- Semantic typing of values (no regex saying "this is a NIF")
- Multi-page reasoning beyond reading order
- Resolving label ambiguity (two NIFs in same doc)
- Free-text extraction without visible labels
- OCR of scanned PDFs

## Next session bootstrap

1. `cd /Users/carlos/Edelwyss/Projects/docomestria && git checkout feature/structural-extraction`
2. `cd /Users/carlos/Edelwyss/Projects/docomestria-studio && git checkout feature/structural-extraction`
3. Re-read this file
4. User provides annotated real PDFs
5. Implement `src/docomestria/structural.py` with the agreed rules
6. Add studio view "Estructura detectada" showing pairs + hierarchy
7. Iterate against user annotations

## Empirical study

Postponed. Will be done globally (all docs pooled, no per-type segmentation)
once the structural extractor is stable and user has annotated enough cases
to compute precision/recall.
