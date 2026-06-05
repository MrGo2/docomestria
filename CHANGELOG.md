# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-06-05

### Added
- `docomestria.transform` for typed extraction with ES/EU format support
  (dates, amounts, NIF, NIE, CIF, IBAN, BIC, phone, email, URL, postal
  codes, provinces, percentages, checkboxes).
- `TypedValue` dataclass with bbox/page/source_items preserved through
  normalization, plus per-value `confidence` and `issues`.
- `Schema` and `Field` for declarative typed extraction; `Schema.apply()`
  runs every transformer against a list of `BoundValue`s.
- Table detection in the pdfplumber engine — `FusedItem` now carries
  `table_id`, `table_row`, `table_col`, and `cell_bbox`. `VisualRect`
  gained `rect_type` (`"box" | "table" | "checkbox" | "signature_field"`)
  and `table_grid`.
- `FusionResult` container with lookup helpers: `get_item`, `get_box`,
  `get_table`, `items_in_box`, `items_in_table_cell`, `resolve`.
- `TypedValue.trace()` returns a `ProvenanceTrace` walking the full chain
  back to the LiteItems, DoclingBlock, VisualRect, and table cell that
  produced the value.
- `examples/typed_extraction.py` — end-to-end Spanish contract scenario.
- Optional dependency group: `pip install docomestria[transform]`.

### Changed
- BREAKING: `fuse(pdf)` now returns `FusionResult` instead of
  `list[FusedItem]`. Migration: use `fuse(pdf).items` to recover the old
  list. `fuse_from_engines()` now returns `FusionStats` (the prior
  in-module `FusionResult`).
- `VisualRect` gained `rect_type` and `table_grid` (default `"box"` and
  `None`, so existing callers keep working).
- `FusedItem` gained `table_id`, `table_row`, `table_col`, `cell_bbox`
  (all default `None`).

## [0.2.0] - 2026-06-05

### Added
- `docomestria.llm` optional sub-package for LLM output provenance binding.
- `bind_provenance()` maps LLM-extracted values back to `FusedItem`s via
  exact, substring, and fuzzy matching (powered by `rapidfuzz`).
- `detect_hallucinations()` flags values that don't appear in the source PDF.
- `detect_role_mismatches()` flags values bound to suspicious semantic roles
  (e.g. `section_header`, `title`, `page_footer`).
- Frozen dataclasses `BoundValue` and `ProvenanceIssue`.
- `examples/with_gemini.py` showing the end-to-end pattern (LLM-agnostic).
- Optional dependency group: install with `pip install docomestria[llm]`.

## [0.1.0] - 2026-06-05

### Added
- Initial public release.
- Three-engine fusion: LiteParse v2, Docling, pdfplumber.
- Frozen-dataclass models: `BBox`, `LiteItem`, `DoclingBlock`, `VisualRect`, `FusedItem`.
- Geometry utilities: centroid, IoU, containment.
- `fuse()` orchestrator: smallest-containing-block matching with IoU fallback.
- Enclosing-box detection from pdfplumber rectangles, with section-title inference.
- Checkbox detection (visual rectangles in a square-ish range).
- Optional `pair_labels_to_values()` helper for form-like layouts.
- Examples and architecture documentation.

[Unreleased]: https://github.com/MrGo2/docomestria/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/MrGo2/docomestria/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/MrGo2/docomestria/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MrGo2/docomestria/releases/tag/v0.1.0
