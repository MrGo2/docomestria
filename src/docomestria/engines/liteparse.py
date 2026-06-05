"""Wrapper around the LiteParse v2 engine."""

from __future__ import annotations

from pathlib import Path

from ..models import BBox, LiteItem


def extract_lite_items(pdf_path: str | Path) -> list[LiteItem]:
    """Parse a PDF with LiteParse v2 and return a flat list of `LiteItem`.

    LiteParse is imported lazily so the rest of the library can be used in
    environments where it is not installed (e.g. unit tests that exercise the
    geometry layer only).
    """
    import liteparse  # type: ignore[import-not-found]

    parser = liteparse.LiteParse(ocr_enabled=False, quiet=True)
    result = parser.parse(str(pdf_path))

    items: list[LiteItem] = []
    for pno in range(1, result.num_pages + 1):
        page = result.get_page(pno)
        if page is None:
            continue
        for it in page.text_items:
            items.append(
                LiteItem(
                    text=it.text,
                    bbox=BBox(x=float(it.x), y=float(it.y), w=float(it.width), h=float(it.height)),
                    font_name=getattr(it, "font_name", None),
                    font_size=float(getattr(it, "font_size", 0.0)) or None,
                    page=pno,
                )
            )
    return items
