# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/MrGo2/docomestria/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MrGo2/docomestria/releases/tag/v0.1.0
