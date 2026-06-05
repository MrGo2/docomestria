"""Top-level orchestrator: PDF path → StructuralExtraction.

Runs the three engines, classifies, detects structure, emits candidates,
scores+dedups, and assembles the final result. No LLM, no regex per field,
no ML beyond what the engines themselves use internally.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..engines import (
    extract_docling_blocks,
    extract_lite_items,
    extract_visual_rects,
)
from ..models import DoclingBlock, LiteItem, VisualRect
from .candidates import emit_all
from .classify import classify
from .models import Page, Pair, StructuralExtraction
from .scoring import resolve_pairs
from .structure import detect_structure


def _section_title_for(page: Page, pair: Pair) -> str | None:
    """The deepest open Section whose Y range contains the pair's label.

    Sections close at the next section of equal or shallower level. We walk
    them in reading order and keep the last one whose top is above the pair.
    """
    current: str | None = None
    for sec in page.sections:
        if sec.bbox.top <= pair.label_bbox.top:
            current = sec.title
        else:
            break
    return current


def structural_extract_from_engines(
    docling_blocks: Iterable[DoclingBlock],
    lite_items: Iterable[LiteItem],
    plumber_rects: Iterable[VisualRect],
) -> StructuralExtraction:
    """Same as `structural_extract` but takes the engines' outputs directly.

    Useful for tests and for callers that already ran the engines (e.g. for
    caching or alternative engine implementations).
    """
    docling_blocks = tuple(docling_blocks)
    lite_items = tuple(lite_items)
    plumber_rects = tuple(plumber_rects)

    classified = classify(lite_items)
    pages = detect_structure(docling_blocks, lite_items, plumber_rects)
    candidates = emit_all(classified, pages)
    pairs = resolve_pairs(candidates)

    # Backfill section_title on each pair using the page's section list.
    pages_by_no = {p.number: p for p in pages}
    enriched: list[Pair] = []
    for pair in pairs:
        page = pages_by_no.get(pair.page)
        section_title = _section_title_for(page, pair) if page else None
        enriched.append(
            Pair(
                label_text=pair.label_text,
                value_text=pair.value_text,
                label_bbox=pair.label_bbox,
                value_bbox=pair.value_bbox,
                page=pair.page,
                score=pair.score,
                confidence=pair.confidence,
                evidence=pair.evidence,
                section_title=section_title,
                subsection_title=pair.subsection_title,
                column_index=pair.column_index,
            )
        )

    return StructuralExtraction(
        pages=pages,
        pairs=tuple(enriched),
        classified=classified,
    )


def structural_extract(pdf_path: str | Path) -> StructuralExtraction:
    """Run the full structural extraction over a PDF on disk.

    Steps:
      1. Run Docling, LiteParse, and pdfplumber (cold — no caching here).
      2. Classify every LiteParse item.
      3. Detect page structure (sections, tables, sub-sections, exclusions).
      4. Emit pair candidates from each emitter (D-2col / inline / horizontal).
      5. Score, dedup, and resolve to final Pairs.
      6. Backfill section titles and return the StructuralExtraction.
    """
    pdf_path = str(pdf_path)
    return structural_extract_from_engines(
        extract_docling_blocks(pdf_path),
        extract_lite_items(pdf_path),
        extract_visual_rects(pdf_path),
    )
