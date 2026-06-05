"""FusionResult container + provenance traceability.

`FusionResult` is the v0.3.0 return type of `fuse()` — it carries the fused
items plus every engine-level item used to produce them (LiteItem,
DoclingBlock, VisualRect) so downstream code can walk the provenance chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import BBox, DoclingBlock, FusedItem, LiteItem, VisualRect

if TYPE_CHECKING:  # pragma: no cover
    from .llm.models import BoundValue
    from .transform.models import TypedValue


@dataclass(frozen=True)
class TableCellRef:
    """Reference to a single cell in a detected table."""

    table_id: str
    row: int
    col: int
    cell_bbox: BBox
    header_row: tuple[str, ...] | None = None
    header_col: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ProvenanceChain:
    """For a single FusedItem, what each engine contributed.

    `section_path` walks up nested boxes (innermost first → outermost last).
    """

    fused_item: FusedItem
    lite_items: tuple[LiteItem, ...]
    docling_block: DoclingBlock | None
    visual_box: VisualRect | None
    table_cell: TableCellRef | None
    section_path: tuple[str, ...]


@dataclass(frozen=True)
class ProvenanceTrace:
    """For a TypedValue, the full chain from typed value back to source items."""

    typed_value: "TypedValue"
    bound_value: "BoundValue | None"
    chains: tuple[ProvenanceChain, ...]
    page: int | None


@dataclass(frozen=True)
class FusionResult:
    """v0.3.0 fuse() return type.

    Carries the fused items plus the per-engine source data so callers can
    walk the provenance chain. Stats fields stay accessible for backward
    compatibility with v0.2.0's `fusion.FusionResult`.
    """

    items: tuple[FusedItem, ...]
    lite_items: tuple[LiteItem, ...]
    docling_blocks: tuple[DoclingBlock, ...]
    visual_rects: tuple[VisualRect, ...]
    coverage: float = 0.0
    matched_to_docling: int = 0
    matched_to_box: int = 0
    total_items: int = 0

    # --- Lookup helpers ----------------------------------------------------

    def get_item(self, item_id: str) -> FusedItem:
        """Look up a FusedItem by its string index (as used in BoundValue.source_items)."""
        idx = int(item_id)
        return self.items[idx]

    def get_box(self, rect_id: str) -> VisualRect:
        """Look up a VisualRect by `rect_id`. Raises KeyError if missing."""
        for r in self.visual_rects:
            if r.rect_id == rect_id:
                return r
        raise KeyError(f"no rect with rect_id={rect_id!r}")

    def get_table(self, table_id: str) -> VisualRect:
        """Look up a detected table (VisualRect with rect_type='table') by id."""
        for r in self.visual_rects:
            if r.rect_id == table_id and r.rect_type == "table":
                return r
        raise KeyError(f"no table with id={table_id!r}")

    def items_in_box(self, rect_id: str) -> tuple[FusedItem, ...]:
        """All FusedItems whose enclosing_box_id matches `rect_id`."""
        return tuple(it for it in self.items if it.enclosing_box_id == rect_id)

    def items_in_table_cell(self, table_id: str, row: int, col: int) -> tuple[FusedItem, ...]:
        """All FusedItems that landed in a specific table cell."""
        return tuple(
            it
            for it in self.items
            if it.table_id == table_id and it.table_row == row and it.table_col == col
        )

    def resolve(self, item: FusedItem) -> ProvenanceChain:
        """Build a ProvenanceChain for `item` — looks up source LiteItems,
        the matching DoclingBlock, the enclosing VisualRect, and any table cell.
        """
        return _build_chain(item, self)


# --- Internal helpers -----------------------------------------------------


def _lite_items_for(item: FusedItem, fr: FusionResult) -> tuple[LiteItem, ...]:
    """Match by (page, bbox tuple) — FusedItem inherits LiteItem's bbox unchanged."""
    matches: list[LiteItem] = []
    target = item.bbox.as_tuple()
    for li in fr.lite_items:
        if li.page != item.page:
            continue
        if li.bbox.as_tuple() == target and li.text == item.text:
            matches.append(li)
    return tuple(matches)


def _docling_for(item: FusedItem, fr: FusionResult) -> DoclingBlock | None:
    if item.docling_label is None:
        return None
    cx, cy = item.bbox.centroid
    candidates = [
        blk
        for blk in fr.docling_blocks
        if blk.page == item.page
        and blk.label == item.docling_label
        and blk.bbox.contains_point(cx, cy)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda b: b.bbox.area)


def _visual_box_for(item: FusedItem, fr: FusionResult) -> VisualRect | None:
    if item.enclosing_box_id is None:
        return None
    for r in fr.visual_rects:
        if r.rect_id == item.enclosing_box_id:
            return r
    return None


def _table_cell_ref(item: FusedItem, fr: FusionResult) -> TableCellRef | None:
    if item.table_id is None or item.table_row is None or item.table_col is None:
        return None
    if item.cell_bbox is None:
        return None
    headers_row: tuple[str, ...] | None = None
    headers_col: tuple[str, ...] | None = None
    try:
        table = fr.get_table(item.table_id)
    except KeyError:
        table = None
    if table is not None and table.table_grid is not None and table.table_grid:
        # Column headers — items in row 0 of this table.
        cells_row_0 = table.table_grid[0]
        headers_row = tuple(
            _join_text(fr.items_in_table_cell(item.table_id, 0, c)) for c in range(len(cells_row_0))
        )
        headers_col = tuple(
            _join_text(fr.items_in_table_cell(item.table_id, r, 0))
            for r in range(len(table.table_grid))
        )
    return TableCellRef(
        table_id=item.table_id,
        row=item.table_row,
        col=item.table_col,
        cell_bbox=item.cell_bbox,
        header_row=headers_row,
        header_col=headers_col,
    )


def _join_text(items: tuple[FusedItem, ...]) -> str:
    return " ".join(it.text for it in items if it.text).strip()


def _section_path(item: FusedItem, fr: FusionResult) -> tuple[str, ...]:
    """Walk up nested boxes; innermost first → outermost last."""
    path: list[str] = []
    if item.section_title:
        path.append(item.section_title)
    # Walk up via containing rects on the same page.
    box = _visual_box_for(item, fr)
    if box is None:
        return tuple(path)
    seen: set[str] = {box.rect_id}
    cur_bbox = box.bbox
    while True:
        parent: VisualRect | None = None
        parent_area = float("inf")
        for r in fr.visual_rects:
            if r.page != item.page or r.rect_id in seen or r.rect_type == "checkbox":
                continue
            if (
                r.bbox.contains(cur_bbox)
                and r.bbox.area > cur_bbox.area
                and r.bbox.area < parent_area
            ):
                parent = r
                parent_area = r.bbox.area
        if parent is None:
            break
        # Find a title for this parent box: largest-font item inside it.
        title_items = fr.items_in_box(parent.rect_id)
        if title_items:
            title = max(title_items, key=lambda it: it.font_size or 0.0)
            if title.text and title.text not in path:
                path.append(title.text)
        seen.add(parent.rect_id)
        cur_bbox = parent.bbox
    return tuple(path)


def _build_chain(item: FusedItem, fr: FusionResult) -> ProvenanceChain:
    return ProvenanceChain(
        fused_item=item,
        lite_items=_lite_items_for(item, fr),
        docling_block=_docling_for(item, fr),
        visual_box=_visual_box_for(item, fr),
        table_cell=_table_cell_ref(item, fr),
        section_path=_section_path(item, fr),
    )


def build_trace(typed_value: "TypedValue", fr: FusionResult) -> ProvenanceTrace:
    """Implementation behind `TypedValue.trace()`."""
    chains: list[ProvenanceChain] = []
    for sid in typed_value.source_items:
        try:
            item = fr.get_item(sid)
        except (ValueError, IndexError):
            continue
        chains.append(_build_chain(item, fr))
    bound_value = None  # We don't keep a back-reference; chains carry the items.
    return ProvenanceTrace(
        typed_value=typed_value,
        bound_value=bound_value,
        chains=tuple(chains),
        page=typed_value.page,
    )


__all__ = [
    "FusionResult",
    "ProvenanceChain",
    "ProvenanceTrace",
    "TableCellRef",
    "build_trace",
]
