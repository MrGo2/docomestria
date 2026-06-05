# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-06-05

### Added
- Deterministic mode: `Pipeline(llm=None)` runs end-to-end without any LLM call.
  Uses label-based field pairing (`"NIF:"` -> next item to the right) plus
  checkbox detection from pdfplumber VisualRects. Free, instant, offline-capable,
  reproducible.
- `Field(transform, labels=(...))` — explicit label hints for deterministic pairing.
  If omitted, hints are inferred from the schema key's last segment via the new
  `infer_labels_from_key()` helper.
- New stream step `pair_fields` (engine="pairing") replacing the LLM steps
  when running deterministically — total of 9 canonical steps vs 13 with LLM.
- `examples/deterministic_extraction.py`
- New module `docomestria.pipeline.deterministic` for the pairing logic.

### Changed
- `CostReport` now carries `usd=0.0` and `model_used="deterministic"` in the
  LLM-free path (the dataclass already accepted these values).
- README leads with the deterministic quickstart; OpenRouter section follows.

## [0.5.0] - 2026-06-05

### Added
- `Pipeline.stream(pdf_path)` yields `PipelineStep` per phase for observable
  step-by-step execution (foundation for the upcoming `docomestria-studio`
  viewer).
- `PipelineStep` dataclass with `name`, `title`, ES/EN `explanation`,
  `engine`, `step_index` / `total_steps`, `elapsed_ms` / `cumulative_ms`,
  `bboxes` touched, partial state (`fusion`, `bound`, `issues`,
  `typed_fields`), and a `progress` property.
- `Pipeline.step_callback` optional callback fired for every step in both
  `run()` and `stream()` (observability without changing API style).
- `Pipeline.parallel_extract` flag — when `True`, surface a single bundled
  `extract_all` step instead of three sequential extract steps.
- 13 canonical step names with ES/EN explanations, plus a `cache_hit`
  short-circuit step when the result is already cached.

### Changed
- `Pipeline.run()` is now internally implemented on top of `stream()`. No
  external API change — same `ExtractionResult` returned. Verified by
  regression tests against the v0.4.0 behaviour.

## [0.4.0] - 2026-06-05

### Added
- `docomestria.pipeline` orchestrator — `Pipeline` class that runs
  fuse → LLM → bind → schema in one call.
- OpenRouter provider as the recommended default (one API key, 200+ models,
  built-in fallback chains, accurate per-call cost reporting via OpenRouter's
  `usage.cost` field).
- Native providers: `GeminiFlashLite`, `Claude`, `OpenAINative` for users who
  prefer direct SDKs. All SDK imports are lazy.
- `RetryPolicy` with `none`/`linear`/`exponential` backoff for transient
  `LLMRateLimitError` / `LLMTimeoutError`.
- `DiskCache` and `MemoryCache` backends keyed by
  (pdf SHA256, schema repr, model id).
- `ExtractionResult` with cost tracking (tokens + USD), `duration_ms`,
  `cache_hit`, and `llm_calls` counters; `.trace(field)` convenience.
- Re-prompt logic for hallucinations (`on_hallucination="retry_llm"`) and
  low-confidence fields (`on_low_confidence_field=<threshold>`).
- `examples/openrouter_pipeline.py` showing end-to-end usage.
- New `openrouter` optional dependency group (reuses the `openai` SDK).
- `docs/providers.md` comparing OpenRouter vs native providers.

### Changed
- README now leads with the OpenRouter quickstart — native providers
  documented as alternatives.
- Top-level `docomestria` package re-exports `Pipeline`, `ExtractionResult`,
  `RetryPolicy`, and `CostReport` lazily so the core import stays light.

## [0.3.1] - 2026-06-05

### Changed
- All dependencies pinned to latest stable versions with explicit upper bounds
  before next major release to prevent silent breakage:
  `liteparse>=2.0.5,<3`, `docling>=2.97,<3`, `pdfplumber>=0.11.9,<1`,
  `rapidfuzz>=3.14,<4`, `python-dateutil>=2.9,<3`, `python-stdnum>=2.2,<3`,
  `babel>=2.18,<3`, `phonenumbers>=9.0,<10`.

### Added
- New optional dependency groups in preparation for the v0.4.0 pipeline
  orchestrator: `pipeline` (`diskcache`), `gemini` (`google-genai>=2.8`),
  `claude` (`anthropic>=0.105`), `openai` (`openai>=2.41`).

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

[Unreleased]: https://github.com/MrGo2/docomestria/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/MrGo2/docomestria/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/MrGo2/docomestria/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/MrGo2/docomestria/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/MrGo2/docomestria/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/MrGo2/docomestria/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MrGo2/docomestria/releases/tag/v0.1.0
