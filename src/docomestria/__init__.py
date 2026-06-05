"""Docomestria — fuse LiteParse v2, Docling, and pdfplumber into a single PDF view."""

from __future__ import annotations

from .fusion import FusionStats, fuse, fuse_from_engines
from .models import BBox, DoclingBlock, FusedItem, LiteItem, VisualRect
from .pairing import pair_labels_to_values
from .result import FusionResult, ProvenanceChain, ProvenanceTrace, TableCellRef

__all__ = [
    "BBox",
    "CostReport",
    "DoclingBlock",
    "ExtractionResult",
    "FusedItem",
    "FusionResult",
    "FusionStats",
    "LiteItem",
    "Pipeline",
    "PipelineStep",
    "ProvenanceChain",
    "ProvenanceTrace",
    "RetryPolicy",
    "TableCellRef",
    "VisualRect",
    "fuse",
    "fuse_from_engines",
    "pair_labels_to_values",
]

__version__ = "0.6.2"


def __getattr__(name: str):
    """Lazy re-exports from the optional `pipeline` sub-package.

    Keeps `from docomestria import Pipeline` working without forcing the
    pipeline-only deps at core import time.
    """
    if name in {"Pipeline", "PipelineStep", "ExtractionResult", "RetryPolicy", "CostReport"}:
        from . import pipeline as _pipe

        return getattr(_pipe, name)
    raise AttributeError(f"module 'docomestria' has no attribute {name!r}")
