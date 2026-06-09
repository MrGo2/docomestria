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
from ..models import BBox, DoclingBlock, LiteItem, VisualRect
from .candidates import emit_all
from .classify import classify
from .ilp import resolve_conflicts
from .models import Page, Pair, StructuralExtraction
from .scoring import resolve_pairs
from .structure import detect_structure
from .typing import coerce_value

# --- False-positive pair suppression ---------------------------------------
# Sibling to `_is_false_positive_plumber_table` (structure.py): three
# independent signals each mark a junk KV pair seen in real output. The
# predicate runs once per pair at the post-scoring chokepoint, before global
# conflict resolution, so junk never wins an ILP tie-break.

_VERTICAL_ASPECT = 1.5  # bbox h > w * this (for multi-char text) ⇒ rotated text
_MIN_SLIVER_CHARS = 3  # need a few chars before judging orientation


def _has_control_chars(s: str) -> bool:
    """True if `s` holds a C0/C1 control char (excluding ``\\t \\n \\r``).

    Catches garbage values like ``\\x9f (*) Comisión Estudio``; the euro sign
    (U+20AC) and ordinary whitespace are intentionally allowed.
    """
    return any((ord(c) < 0x20 and c not in "\t\n\r") or 0x7F <= ord(c) <= 0x9F for c in s)


def _is_vertical_sliver(text: str, bbox: BBox) -> bool:
    """True if multi-char `text` sits in a taller-than-wide bbox (rotated text).

    Genuine horizontal lines are wide and short (``w >> h``), so the guard
    ``h > w * _VERTICAL_ASPECT`` can only fire on text rendered vertically —
    e.g. form-template ``Date``/``Guid`` stamps in the page margin.
    """
    if len(text.strip()) < _MIN_SLIVER_CHARS:
        return False
    if bbox.w <= 0:
        return False
    return bbox.h > bbox.w * _VERTICAL_ASPECT


def _is_title_case_phrase(text: str) -> bool:
    """True if `text` is a multi-word phrase that opens Title-Case
    (initial uppercase + lowercase tail), e.g. ``Comisión apertura``.

    Excludes all-caps form values (``LAS PALMAS``) and single words (``Madrid``).
    """
    t = text.strip()
    if len(t) < 2 or len(t.split()) < 2:
        return False
    if t == t.upper():  # all-caps form field, not a header phrase
        return False
    return t[0].isupper() and t[1].islower()


def _is_header_glue(label: str, value: str) -> bool:
    """True if a colon-split pair is really two glued column headers.

    Both sides must be plain strings (neither coerces to date/amount/percent/
    nif/bool via `coerce_value`) and the value must be a multi-word Title-Case
    header phrase with no terminal punctuation. Mirrors the real
    ``No Financiadas → Comisión apertura`` artifact while sparing genuine pairs
    like ``Lugar → LAS PALMAS`` (all-caps), ``05-06-2024 → 273,23€`` (typed),
    and sentence values.
    """
    v = value.strip()
    if not v or v[-1] in ".!?":
        return False
    if coerce_value(label).kind != "string" or coerce_value(value).kind != "string":
        return False
    return _is_title_case_phrase(v)


def _is_false_positive_pair(p: Pair) -> bool:
    """Suppress junk KV pairs matching known false-positive patterns.

    Three independent signals (any one suppresses):
      A. control chars in label/value text — OCR/template garbage.
      B. either side is a vertical-margin sliver — rotated form metadata.
      C. header-on-header glue — gated to single-rule ``L-inline-split`` pairs
         (no cross-engine support) so a corroborated pair is never dropped.
    """
    if _has_control_chars(p.label_text) or _has_control_chars(p.value_text):
        return True
    if _is_vertical_sliver(p.value_text, p.value_bbox) or _is_vertical_sliver(
        p.label_text, p.label_bbox
    ):
        return True
    return p.evidence == ("L-inline-split",) and _is_header_glue(p.label_text, p.value_text)


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
    # Drop false-positive pairs (control-char garbage, rotated margin metadata,
    # header-on-header glue) before conflict resolution so junk never wins a
    # tie-break. Mirrors `_is_false_positive_plumber_table` in structure.py.
    pairs = tuple(p for p in pairs if not _is_false_positive_pair(p))
    # Global ILP-style conflict resolution (sección 6.5) — drops same-page,
    # same-label pairs without a distinguishing column_index. Keeps the
    # highest-scoring candidate per conflict group.
    pairs = resolve_conflicts(pairs)

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
