"""Detect page-level structure: sections, tables, sub-section splits, regions
to exclude from KV pairing (furniture and pictures).

This is the second stage of the pipeline (after `classify.py`, before
`candidates.py`). It consumes the three engines' raw outputs and produces a
`tuple[Page, ...]` — one `Page` per source page — that downstream stages can
walk to scope every emitted candidate to its containing section/table and to
mark cross-section pairings as illegal.

The MVP scope here matches the v0.7.0 judicial regression set (LABORAL +
PATRIMONIAL). Banking-contract extensions (prose suppression S6, two-column
form detection S7, dense-matrix detection S8) are deferred to a follow-up.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

from ..models import BBox, DoclingBlock, LiteItem, VisualRect
from .models import Box, Page, Section, Subsection, Table

# Two table bboxes are considered the *same* logical table when their IoU
# crosses this threshold. Docling and pdfplumber rarely agree to the pixel,
# so the threshold is loose. Borderline cases (0.3–0.5) are reported as
# separate tables — we'd rather double-count than fuse the wrong rect.
TABLE_FUSE_IOU = 0.5

# A pdfplumber `type=box` rect counts as a sub-section header for a table
# when their widths match within this many points. The boxes BBVA / PNJ use
# for sub-headers are full table width minus a thin border.
SUBHEADER_WIDTH_TOLERANCE_PT = 6.0

# Sub-header boxes are short — a single row. A box taller than this inside
# a table is more likely a body region than a header strip.
SUBHEADER_MAX_HEIGHT_PT = 30.0

# A Docling text block long enough to count as a prose paragraph. Calibrated
# from BBVA contracts: real KV labels live in tables or as short standalone
# strings; body paragraphs ("En consecuencia, en cada liquidación...") start
# around 100 chars. Set conservatively to avoid flagging short captions.
PROSE_TEXT_MIN_CHARS = 60

# A Docling list_item long enough to count as a clause sub-bullet. Lower
# than text-block because list items often pack a single thought into one
# line ("Cuota Sin nómina domiciliada: considerando el Interés...").
PROSE_LIST_ITEM_MIN_CHARS = 40


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _by_page(items: Iterable, *, attr: str = "page") -> dict[int, list]:
    """Group any iterable of objects-with-`.page` into a dict keyed by page."""
    out: dict[int, list] = {}
    for it in items:
        out.setdefault(getattr(it, attr), []).append(it)
    return out


def _bbox_contains(outer: BBox, inner: BBox, tol: float = 1.0) -> bool:
    """True if `inner` is nested inside `outer` (with a small slack)."""
    return (
        inner.left >= outer.left - tol
        and inner.right <= outer.right + tol
        and inner.top >= outer.top - tol
        and inner.bottom <= outer.bottom + tol
    )


def _intervals_between(splits: list[float], top: float, bottom: float) -> list[tuple[float, float]]:
    """Given a sorted list of Y splits inside [top, bottom], return the resulting
    [(y_start, y_end), ...] intervals.
    """
    bounds = [top, *splits, bottom]
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]


# --------------------------------------------------------------------------
# Section detection
# --------------------------------------------------------------------------


def detect_sections(docling_blocks: Iterable[DoclingBlock]) -> tuple[Section, ...]:
    """Build a `Section` for every Docling section_header on the page.

    Sections close implicitly at the next section_header of equal or shallower
    level, or at the end of the page — the closing logic lives in
    `candidates.py` when it scopes a pair; here we just record the openings
    in reading order.
    """
    sections: list[Section] = []
    for blk in docling_blocks:
        if blk.label != "section_header":
            continue
        sections.append(
            Section(
                title=(blk.text or "").strip(),
                level=blk.heading_level or 1,
                bbox=blk.bbox,
                page=blk.page,
            )
        )
    sections.sort(key=lambda s: s.bbox.top)
    return tuple(sections)


# --------------------------------------------------------------------------
# Furniture & picture regions (exclusion zones)
# --------------------------------------------------------------------------


def detect_furniture_regions(docling_blocks: Iterable[DoclingBlock]) -> tuple[BBox, ...]:
    """BBoxes of every Docling block tagged with content_layer='furniture'."""
    return tuple(
        blk.bbox for blk in docling_blocks if blk.content_layer == "furniture"
    )


def detect_picture_regions(docling_blocks: Iterable[DoclingBlock]) -> tuple[BBox, ...]:
    """BBoxes of every Docling block with label='picture' (logos, figures)."""
    return tuple(blk.bbox for blk in docling_blocks if blk.label == "picture")


def detect_prose_regions(docling_blocks: Iterable[DoclingBlock]) -> tuple[BBox, ...]:
    """Bboxes of paragraph-style regions that should not emit KV pairs.

    Docling already labels paragraphs and clause sub-bullets — `text` blocks
    are body prose, `list_item` blocks are typically clause numbering with
    explanatory content. When their content is long enough to be more than
    a caption, we treat the whole region as a no-emit zone so the inline-
    colon split rule (E2) and the horizontal-pair rule (E3) don't fire on
    items that look label-like but are really part of a sentence.

    Verified on BBVA5 page 14: the two false-positive pairs
    `1. - Cuota Sin nómina domiciliada → considerando el Interés Nominal`
    `2. - Cuota Con Nómina → considerando que se aplica el Interés`
    live inside Docling `list_item` blocks at Y=183 and Y=219 — they are
    footnote explanations, not key/value pairs.
    """
    regions: list[BBox] = []
    for blk in docling_blocks:
        text_len = len((blk.text or "").strip())
        if blk.label == "text" and text_len >= PROSE_TEXT_MIN_CHARS:
            regions.append(blk.bbox)
        elif blk.label == "list_item" and text_len >= PROSE_LIST_ITEM_MIN_CHARS:
            regions.append(blk.bbox)
    return tuple(regions)


# --------------------------------------------------------------------------
# Box detection (non-table rects from pdfplumber)
# --------------------------------------------------------------------------


def detect_boxes(plumber_rects: Iterable[VisualRect]) -> tuple[Box, ...]:
    """Wrap pdfplumber rect_type='box' as our `Box` model.

    These boxes are visual containers — section header strips, labelled
    blocks. They feed Rule 4 (sub-section split inside tables) and may be
    consumed by candidates.py to scope pairings.
    """
    return tuple(
        Box(bbox=r.bbox, page=r.page, rect_id=r.rect_id)
        for r in plumber_rects
        if r.rect_type == "box"
    )


# --------------------------------------------------------------------------
# Table fusion (Docling ∪ pdfplumber)
# --------------------------------------------------------------------------


class _TableLike(NamedTuple):
    """Common shape used to fuse Docling and pdfplumber tables uniformly."""

    bbox: BBox
    page: int
    rect_id: str
    cells: tuple[tuple[str, ...], ...] | None
    source: str


def _docling_tables_as_tablelike(blocks: Iterable[DoclingBlock]) -> list[_TableLike]:
    return [
        _TableLike(
            bbox=blk.bbox,
            page=blk.page,
            rect_id=blk.self_ref or "",
            cells=blk.cells,
            source="docling",
        )
        for blk in blocks
        if blk.label == "table"
    ]


def _plumber_tables_as_tablelike(rects: Iterable[VisualRect]) -> list[_TableLike]:
    return [
        _TableLike(
            bbox=r.bbox,
            page=r.page,
            rect_id=r.rect_id,
            cells=r.cells,
            source="pdfplumber",
        )
        for r in rects
        if r.rect_type == "table"
    ]


def _fuse_one_pair(d: _TableLike, p: _TableLike) -> _TableLike:
    """Fuse one Docling table with its matching pdfplumber table.

    Cells from Docling win because TableFormer correctly fuses multi-line
    bold labels and splits label/value columns (verified on LABORAL Respuesta
    and PATRIMONIAL Servicios Consultados). pdfplumber contributes the
    snap-to-grid bbox, which is geometrically tighter than Docling's.
    """
    cells = d.cells if d.cells is not None else p.cells
    return _TableLike(
        bbox=p.bbox,
        page=d.page,
        rect_id=p.rect_id or d.rect_id,
        cells=cells,
        source="fused",
    )


def _normalise_cells(cells: tuple[tuple[str, ...], ...] | None) -> str:
    """Collapse a cell matrix to a single normalised string for similarity.

    Whitespace-stripped, lowercased, row-by-row. Used to detect shadow
    duplicates where pdfplumber re-detects a Docling table at a different
    (often off-page) Y coordinate with whitespace-collapsed text — observed
    on BBVA5 p3 (15×4) and p16 glossary (8×2 vs 7×2). The duplicate carries
    the same content modulo whitespace, so a single normalised string per
    table is enough to recognise the redundancy.
    """
    if not cells:
        return ""
    parts: list[str] = []
    for row in cells:
        for c in row:
            parts.append("".join(c.lower().split()))
    return "|".join(parts)


def _is_shadow_duplicate(
    candidate: _TableLike, accepted: list[_TableLike]
) -> bool:
    """True if `candidate` reproduces the content of an already-accepted
    table on the same page (same row count, same col count, similar text).

    Same shape + 60% normalised-content overlap is the empirical threshold
    that catches pdfplumber's BBVA5 off-page duplicates without flagging
    real-but-similar tables (e.g. the two `Datos Petición` / `Respuesta`
    headed blocks in PNJ documents have very different content despite
    sharing structural shape).
    """
    if not candidate.cells:
        return False
    cand_rows = len(candidate.cells)
    cand_cols = max((len(r) for r in candidate.cells), default=0)
    cand_norm = _normalise_cells(candidate.cells)
    if not cand_norm:
        return False
    cand_parts = set(cand_norm.split("|"))
    for other in accepted:
        if other.page != candidate.page or not other.cells:
            continue
        if len(other.cells) != cand_rows:
            continue
        other_cols = max((len(r) for r in other.cells), default=0)
        if other_cols != cand_cols:
            continue
        other_parts = set(_normalise_cells(other.cells).split("|"))
        if not other_parts:
            continue
        overlap = len(cand_parts & other_parts) / max(len(cand_parts), 1)
        if overlap >= 0.6:
            return True
    return False


def detect_tables(
    docling_blocks: Iterable[DoclingBlock],
    plumber_rects: Iterable[VisualRect],
) -> tuple[Table, ...]:
    """Fuse Docling tables and pdfplumber tables into one set per page.

    Strategy:
      - For each Docling table on the page, find the pdfplumber table whose
        bbox has the highest IoU. If IoU >= TABLE_FUSE_IOU → fuse them.
      - Docling tables without a pdfplumber match are emitted with
        source='docling' (Docling sees grid-less tables that pdfplumber cannot).
      - pdfplumber tables without a Docling match are emitted with
        source='pdfplumber' ONLY IF their normalised content doesn't already
        appear in an accepted table on the same page. pdfplumber occasionally
        re-detects a Docling table at a phantom off-page Y with whitespace-
        collapsed cells — those shadow duplicates are dropped here.
      - Cell content uses Docling when available; otherwise pdfplumber.
    """
    docling_tl = _docling_tables_as_tablelike(docling_blocks)
    plumber_tl = _plumber_tables_as_tablelike(plumber_rects)

    matched_plumber: set[int] = set()
    fused: list[_TableLike] = []

    for d in docling_tl:
        best_iou = 0.0
        best_idx: int | None = None
        for i, p in enumerate(plumber_tl):
            if p.page != d.page or i in matched_plumber:
                continue
            iou = d.bbox.iou(p.bbox)
            if iou > best_iou:
                best_iou = iou
                best_idx = i
        if best_idx is not None and best_iou >= TABLE_FUSE_IOU:
            matched_plumber.add(best_idx)
            fused.append(_fuse_one_pair(d, plumber_tl[best_idx]))
        else:
            fused.append(d)

    for i, p in enumerate(plumber_tl):
        if i in matched_plumber:
            continue
        if _is_shadow_duplicate(p, fused):
            continue
        fused.append(p)

    return tuple(
        Table(
            bbox=t.bbox,
            page=t.page,
            rect_id=t.rect_id,
            cells=t.cells,
            source=t.source,
        )
        for t in sorted(fused, key=lambda x: (x.page, x.bbox.top))
    )


# --------------------------------------------------------------------------
# Sub-section detection inside a table (Rule 4)
# --------------------------------------------------------------------------


def _box_is_subheader_for(box: Box, table: Table) -> bool:
    """True if `box` looks like a sub-header strip nested inside `table`.

    A sub-header strip:
      - lives entirely inside the table bbox
      - has width approximately equal to the table's width
      - has a short height (one-row band, not a body region)
    """
    if box.page != table.page:
        return False
    if not _bbox_contains(table.bbox, box.bbox):
        return False
    if abs(box.bbox.w - table.bbox.w) > SUBHEADER_WIDTH_TOLERANCE_PT:
        return False
    if box.bbox.h > SUBHEADER_MAX_HEIGHT_PT:
        return False
    return True


def _subheader_text(box: Box, lite_items: Iterable[LiteItem]) -> str:
    """Best-effort: the title text inside a sub-header box is whatever
    LiteParse items have their centroid in the box. Joined by space, trimmed.
    """
    parts: list[str] = []
    for it in lite_items:
        if it.page != box.page:
            continue
        cx, cy = it.bbox.centroid
        if box.bbox.contains_point(cx, cy):
            parts.append((it.text or "").strip())
    return " ".join(p for p in parts if p).strip()


def attach_subsections(
    tables: tuple[Table, ...],
    boxes: tuple[Box, ...],
    lite_items: tuple[LiteItem, ...],
) -> tuple[Table, ...]:
    """For each table, find sub-header boxes inside it and split into
    Subsection regions. Returns a new tuple of Tables with `subsections` set.

    Rule 4 in the v0.7.0 handoff: a `pdfplumber rect_type='box'` whose width
    matches the parent table is a horizontal split. The space between
    consecutive sub-header tops is one Subsection's body.
    """
    by_table: dict[int, list[Box]] = {}
    for i, t in enumerate(tables):
        candidates = [b for b in boxes if _box_is_subheader_for(b, t)]
        candidates.sort(key=lambda b: b.bbox.top)
        if candidates:
            by_table[i] = candidates

    out: list[Table] = []
    for i, t in enumerate(tables):
        subheaders = by_table.get(i, [])
        if not subheaders:
            out.append(t)
            continue
        # Build Subsection objects: header band + body band until next header.
        splits = [h.bbox.top for h in subheaders[1:]]
        bodies = _intervals_between(splits, subheaders[0].bbox.bottom, t.bbox.bottom)
        subs: list[Subsection] = []
        for header, (y_start, y_end) in zip(subheaders, bodies, strict=True):
            body_bbox = BBox.from_ltrb(t.bbox.left, y_start, t.bbox.right, y_end)
            subs.append(
                Subsection(
                    header_text=_subheader_text(header, lite_items),
                    header_bbox=header.bbox,
                    body_bbox=body_bbox,
                    page=t.page,
                )
            )
        out.append(
            Table(
                bbox=t.bbox,
                page=t.page,
                rect_id=t.rect_id,
                cells=t.cells,
                subsections=tuple(subs),
                source=t.source,
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def detect_structure(
    docling_blocks: Iterable[DoclingBlock],
    lite_items: Iterable[LiteItem],
    plumber_rects: Iterable[VisualRect],
) -> tuple[Page, ...]:
    """Run every detection step and return a `Page` per source page.

    The caller is responsible for ordering / providing the engine outputs;
    this function does no I/O and no caching.
    """
    docling_blocks = tuple(docling_blocks)
    lite_items = tuple(lite_items)
    plumber_rects = tuple(plumber_rects)

    pages: dict[int, dict] = {}
    for blk in docling_blocks:
        pages.setdefault(blk.page, {"docling": [], "lite": [], "plumber": []})["docling"].append(blk)
    for it in lite_items:
        pages.setdefault(it.page, {"docling": [], "lite": [], "plumber": []})["lite"].append(it)
    for r in plumber_rects:
        pages.setdefault(r.page, {"docling": [], "lite": [], "plumber": []})["plumber"].append(r)

    result: list[Page] = []
    for page_no in sorted(pages):
        bucket = pages[page_no]
        d, l, p = bucket["docling"], bucket["lite"], bucket["plumber"]

        sections = detect_sections(d)
        furniture = detect_furniture_regions(d)
        pictures = detect_picture_regions(d)
        prose = detect_prose_regions(d)
        boxes = detect_boxes(p)
        tables = detect_tables(d, p)
        tables = attach_subsections(tables, boxes, tuple(l))

        result.append(
            Page(
                number=page_no,
                sections=sections,
                boxes=boxes,
                tables=tables,
                furniture_regions=furniture,
                picture_regions=pictures,
                prose_regions=prose,
            )
        )
    return tuple(result)
