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

# A 2-col Docling table is treated as a *multi-label form* — and routed to
# E5's LiteParse-based extractor — when at least one row's left cell carries
# this many colons. BBVA3 Titulares fuses pairs on row 1 only
# (`'N.I.F.: 009786573G Tipo Identificación: NIF PERSONA FISICA'`); one
# fused row is enough to indicate the column semantics are wrong throughout.
MULTI_LABEL_CELL_MIN_COLONS = 2


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


def _is_multi_label_form(table: Table) -> bool:
    """True if a 2-col table has at least one row whose left cell carries
    multiple `:` characters.

    Signal that Docling TableFormer collapsed two parallel columns of
    independent label/value pairs into one cell string — verified on
    BBVA3 Titulares row 1 col[0]
    `'N.I.F.: 009786573G Tipo Identificación: NIF PERSONA FISICA'`
    (2 colons in one cell, two logical pairs concatenated).

    Any single multi-colon cell is enough — averaging across all rows
    dilutes the signal (BBVA3 only fuses pairs on 1 of 9 rows; most rows
    still carry a single KV correctly). When one fused row is found we
    re-extract the whole table from LiteParse via E5 because the column
    semantics are wrong throughout.
    """
    if not table.cells:
        return False
    n_cols = max((len(r) for r in table.cells), default=0)
    if n_cols != 2:
        return False
    return any(
        row[0].count(":") >= MULTI_LABEL_CELL_MIN_COLONS
        for row in table.cells
        if row
    )


def _cells_all_equal(cells: tuple[str, ...], start: int) -> bool:
    """True if every cell from `start` onwards has the same stripped content.

    Used to detect single-value rows in an N-column matrix where the
    label sits in col 0 and a colspan repeated the same value across
    cols 1..N-1 (a common Docling TableFormer artefact — verified on
    BBVA5 page 3 where rows like
    `['Fecha Entrada en Vigor', '29-03-2021', '29-03-2021', '29-03-2021']`
    are semantically a single label/value pair).
    """
    ref = cells[start].strip()
    return all(c.strip() == ref for c in cells[start:])


def _is_column_header_row(cells: tuple[str, ...]) -> bool:
    """True if row[0] is empty and the remaining cells provide distinct
    column headers (BBVA5 `['', 'Sin nómina', 'Con nómina', 'Con nómina']`).

    Such a row introduces the sub-column labels that apply to every row
    below it (until the next column-header row), so we emit no pair for
    it and instead carry forward its non-empty cells as `column_headers`.
    """
    if not cells or cells[0].strip():
        return False
    rest = [c.strip() for c in cells[1:]]
    if not rest or not any(rest):
        return False
    # At least two of the non-empty cells should differ — otherwise it's
    # just a single repeated header (still useful but indistinguishable
    # from a normal spanned-title row).
    seen = set(c for c in rest if c)
    return len(seen) >= 2


def emit_from_docling_tables(pages: Iterable[Page]) -> tuple[PairCandidate, ...]:
    """Emit one candidate per row of every fused table.

    Three row shapes, listed in priority order — the first match wins for
    each row:

      1. **Spanned title** (col[0] == col[1] == ... == col[N-1])
         Skipped — already represented as a Subsection by structure.py.

      2. **Column-header row** (col[0] empty, col[1..N-1] distinct
         non-empty values, e.g. `['', 'Sin nómina', 'Con nómina', ...]`)
         Captured as a `column_headers` carry-forward that annotates
         subsequent rows. No pair emitted directly.

      3. **Consistent-value row** (col[1] == col[2] == ... == col[N-1])
         Emits a single pair (label=col[0], value=col[1]). This catches
         the dominant case in BBVA5 page 3 — rows like
         `['Comisión de Cancelación Anticipada Total', '1,0000% máximo...',
         idem, idem]` where Docling fused the multi-line bold label and
         the value is the same across colspans.

      4. **Per-column-with-header row** (col[1] != col[2], a prior
         column-header row exists)
         Emits one pair per distinct cell, with the column header
         appended to the label so downstream callers can distinguish
         `'TAE (Sin nómina)' → '12,6020%'` from
         `'TAE (Con nómina)' → '11,4813%'`.

      5. **Otherwise** — skipped for now; will be handled by a follow-up
         dense-matrix emitter.
    """
    out: list[PairCandidate] = []
    for page in pages:
        for table in page.tables:
            if not table.cells:
                continue
            n_rows = len(table.cells)
            n_cols = max((len(r) for r in table.cells), default=0)
            if n_cols < 2:
                continue
            if _is_multi_label_form(table):
                continue  # E5 handles this table with LiteParse items
            col_headers: tuple[str, ...] | None = None
            for r, row in enumerate(table.cells):
                if len(row) < 2:
                    continue
                stripped = tuple(c.strip() for c in row)

                # Shape 1 — spanned title row, skip.
                if all(c == stripped[0] for c in stripped) and stripped[0]:
                    continue
                if not any(stripped):
                    continue

                # Shape 2 — column-header row, capture and skip.
                if _is_column_header_row(row):
                    col_headers = stripped
                    continue

                row_top, row_bottom = _row_y_range(table, r, n_rows)
                sub_title = _subsection_title_for_row(table, row_top, row_bottom)
                label = stripped[0]

                # Shape 3 — consistent value across cols[1:].
                if _cells_all_equal(row, start=1):
                    value = stripped[1]
                    if not label and not value:
                        continue
                    out.append(_make_table_candidate(
                        table, label, value, row_top, row_bottom,
                        row_index=r, row_count=n_rows, sub_title=sub_title,
                        column_header=None,
                    ))
                    continue

                # Shape 4 — per-column row with prior headers available.
                if col_headers is not None and label:
                    seen: dict[str, int] = {}
                    for col_idx in range(1, len(stripped)):
                        v = stripped[col_idx]
                        if not v or v in seen:
                            continue
                        seen[v] = col_idx
                        header = col_headers[col_idx] if col_idx < len(col_headers) else ""
                        out.append(_make_table_candidate(
                            table,
                            f"{label} ({header})" if header else label,
                            v,
                            row_top, row_bottom,
                            row_index=r, row_count=n_rows, sub_title=sub_title,
                            column_header=header,
                        ))
                    continue

                # Shape 5 — fallback: emit col[0] + col[1] as best-effort
                # pair so we don't lose the row entirely. Lower confidence
                # because the multi-column semantics are unresolved.
                if label and stripped[1]:
                    out.append(_make_table_candidate(
                        table, label, stripped[1], row_top, row_bottom,
                        row_index=r, row_count=n_rows, sub_title=sub_title,
                        column_header=None, low_confidence=True,
                    ))
    return tuple(out)


def _make_table_candidate(
    table: Table,
    label: str,
    value: str,
    row_top: float,
    row_bottom: float,
    *,
    row_index: int,
    row_count: int,
    sub_title: str,
    column_header: str | None,
    low_confidence: bool = False,
) -> PairCandidate:
    """Construct a D-2col PairCandidate for one row.

    Bboxes are linear approximations because Docling exposes cell text
    but not per-cell bboxes — half-width split keeps the geometric data
    useful for dedup and for studio-side highlighting without being
    misleading about precision.
    """
    half_w = table.bbox.w / 2.0
    label_bbox = BBox.from_ltrb(
        table.bbox.left, row_top, table.bbox.left + half_w, row_bottom
    )
    value_bbox = BBox.from_ltrb(
        table.bbox.left + half_w, row_top, table.bbox.right, row_bottom
    )
    features: dict[str, float | bool | int | str] = {
        "row_index": row_index,
        "row_count": row_count,
        "table_source": table.source,
        "subsection_title": sub_title,
        "label_ends_with_colon": label.rstrip().endswith(":"),
        "value_empty": not value,
    }
    if column_header:
        features["column_header"] = column_header
    if low_confidence:
        features["unresolved_matrix"] = True
    return PairCandidate(
        label_text=label,
        value_text=value,
        label_bbox=label_bbox,
        value_bbox=value_bbox,
        page=table.page,
        rule="D-2col",
        features=features,
    )


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
    # Key by page so an item on page 1 isn't suppressed by a table on page 4
    # that happens to share coordinates (Entidades Financieras 4×8 on
    # PATRIMONIAL p4 sits at Y=109, h=105 — the same band as the Datos
    # Petición block on page 1).
    docling_table_bboxes_by_page: dict[int, list[BBox]] = {}
    prose_by_page: dict[int, list[BBox]] = {}
    for p in pages:
        for t in p.tables:
            if (
                t.source in ("docling", "fused")
                and t.cells
                and max((len(r) for r in t.cells), default=0) >= 2
            ):
                docling_table_bboxes_by_page.setdefault(p.number, []).append(t.bbox)
        prose_by_page[p.number] = list(p.prose_regions)

    out: list[PairCandidate] = []
    for ci in classified:
        if ci.kind is not ItemKind.LABEL:
            continue
        page_tables = docling_table_bboxes_by_page.get(ci.page, [])
        if _item_inside_any(ci.bbox, page_tables):
            continue
        if _item_inside_any(ci.bbox, prose_by_page.get(ci.page, [])):
            continue  # inside a paragraph / list_item — not a real KV pair
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

    # Per-page exclusion regions so cross-page coordinate collisions can't
    # silently suppress a real pair (PATRIMONIAL bug: a 4×8 table at Y=109
    # on page 4 was suppressing the Datos Petición items on page 1 because
    # the bbox check was page-blind).
    docling_table_bboxes: dict[int, list[BBox]] = {}
    furniture: dict[int, list[BBox]] = {}
    pictures: dict[int, list[BBox]] = {}
    prose: dict[int, list[BBox]] = {}
    for p in pages:
        for t in p.tables:
            if t.source in ("docling", "fused") and t.cells and max(
                (len(r) for r in t.cells), default=0
            ) >= 2:
                docling_table_bboxes.setdefault(p.number, []).append(t.bbox)
        furniture[p.number] = list(p.furniture_regions)
        pictures[p.number] = list(p.picture_regions)
        prose[p.number] = list(p.prose_regions)

    by_page: dict[int, list[ClassifiedItem]] = {}
    for ci in classified:
        by_page.setdefault(ci.page, []).append(ci)

    out: list[PairCandidate] = []
    for page_no, items in by_page.items():
        d_tables = docling_table_bboxes.get(page_no, [])
        furn = furniture.get(page_no, [])
        pict = pictures.get(page_no, [])
        prs = prose.get(page_no, [])

        def excluded(b: BBox) -> bool:
            return (
                _item_inside_any(b, d_tables)
                or _item_inside_any(b, furn)
                or _item_inside_any(b, pict)
                or _item_inside_any(b, prs)
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
# E5 — Two-column form extraction (LiteParse inside Docling-fused form table)
# --------------------------------------------------------------------------


def emit_from_two_column_form(
    classified: Iterable[ClassifiedItem],
    pages: Iterable[Page],
) -> tuple[PairCandidate, ...]:
    """Re-extract pairs from LiteParse items inside multi-label form tables.

    Triggered when Docling reports a 2-col table whose cells fused two
    parallel columns of independent `label: value` strings — `_is_multi_label_form`
    detects this. E1 produces junk for these tables (concatenated cells
    pointed at each other); E5 walks the LiteParse items inside the table
    bbox instead, splits each item on its colon, and annotates the column
    using the X centroid vs the table midline.

    Verified on BBVA3 page 1 Titulares (9×2): the form has two parallel
    columns at X≈31 (col 1, "Titular 1" data) and X≈305 (col 2, "Titular 2"
    data). Each LiteParse item is a clean single `label: value` we can
    split, and the column position tells us which titular it belongs to.

    Labels emerge as `'N.I.F. (col 1)'`, `'N.I.F. (col 2)'`, etc. — the
    column suffix preserves the parallel-form semantics without committing
    to brittle titular names (which are not always present in the PDF).
    """
    pages = tuple(pages)
    classified = tuple(classified)

    form_tables: list[Table] = []
    for p in pages:
        for t in p.tables:
            if _is_multi_label_form(t):
                form_tables.append(t)
    if not form_tables:
        return ()

    by_page: dict[int, list[ClassifiedItem]] = {}
    for ci in classified:
        by_page.setdefault(ci.page, []).append(ci)

    out: list[PairCandidate] = []
    for table in form_tables:
        midline = table.bbox.left + table.bbox.w / 2.0
        items_on_page = by_page.get(table.page, [])
        for ci in items_on_page:
            cx, cy = ci.bbox.centroid
            if not _bbox_contains_point(table.bbox, cx, cy):
                continue
            # Skip items that don't look like KV at all (titles, prose).
            if ci.kind not in (ItemKind.LABEL, ItemKind.VALUE):
                continue
            idx = _find_inline_colon(ci.text)
            if idx < 0:
                continue
            label_part = ci.text[:idx].rstrip()
            value_part = ci.text[idx + 1 :].lstrip()
            if not label_part:
                continue

            col_idx = 1 if cx < midline else 2
            annotated_label = f"{label_part} (col {col_idx})"

            total = len(ci.text) or 1
            split_frac = (idx + 1) / total
            full = ci.bbox
            split_x = full.left + full.w * split_frac
            label_bbox = BBox.from_ltrb(full.left, full.top, split_x, full.bottom)
            value_bbox = BBox.from_ltrb(split_x, full.top, full.right, full.bottom)

            out.append(
                PairCandidate(
                    label_text=annotated_label,
                    value_text=value_part,
                    label_bbox=label_bbox,
                    value_bbox=value_bbox,
                    page=table.page,
                    rule="L-twocol-form",
                    features={
                        "label_ends_with_colon": True,
                        "column_index": col_idx,
                        "raw_label": label_part,
                        "value_empty": value_part.strip() in ("", "-"),
                    },
                    label_item=ci,
                    value_item=ci,
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
        + emit_from_two_column_form(classified, pages)
    )
