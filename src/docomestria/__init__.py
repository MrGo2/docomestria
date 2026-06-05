"""Docomestria — fuse LiteParse v2, Docling, and pdfplumber into a single PDF view."""

from __future__ import annotations

from .fusion import FusionStats, fuse, fuse_from_engines
from .models import BBox, DoclingBlock, FusedItem, LiteItem, VisualRect
from .pairing import pair_labels_to_values
from .result import FusionResult, ProvenanceChain, ProvenanceTrace, TableCellRef

__all__ = [
    "BBox",
    "DoclingBlock",
    "FusedItem",
    "FusionResult",
    "FusionStats",
    "LiteItem",
    "ProvenanceChain",
    "ProvenanceTrace",
    "TableCellRef",
    "VisualRect",
    "fuse",
    "fuse_from_engines",
    "pair_labels_to_values",
]

__version__ = "0.3.0"
