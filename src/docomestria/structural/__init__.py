"""Structural key-value extraction — v0.7.0.

Auto-discovered key-value pairs and hierarchical structure from a PDF using
three signals only: position (pdfplumber), structure (Docling), and format
(LiteParse). No LLMs, no regex-based field guessing.

Public API (filled out as sub-modules land):

    from docomestria.structural import (
        ItemKind, Confidence,
        ClassifiedItem, Section, Box, Subsection, Table,
        PairCandidate, Pair, Page, StructuralExtraction,
    )

The top-level entry point `structural_extract(pdf_path)` is added by
`extractor.py` once the classify / structure / pairing / scoring stages exist.
"""

from __future__ import annotations

from .candidates import (
    emit_all,
    emit_from_docling_tables,
    emit_from_horizontal_pair,
    emit_from_in_item_split,
    emit_from_two_column_form,
    emit_from_vertical_pair,
)
from .classify import classify, classify_page, dominant_font_size, is_bold
from .extractor import structural_extract, structural_extract_from_engines
from .scoring import confidence_for, resolve_pairs, score_one
from .structure import (
    attach_subsections,
    detect_boxes,
    detect_furniture_regions,
    detect_picture_regions,
    detect_prose_regions,
    detect_sections,
    detect_structure,
    detect_tables,
)
from .models import (
    Box,
    ClassifiedItem,
    Confidence,
    ItemKind,
    Page,
    Pair,
    PairCandidate,
    Section,
    StructuralExtraction,
    Subsection,
    Table,
)

__all__ = [
    "Box",
    "ClassifiedItem",
    "Confidence",
    "ItemKind",
    "Page",
    "Pair",
    "PairCandidate",
    "Section",
    "StructuralExtraction",
    "Subsection",
    "Table",
    "attach_subsections",
    "classify",
    "classify_page",
    "confidence_for",
    "detect_boxes",
    "detect_furniture_regions",
    "detect_picture_regions",
    "detect_prose_regions",
    "detect_sections",
    "detect_structure",
    "detect_tables",
    "dominant_font_size",
    "emit_all",
    "emit_from_docling_tables",
    "emit_from_horizontal_pair",
    "emit_from_in_item_split",
    "emit_from_two_column_form",
    "emit_from_vertical_pair",
    "is_bold",
    "resolve_pairs",
    "score_one",
    "structural_extract",
    "structural_extract_from_engines",
]
