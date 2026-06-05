# Why fusion?

Each engine is excellent at one thing and blind to the others.

## What each engine alone misses

### LiteParse v2 alone

You get crisp text and font metadata, but you do not know *what role* each item
plays. Is "DATOS PERSONALES DEL TITULAR" a heading or just a bold sentence? Is
"X" a checkbox marker or a literal letter? LiteParse cannot tell you.

### Docling alone

You get labels like `section_header`, `list_item`, `table`, and a heading
hierarchy. But Docling collapses runs of text into block-level entities,
losing per-glyph fidelity. You also lose font names and font sizes, which
matter when you want to render an exact reconstruction or apply font-based
heuristics.

### pdfplumber alone

You get every vector primitive: rectangles, lines, curves. Forms become
visible as boxes. Checkboxes show up as small squares. But pdfplumber has no
notion of semantics — it has no idea which box is a section frame, which
one is a checkbox, or which text belongs to which box.

## The combined view

| Question                                                | LP  | DL  | PP  | Fused |
|---------------------------------------------------------|:---:|:---:|:---:|:-----:|
| Exact text and bbox of every glyph run                  | yes | -   | -   | yes   |
| Font name and size per run                              | yes | -   | -   | yes   |
| Semantic role of each run                               | -   | yes | -   | yes   |
| Heading hierarchy                                       | -   | yes | -   | yes   |
| Visual boxes that group fields on a form                | -   | -   | yes | yes   |
| Section title of each box                               | -   | -   | -   | yes   |
| Checkbox detection                                      | -   | -   | yes | yes   |

The last two rows are the unique value: only the fused view can say *"this
list item lives inside the box titled DATOS PERSONALES DEL TITULAR and is
rendered in Arial-Bold 12pt."*

## Where it matters

- **Form extraction** — group labels and values by the box that encloses them.
- **Contract analysis** — attach every clause to its section heading.
- **Audit and provenance** — for every value you extract, you can point at the
  exact pixels and the exact font that produced it.
- **OCR-free pipelines** — for digital PDFs you get all of the above without
  rasterizing a single page.

## Why typed extraction with bbox preservation

LLMs are great at pulling raw strings out of forms but terrible at
*structured* output: ask for a date and you might get `"06 de Diciembre"`,
`"6/12/26"`, or `"December 6th"`. Ask for an amount and the currency may or
may not be there. Ask for a Spanish NIF and you may get an invalid checksum.

Docomestria's transform layer normalizes the raw strings to typed Python
values (`date`, `Decimal`, `Money`, validated `str`, `bool`, ...) while
keeping the original `bbox`, `page`, and source-item indices attached. That
means every typed value still answers "where in the PDF did this come from?"
— so you can render highlights on the original page, audit hallucinations,
or feed downstream OCR-quality metrics. Format-level issues (`invalid_date`,
`nif_checksum_mismatch`, `currency_ambiguous`) surface explicitly rather
than crashing the pipeline.
