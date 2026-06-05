"""Emit `PairCandidate` instances from multiple sources.

Each emitter is independent and produces candidates with `rule` set so the
scorer can apply rule-specific weights. The same label may legitimately appear
across emitters — scoring.py is responsible for resolving the conflict, not
candidates.py.

MVP scope (judicial):
    E1  emit_from_docling_tables   — Docling 2-col cells where col[0] != col[1]
    E2  emit_from_in_item_split    — LABEL items containing ':' not at the end
    E3  emit_from_horizontal_pair  — LiteParse Bold + Regular on same Y

Banking-contract extensions (E4 vertical pair, dense-matrix, two-column form)
will land in a follow-up.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..models import BBox
from .models import ClassifiedItem, ItemKind, Page, PairCandidate, Table

# Same-Y tolerance for horizontal pairing. Picked from observation: same-line
# items in LiteParse share Y to within ±0.2pt (PDF subpixel rounding) but
# baseline shifts on Spanish accented characters can push it to ~3pt.
HORIZONTAL_Y_TOLERANCE_PT = 3.0

# A horizontal-pair value must start strictly to the RIGHT of the label's
# right edge, with at most this much gap. Wider gaps suggest a different
# column entirely (e.g. titular vs co-titular in BBVA forms).
HORIZONTAL_X_GAP_MAX_PT = 300.0


# --------------------------------------------------------------------------
# Geometric helpers
# --------------------------------------------------------------------------


def _bbox_contains_point(b: BBox, x: float, y: float) -> bool:
    return b.left <= x <= b.right and b.top <= y <= b.bottom


def _item_inside_any(item_bbox: BBox, regions: Iterable[BBox]) -> bool:
    cx, cy = item_bbox.centroid
    return any(_bbox_contains_point(r, cx, cy) for r in regions)


def _row_y_range(table: Table, row_idx: int, n_rows: int) -> tuple[float, float]:
    """Linear approximation of one row's Y band inside a table.

    Docling cells carry text but not per-cell bboxes — we approximate row
    geometry by dividing the table bbox uniformly. Good enough for scoring
    and for sub-section lookup; not used for final reporting (final bboxes
    come from the matched LiteParse items when available).
    """
    h = table.bbox.h / max(n_rows, 1)
    return table.bbox.top + row_idx * h, table.bbox.top + (row_idx + 1) * h


def _subsection_title_for_row(table: Table, row_top: float, row_bottom: float) -> str:
    """The title of the subsection that owns this row, or '' if none."""
    cy = (row_top + row_bottom) / 2.0
    for sub in table.subsections:
        if sub.body_bbox.top <= cy <= sub.body_bbox.bottom:
            return sub.header_text
    return ""


# --------------------------------------------------------------------------
# E1 — Docling 2-column tables
# --------------------------------------------------------------------------


def emit_from_docling_tables(pages: Iterable[Page]) -> tuple[PairCandidate, ...]:
    """For each fused table whose cell matrix has 2 columns, emit one
    candidate per row whose two cells differ.

    Cells where col[0] == col[1] are spanned section/sub-section titles
    and are skipped (they're already represented as Subsection in
    structure.py). Cells where one side is empty still get emitted — an
    empty value is legitimate (LABORAL `CCC:` → ''), and downstream
    scoring will keep them as confirmed-empty pairs.
    """
    out: list[PairCandidate] = []
    for page in pages:
        for table in page.tables:
            if not table.cells:
                continue
            n_rows = len(table.cells)
            n_cols = max((len(r) for r in table.cells), default=0)
            if n_cols != 2:
                continue  # MVP: leave N×M matrices to a later emitter
            half_w = table.bbox.w / 2.0
            for r, row in enumerate(table.cells):
                if len(row) < 2:
                    continue
                left, right = row[0].strip(), row[1].strip()
                if left == right:
                    continue  # spanned title — handled by structure.py
                if not left and not right:
                    continue  # truly empty row
                row_top, row_bottom = _row_y_range(table, r, n_rows)
                label_bbox = BBox.from_ltrb(
                    table.bbox.left, row_top, table.bbox.left + half_w, row_bottom
                )
                value_bbox = BBox.from_ltrb(
                    table.bbox.left + half_w, row_top, table.bbox.right, row_bottom
                )
                sub_title = _subsection_title_for_row(table, row_top, row_bottom)
                out.append(
                    PairCandidate(
                        label_text=left,
                        value_text=right,
                        label_bbox=label_bbox,
                        value_bbox=value_bbox,
                        page=table.page,
                        rule="D-2col",
                        features={
                            "row_index": r,
                            "row_count": n_rows,
                            "table_source": table.source,
                            "subsection_title": sub_title,
                            "label_ends_with_colon": left.rstrip().endswith(":"),
                            "value_empty": not right,
                        },
                    )
                )
    return tuple(out)


# --------------------------------------------------------------------------
# E2 — In-item split (label : value inside one LiteParse text run)
# --------------------------------------------------------------------------


def _find_inline_colon(text: str) -> int:
    """Index of the first ':' that is NOT at the very end of the trimmed text.

    Returns -1 if no qualifying colon is found. We use the *first* colon so
    a label like 'Fecha de emisión: 17 d'abr. 2026 17:14' splits at the
    first ':' (the label/value boundary) and not at the '14:' time literal.
    """
    stripped = text.rstrip()
    idx = stripped.find(":")
    if idx < 0 or idx == len(stripped) - 1:
        return -1
    return idx


def emit_from_in_item_split(
    classified: Iterable[ClassifiedItem],
    pages: Iterable[Page],
) -> tuple[PairCandidate, ...]:
    """Find LABEL items whose text holds `label: value` in one string and emit
    a candidate for each.

    Applies to items classified as LABEL (we trust classify.py to filter
    BODY noise). We deliberately do NOT consume Docling cells here — E1 has
    already emitted candidates for true 2-column tables; E2's job is the
    single-cell / inline case (Datos Petición block in LABORAL, header
    fields in BBVA contracts).

    Items whose centroid falls inside a Docling-handled table (i.e. one
    whose source includes Docling and which has a 2-col cell matrix) are
    skipped — E1 already produced canonical candidates for them.
    """
    pages = tuple(pages)
    docling_2col_tables = tuple(
        t
        for p in pages
        for t in p.tables
        if t.source in ("docling", "fused")
        and t.cells
        and max((len(r) for r in t.cells), default=0) == 2
    )

    out: list[PairCandidate] = []
    for ci in classified:
        if ci.kind is not ItemKind.LABEL:
            continue
        if _item_inside_any(ci.bbox, (t.bbox for t in docling_2col_tables)):
            continue
        idx = _find_inline_colon(ci.text)
        if idx < 0:
            continue
        label_part = ci.text[:idx].rstrip()
        value_part = ci.text[idx + 1 :].lstrip()
        if not label_part or not value_part:
            continue

        # Proportionally split the item's bbox by character offset so the
        # label/value bboxes land roughly where the text sits.
        total = len(ci.text) or 1
        split_frac = (idx + 1) / total
        full = ci.bbox
        split_x = full.left + full.w * split_frac
        label_bbox = BBox.from_ltrb(full.left, full.top, split_x, full.bottom)
        value_bbox = BBox.from_ltrb(split_x, full.top, full.right, full.bottom)

        out.append(
            PairCandidate(
                label_text=label_part,
                value_text=value_part,
                label_bbox=label_bbox,
                value_bbox=value_bbox,
                page=ci.page,
                rule="L-inline-split",
                features={
                    "label_ends_with_colon": True,
                    "value_empty": False,
                    "source_item_text": ci.text,
                },
                label_item=ci,
                value_item=ci,
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------
# E3 — LiteParse horizontal pair (Bold label + Regular value on same Y)
# --------------------------------------------------------------------------


def emit_from_horizontal_pair(
    classified: Iterable[ClassifiedItem],
    pages: Iterable[Page],
) -> tuple[PairCandidate, ...]:
    """Pair each LABEL with the nearest VALUE on the same Y, to the right.

    Skips items inside Docling 2-col tables (E1 already covered them) and
    items inside furniture / picture regions. A LABEL can match at most one
    value — the closest VALUE strictly to the right on the same Y band.
    """
    pages = tuple(pages)
    classified = tuple(classified)

    # Lookup tables we use to suppress duplicates against E1 and the
    # exclusion regions on each page.
    docling_2col_bboxes: dict[int, list[BBox]] = {}
    furniture: dict[int, list[BBox]] = {}
    pictures: dict[int, list[BBox]] = {}
    for p in pages:
        for t in p.tables:
            if t.source in ("docling", "fused") and t.cells and max(
                (len(r) for r in t.cells), default=0
            ) == 2:
                docling_2col_bboxes.setdefault(p.number, []).append(t.bbox)
        furniture[p.number] = list(p.furniture_regions)
        pictures[p.number] = list(p.picture_regions)

    by_page: dict[int, list[ClassifiedItem]] = {}
    for ci in classified:
        by_page.setdefault(ci.page, []).append(ci)

    out: list[PairCandidate] = []
    for page_no, items in by_page.items():
        d_tables = docling_2col_bboxes.get(page_no, [])
        furn = furniture.get(page_no, [])
        pict = pictures.get(page_no, [])

        def excluded(b: BBox) -> bool:
            return (
                _item_inside_any(b, d_tables)
                or _item_inside_any(b, furn)
                or _item_inside_any(b, pict)
            )

        labels = [ci for ci in items if ci.kind is ItemKind.LABEL and not excluded(ci.bbox)]
        values = [ci for ci in items if ci.kind is ItemKind.VALUE and not excluded(ci.bbox)]

        for label in labels:
            best_value: ClassifiedItem | None = None
            best_distance = float("inf")
            l_cx, l_cy = label.bbox.centroid
            for value in values:
                if abs(value.bbox.centroid[1] - l_cy) > HORIZONTAL_Y_TOLERANCE_PT:
                    continue
                if value.bbox.left <= label.bbox.right:
                    continue
                gap = value.bbox.left - label.bbox.right
                if gap > HORIZONTAL_X_GAP_MAX_PT:
                    continue
                if gap < best_distance:
                    best_distance = gap
                    best_value = value
            if best_value is None:
                continue

            ends_colon = label.text.rstrip().endswith(":")
            out.append(
                PairCandidate(
                    label_text=label.text.strip(),
                    value_text=best_value.text.strip(),
                    label_bbox=label.bbox,
                    value_bbox=best_value.bbox,
                    page=page_no,
                    rule="L-horizontal",
                    features={
                        "label_ends_with_colon": ends_colon,
                        "x_gap": best_distance,
                        "y_offset": abs(best_value.bbox.centroid[1] - l_cy),
                        "value_empty": False,
                    },
                    label_item=label,
                    value_item=best_value,
                )
            )
    return tuple(out)


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def emit_all(
    classified: Iterable[ClassifiedItem],
    pages: Iterable[Page],
) -> tuple[PairCandidate, ...]:
    """Run every active emitter and return the concatenated candidates.

    Order is irrelevant — scoring.py groups by (label_text, label_bbox) for
    dedup.
    """
    classified = tuple(classified)
    pages = tuple(pages)
    return (
        emit_from_docling_tables(pages)
        + emit_from_in_item_split(classified, pages)
        + emit_from_horizontal_pair(classified, pages)
    )
