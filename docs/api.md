# API reference

All public types are importable from the top-level package.

```python
from docomestria import (
    BBox, LiteItem, DoclingBlock, VisualRect, FusedItem,
    FusionResult, fuse, fuse_from_engines, pair_labels_to_values,
)
```

## `fuse(pdf_path: str | Path) -> list[FusedItem]`

Run all three engines on `pdf_path` and return the fused list. This is the
quickest way to get going. Raises whatever the upstream engines raise.

## `fuse_from_engines(lite, docling, rects) -> FusionResult`

Pure-Python fusion over pre-extracted inputs. Useful when you want to:

- run the engines with custom options;
- swap in your own extractor that emits the same model shapes;
- unit-test fusion logic without touching disk.

`FusionResult` carries the items plus simple coverage statistics
(`coverage`, `matched_to_docling`, `matched_to_box`, `total_items`).

## `pair_labels_to_values(items) -> dict[str, str]`

Optional convenience for form layouts. For each label-like item (text ending
in `:`), finds the nearest item to the right on the same row inside the same
enclosing box. Skips labels with no matching value.

## Data models

All models are **frozen dataclasses**. To make a modified copy use
`dataclasses.replace(obj, field=value)`.

### `BBox`

Top-left origin in PDF points. Exposes `left`, `top`, `right`, `bottom`,
`area`, `centroid`, plus `contains_point`, `contains`, `iou`. Build one with
`BBox(x, y, w, h)` or `BBox.from_ltrb(l, t, r, b)`.

### `LiteItem`

`text`, `bbox`, `font_name`, `font_size`, `page`.

### `DoclingBlock`

`bbox`, `label`, `heading_level`, `content_layer`, `page`, `text`, `self_ref`.

### `VisualRect`

`bbox`, `is_checkbox`, `is_filled`, `page`, `rect_id`.

### `FusedItem`

Every field above relevant to a single text item, plus `docling_label`,
`docling_heading_level`, `enclosing_box_id`, `section_title`,
`match_method` (`"centroid"` | `"iou"` | `"none"`) and `match_score`.
