"""Data model for structural key-value extraction.

All types are frozen dataclasses. Mutating an extraction means returning a new
copy. The shape mirrors the v0.7.0 handoff:

    StructuralExtraction(pages=[...], pairs=[...])
        pages   -> per-page hierarchy: Section / Box / Table / Subsection
        pairs   -> flat list of detected key-value pairs with confidence + evidence

Every Pair and PairCandidate carries `evidence: tuple[str, ...]` — a frozen
list of rule identifiers that contributed to the decision, so any final pair
can be traced back to *why* it was emitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..models import BBox, LiteItem


class ItemKind(str, Enum):
    """Classification of a single LiteItem within the page context.

    Values are strings so that JSON serialization stays human-readable and
    diffable. Don't add a sub-classification here — that belongs in evidence.
    """

    TITLE = "title"           # bold + font_size > page median; standalone (no value on same Y)
    LABEL = "label"           # bold (with or without ":"), candidate for the left of a pair
    VALUE = "value"           # regular font; candidate for the right/below of a pair
    BODY = "body"             # free-text paragraph, footer, etc. — not part of any pair
    UNKNOWN = "unknown"       # could not classify confidently


class Confidence(str, Enum):
    """Coarse confidence band for a pair. Mapped from numeric score in scoring.py."""

    HIGH = "high"             # >= 0.80 — multiple signals agree (bold + ":" + same row)
    MEDIUM = "medium"         # 0.50–0.79 — at least one strong signal but some ambiguity
    LOW = "low"               # < 0.50 — emitted for inspection, do not trust


@dataclass(frozen=True)
class ClassifiedItem:
    """A LiteItem enriched with its detected kind + the evidence that decided it."""

    item: LiteItem
    kind: ItemKind
    evidence: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return self.item.text

    @property
    def bbox(self) -> BBox:
        return self.item.bbox

    @property
    def page(self) -> int:
        return self.item.page


@dataclass(frozen=True)
class Section:
    """A logical section opened by a Docling section_header.

    Sections are pure positional groupings — every item whose centroid Y falls
    between this section's header_y and the next section's header_y belongs to
    it. The structural extractor uses sections to scope label/value pairing so
    a label cannot pair with a value across a section boundary.
    """

    title: str
    level: int
    bbox: BBox
    page: int


@dataclass(frozen=True)
class Box:
    """A pdfplumber-detected rect that is NOT a table (rect_type == 'box').

    Boxes are visual containers — labelled blocks like "Datos Petición" or
    sub-section headers like "Situaciones". The pairing stage uses boxes
    inside tables as horizontal split lines (Rule 4 — subsection_split).
    """

    bbox: BBox
    page: int
    rect_id: str = ""


@dataclass(frozen=True)
class Subsection:
    """A horizontal split of a parent Table.

    Created by `structure.py` when a sub-header box is detected inside a table
    (Rule 4). `header_text` is the title that lives inside `header_bbox`;
    `body_bbox` is the area between this subsection's header and the next.
    """

    header_text: str
    header_bbox: BBox
    body_bbox: BBox
    page: int


@dataclass(frozen=True)
class Table:
    """A logical table region.

    May come from Docling (TableFormer), from pdfplumber (visual grid), or
    from a fusion of both. `source` names the origin and `cells` are taken
    from whichever engine has the most reliable matrix for this region:
    Docling when both detected the same area, otherwise the only engine
    that saw it.

    `subsections` is populated by `structure.py` (Rule 4 — box rect with
    table-width nested inside this table = horizontal split). An empty
    tuple means the table has no sub-headers (single logical block).
    """

    bbox: BBox
    page: int
    rect_id: str = ""
    cells: tuple[tuple[str, ...], ...] | None = None
    subsections: tuple[Subsection, ...] = ()
    source: str = "fused"   # "docling" | "pdfplumber" | "fused"


@dataclass(frozen=True)
class PairCandidate:
    """A proposed (label, value) pair before scoring + deduplication.

    Always carries the resolved text + bbox for both sides — every emitter
    (Docling cells, in-item split, geometric pairing) lands in this same
    shape. `features` is an open dict consumed by `scoring.py`. `rule`
    identifies the emitter ("D-2col", "L-inline-split", "L-horizontal", ...).
    `label_item` / `value_item` link back to the source ClassifiedItem when
    one exists (LiteParse-based rules); they are None for emitters that
    don't have a per-item source (e.g. Docling cells where we only have the
    table's text matrix, not item-level bboxes).
    """

    label_text: str
    value_text: str
    label_bbox: BBox
    value_bbox: BBox
    page: int
    rule: str
    features: dict[str, float | bool | int | str] = field(default_factory=dict)
    label_item: ClassifiedItem | None = None
    value_item: ClassifiedItem | None = None
    column_index: int | None = None


@dataclass(frozen=True)
class Pair:
    """Final emitted key-value pair after scoring + dedup.

    `evidence` lists every rule that supported this pair (often a single rule;
    when 2+ rules agree, the confidence is bumped). `score` is the raw 0..1
    output of scoring.py; `confidence` is its banded form for end-users.
    """

    label_text: str
    value_text: str
    label_bbox: BBox
    value_bbox: BBox
    page: int
    score: float
    confidence: Confidence
    evidence: tuple[str, ...]
    section_title: str | None = None
    subsection_title: str | None = None
    column_index: int | None = None


@dataclass(frozen=True)
class Page:
    """One page's worth of structural detections.

    `furniture_regions` and `picture_regions` are downstream-filter bboxes —
    any LiteParse item whose centroid falls inside one of these is excluded
    from KV pairing (page footer chrome, logos, etc.). Stored on Page rather
    than recomputed so candidates.py and extractor.py share one source of
    truth.
    """

    number: int
    sections: tuple[Section, ...] = ()
    boxes: tuple[Box, ...] = ()
    tables: tuple[Table, ...] = ()
    furniture_regions: tuple[BBox, ...] = ()
    picture_regions: tuple[BBox, ...] = ()
    prose_regions: tuple[BBox, ...] = ()


@dataclass(frozen=True)
class StructuralExtraction:
    """The full result returned by `structural_extract(pdf_path)`.

    `pairs` is the headline output — flat across all pages, ordered by page
    then by label Y. `pages` exposes the underlying hierarchy for callers who
    need it (e.g. studio's "Estructura detectada" view).
    """

    pages: tuple[Page, ...]
    pairs: tuple[Pair, ...]
    classified: tuple[ClassifiedItem, ...] = ()  # for debugging / studio view
