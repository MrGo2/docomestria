# Architecture

Docomestria is a thin orchestration layer over three independent PDF engines.
It does not parse PDFs itself.

## Data flow

```mermaid
flowchart TD
    PDF[PDF file] --> LP[LiteParse v2<br/>byte-perfect text + bbox + font]
    PDF --> DL[Docling<br/>semantic blocks + reading order]
    PDF --> PP[pdfplumber<br/>vector rects + lines]

    LP --> M[models.LiteItem]
    DL --> N[models.DoclingBlock]
    PP --> O[models.VisualRect]

    M --> F[fusion.fuse_from_engines]
    N --> F
    O --> F

    F --> R[list FusedItem]
```

## Coordinate system

All bounding boxes are normalized to **top-left origin** (y grows downward),
matching what LiteParse and pdfplumber report natively. Docling's
bottom-left coordinates are flipped via `to_top_left_origin(page_height=...)`
inside the engine wrapper.

## Matching rules

For each `LiteItem`:

1. **Docling block** — pick the smallest block whose bbox contains the item's
   centroid. If none, fall back to the highest IoU > 0. If still none,
   `docling_label = None`.
2. **Enclosing visual box** — pick the smallest non-checkbox `VisualRect`
   containing the centroid.
3. **Section title** — for each enclosing box, the largest-font item (ties
   broken by topmost position) becomes the box title; the title item itself
   is not tagged with its own title.

Smallest-first matching prevents page-spanning blocks from absorbing every
item. Checkbox-sized rectangles are excluded from the enclosing-box search
because they would otherwise always win.

## Module map

| Module        | Responsibility                                              |
|---------------|-------------------------------------------------------------|
| `geometry`    | Pure functions: area, centroid, IoU, containment.           |
| `models`      | Frozen dataclasses for inputs and `FusedItem`.              |
| `engines/*`   | Thin wrappers that turn PDF bytes into the model types.     |
| `fusion`      | The `fuse()` and `fuse_from_engines()` entry points.        |
| `pairing`     | Optional helper for form-style label-to-value pairing.      |

## Extensibility

`fuse_from_engines()` takes raw model lists, so any engine that emits the
shape of `LiteItem`, `DoclingBlock`, or `VisualRect` can be plugged in without
modifying the fusion code.

## LLM provenance layer (optional)

The `docomestria.llm` sub-package closes the loop between an LLM's extracted
output and the original PDF. It does not call any LLM — it only consumes the
JSON they produce.

```mermaid
flowchart LR
    PDF[PDF file] --> F[fuse]
    F --> FI[list FusedItem]
    FI --> LLM[your LLM]
    LLM --> J[JSON dict]
    J --> B[bind_provenance]
    FI --> B
    B --> BV[list BoundValue]
    BV --> V1[detect_hallucinations]
    BV --> V2[detect_role_mismatches]
    V1 --> I[list ProvenanceIssue]
    V2 --> I
```

For each scalar in the LLM output, `bind_provenance` searches the FusedItems
in three tiers: exact match, substring match, fuzzy match (`rapidfuzz`,
default threshold `0.85`). The result is a `BoundValue` carrying the source
item indices, the union bbox, the inferred section title, and the docling
label at the bound centroid.

`detect_hallucinations` flags values that could not be matched (or that
matched with a score below `require_score`). `detect_role_mismatches` flags
values bound to semantic blocks that are unlikely to hold data, such as
`section_header`, `title`, `page_header`, `page_footer`, or `picture`.

The layer is LLM-agnostic — Gemini, Claude, OpenAI, or local models all work
as long as they return JSON. Install with `pip install docomestria[llm]`.

## Typed extraction layer (optional)

The `docomestria.transform` sub-package turns `BoundValue`s into `TypedValue`s
while preserving the original bbox, page, and source-item provenance.

```mermaid
flowchart LR
    FR[FusionResult] --> B[bind_provenance]
    B --> BV[list BoundValue]
    BV --> S[Schema.apply]
    FR --> S
    S --> TV[dict TypedValue]
    TV --> T[TypedValue.trace]
    FR --> T
    T --> PT[ProvenanceTrace]
```

A `TypedValue` carries:

- `normalized` — the typed payload (e.g. a `date`, `Decimal`, `Money`, `bool`)
- `raw` — the original string the LLM produced
- `bbox`, `page`, `source_items` — copied verbatim from the `BoundValue`
- `confidence` — combined `match_score * transform_score`
- `issues` — typed flags such as `nif_checksum_mismatch`, `invalid_date`,
  `currency_ambiguous`, `required_field_missing`

Transformers are pure functions: `(raw, *, context) -> (normalized, score,
issues)`. The optional `TransformContext` carries the upstream `BoundValue`
and the full `FusionResult`, which is what lets checkbox transformers read
`VisualRect.is_filled`.

## Provenance traceability

`TypedValue.trace(fusion_result)` returns a `ProvenanceTrace` whose `chains`
walk every source `FusedItem` back to:

- the `LiteItem`s that produced the text (font name and size are recoverable),
- the `DoclingBlock` whose semantics matched (e.g. `list_item`, `table_cell`),
- the enclosing `VisualRect`,
- the `TableCellRef` when the item lives in a detected table (with row/column
  headers materialized from the table's first row and column),
- a `section_path` that walks up nested boxes.

This makes "show me the exact pixels and font that produced this typed
value" a one-liner.

## Pipeline orchestration (v0.4.0)

The `Pipeline` class wraps fuse → LLM → bind → schema → trace into a single
`run(pdf_path)` call.

```mermaid
flowchart TD
    PDF[PDF file] --> F[fuse three engines]
    F --> CTX[build_llm_context<br/>drop furniture, group by section]
    CTX --> P[build_extraction_prompt]
    P --> LLM[LLMProvider.complete<br/>OpenRouter / Gemini / Claude / OpenAI]
    LLM --> J[parse JSON]
    J --> B[bind_provenance]
    B --> H{hallucinations<br/>or low conf?}
    H -- yes, retry --> P
    H -- no --> V[detect issues]
    V --> S[Schema.apply]
    S --> ER[ExtractionResult<br/>typed_fields + cost + trace]
```

Cache lookup happens before fusion: the key is the SHA256 of the PDF bytes
plus the schema repr plus the LLM model identifier. A cache hit returns the
prior `ExtractionResult` with `cache_hit=True` and no LLM call.

Retries apply to the LLM call only: transient errors
(`LLMRateLimitError`, `LLMTimeoutError` by default) are retried with linear
or exponential backoff.

The re-prompt step is opt-in via the `Pipeline` constructor:

- `on_hallucination="retry_llm"` — if any field's value cannot be located
  in the source, prompt the LLM again with a stricter instruction.
- `on_low_confidence_field=0.7` — if any field matched below this score,
  re-prompt for those fields specifically.

See [providers.md](providers.md) for the provider matrix.

## Deterministic mode (v0.6.0)

When the schema fields can be located by label heuristics, `Pipeline(llm=None)`
runs the full pipeline without contacting any LLM. The LLM-specific phases
(`build_context` -> `llm_call` -> `parse_response` -> `bind_provenance` ->
`detect_issues`) are replaced by a single `pair_fields` step backed by the
`docomestria.pipeline.deterministic` module.

```mermaid
flowchart LR
    PDF[PDF file] --> F[fuse three engines]
    F --> PF[pair_fields<br/>label-based pairing + checkbox rects]
    PF --> S[Schema.apply]
    S --> ER[ExtractionResult<br/>cost.usd=0.0, model_used=deterministic]
```

Pairing rules per field:

1. Resolve label hints from `Field(labels=...)` or infer from the schema key's
   last segment (e.g. `"datos_titular.nif"` -> `("Datos de titular nif", ...)`,
   `"nif"` -> `("Nif",)`).
2. Find a label item whose normalized text equals one of the hints, preferring
   matches inside an enclosing box whose section title mentions the field path.
3. For text fields, take the next FusedItem to the right on the same row
   (delta_y < 8 pt), or the next item directly below.
4. For `checkbox_choice` / `checkbox_binary` transformers, locate each declared
   option label inside the same box and pick the option whose nearest
   `VisualRect` is filled.

Required fields with no pairing emit a `ProvenanceIssue` with
`issue_type="missing_required"` and `severity="high"`. `BoundValue.match_method`
is `"deterministic_pair"`.

The deterministic path is reproducible, offline-capable, and free — but it
will not handle free-text contracts, scanned PDFs, or forms where labels and
values do not share a visual relationship. Pick the LLM mode for those.
