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
