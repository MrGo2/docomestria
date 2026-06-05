"""Frozen dataclasses for the LLM provenance layer."""

from __future__ import annotations

from dataclasses import dataclass

from ..models import BBox


@dataclass(frozen=True)
class BoundValue:
    """A value extracted by an LLM, bound back to its source in the PDF.

    `source_items` holds opaque identifiers for the FusedItems that contain the
    value (we use the item index as a string, since `FusedItem` has no id field).
    `match_method` is one of: "exact" | "substring" | "fuzzy" | "not_found".
    `match_score` is in [0.0, 1.0]; 0.0 means the value could not be located.
    """

    field_name: str
    value: str
    source_items: tuple[str, ...]
    bbox: BBox | None
    section_title: str | None
    docling_label: str | None
    match_method: str
    match_score: float
    page: int | None


@dataclass(frozen=True)
class ProvenanceIssue:
    """A QA flag raised against a bound value."""

    field_name: str
    value: str
    issue_type: str  # "hallucination" | "role_mismatch" | "low_confidence"
    severity: str  # "high" | "medium" | "low"
    detail: str
