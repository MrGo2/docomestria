"""Frozen dataclasses for the public API. No mutation — return new copies."""

from __future__ import annotations

from dataclasses import dataclass

from . import geometry


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in PDF points, top-left origin (y grows downward)."""

    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def top(self) -> float:
        return self.y

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)

    @property
    def centroid(self) -> tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.left, self.top, self.right, self.bottom)

    def contains_point(self, x: float, y: float) -> bool:
        return geometry.contains_point(self.as_tuple(), x, y)

    def contains(self, other: "BBox", tol: float = 0.5) -> bool:
        return geometry.contains_box(self.as_tuple(), other.as_tuple(), tol=tol)

    def iou(self, other: "BBox") -> float:
        return geometry.iou(self.as_tuple(), other.as_tuple())

    @classmethod
    def from_ltrb(cls, l: float, t: float, r: float, b: float) -> "BBox":
        l, t, r, b = geometry.normalize_tl((l, t, r, b))
        return cls(x=l, y=t, w=r - l, h=b - t)


@dataclass(frozen=True)
class LiteItem:
    """One text item extracted by LiteParse v2."""

    text: str
    bbox: BBox
    font_name: str | None
    font_size: float | None
    page: int


@dataclass(frozen=True)
class DoclingBlock:
    """One semantic block from Docling.

    `cells` is populated only when this block represents a table — a rows x cols
    matrix of cell text. Best-effort: missing or unrecoverable cell content
    leaves `cells=None`.
    """

    bbox: BBox
    label: str
    heading_level: int | None
    content_layer: str  # "body" or "furniture"
    page: int
    text: str = ""
    self_ref: str | None = None
    cells: tuple[tuple[str, ...], ...] | None = None


@dataclass(frozen=True)
class VisualRect:
    """A vector rectangle detected by pdfplumber.

    `rect_type` is one of: "box" | "table" | "checkbox" | "signature_field".
    `table_grid` is the list of cell bboxes per row, only set when
    `rect_type == "table"`. `is_checkbox` is kept for backward compatibility
    with v0.2.0 callers but is equivalent to `rect_type == "checkbox"`.
    """

    bbox: BBox
    is_checkbox: bool
    is_filled: bool
    page: int
    rect_id: str = ""
    rect_type: str = "box"
    table_grid: tuple[tuple["BBox", ...], ...] | None = None
    cells: tuple[tuple[str, ...], ...] | None = None


@dataclass(frozen=True)
class FusedItem:
    """A LiteParse item enriched with Docling semantics and pdfplumber structure.

    When the item falls inside a detected table cell, `table_id`, `table_row`,
    `table_col`, and `cell_bbox` are populated.
    """

    text: str
    bbox: BBox
    font_name: str | None
    font_size: float | None
    docling_label: str | None
    docling_heading_level: int | None
    enclosing_box_id: str | None
    section_title: str | None
    page: int
    match_method: str  # "centroid" | "iou" | "none"
    match_score: float
    table_id: str | None = None
    table_row: int | None = None
    table_col: int | None = None
    cell_bbox: BBox | None = None
