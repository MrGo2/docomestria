"""Wrapper around the Docling engine."""

from __future__ import annotations

from pathlib import Path

from ..models import BBox, DoclingBlock


def extract_docling_blocks(pdf_path: str | Path) -> list[DoclingBlock]:
    """Parse a PDF with Docling and return semantic blocks in top-left origin.

    Docling reports bboxes in PDF (bottom-left) coordinates; we flip them to
    top-left so they line up with LiteParse and pdfplumber.

    Imports are lazy because Docling pulls heavy ML dependencies.
    """
    from docling.datamodel.base_models import InputFormat  # type: ignore[import-not-found]
    from docling.datamodel.pipeline_options import (  # type: ignore[import-not-found]
        PdfPipelineOptions,
        TableFormerMode,
        TableStructureOptions,
    )
    from docling.document_converter import (  # type: ignore[import-not-found]
        DocumentConverter,
        PdfFormatOption,
    )
    from docling_core.types.doc import (  # type: ignore[import-not-found]
        ContentLayer,
        SectionHeaderItem,
        TableItem,
    )

    pipeline_options = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=True,
        force_backend_text=True,
        generate_page_images=False,
        generate_picture_images=False,
        table_structure_options=TableStructureOptions(
            mode=TableFormerMode.ACCURATE,
            do_cell_matching=True,
        ),
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    doc = converter.convert(str(pdf_path)).document

    page_heights: dict[int, float] = {
        int(pno): float(page.size.height) for pno, page in doc.pages.items()
    }

    blocks: list[DoclingBlock] = []
    for item, _level in doc.iterate_items(
        included_content_layers={ContentLayer.BODY, ContentLayer.FURNITURE}
    ):
        if not getattr(item, "prov", None):
            continue
        prov = item.prov[0]
        page_no = int(prov.page_no)
        ph = page_heights.get(page_no)
        if ph is None:
            continue
        l, t, r, b = prov.bbox.to_top_left_origin(page_height=ph).as_tuple()
        bbox = BBox.from_ltrb(l, t, r, b)

        label_obj = getattr(item, "label", None)
        label = label_obj.value if hasattr(label_obj, "value") else str(label_obj)

        layer_obj = getattr(item, "content_layer", None)
        layer = layer_obj.value if hasattr(layer_obj, "value") else "body"

        cells = _table_cells(item, doc) if isinstance(item, TableItem) else None

        blocks.append(
            DoclingBlock(
                bbox=bbox,
                label=label,
                heading_level=item.level if isinstance(item, SectionHeaderItem) else None,
                content_layer=layer,
                page=page_no,
                text=getattr(item, "text", "") or "",
                self_ref=getattr(item, "self_ref", None),
                cells=cells,
            )
        )
    return blocks


def _table_cells(item: object, doc: object) -> tuple[tuple[str, ...], ...] | None:
    """Best-effort extraction of a TableItem's cell text as a rows x cols matrix.

    Uses `item.data.grid` (computed property on TableData) which returns
    `list[list[TableCell]]`. Each cell exposes `.text` (or `_get_text(doc=...)`
    for rich cells). Returns None on any failure to keep extraction resilient.
    """
    try:
        data = getattr(item, "data", None)
        if data is None:
            return None
        grid = getattr(data, "grid", None)
        if not grid:
            return None
        rows: list[tuple[str, ...]] = []
        for row in grid:
            cells_row: list[str] = []
            for cell in row:
                text = ""
                getter = getattr(cell, "_get_text", None)
                if callable(getter):
                    try:
                        text = getter(doc=doc) or ""
                    except Exception:
                        text = getattr(cell, "text", "") or ""
                else:
                    text = getattr(cell, "text", "") or ""
                cells_row.append(str(text))
            rows.append(tuple(cells_row))
        return tuple(rows) if rows else None
    except Exception:
        return None
