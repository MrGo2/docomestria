"""Compact `FusedItem`s into a JSON-friendly context for the LLM prompt.

We drop the cosmetic layer (page headers, footers, pictures) and group items
by section so the model sees structured input rather than a flat dump.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..models import FusedItem

# Labels that we treat as page furniture — almost never carry data values.
FURNITURE_LABELS: frozenset[str] = frozenset({"page_header", "page_footer", "picture"})


def build_llm_context(items: Iterable[FusedItem]) -> dict[str, object]:
    """Compact `items` into a JSON-serializable context dict.

    Output shape:
        {
            "sections": [
                {"title": "...", "items": [{"i": 0, "t": "..."}, ...]},
                ...
            ]
        }

    `i` is the FusedItem index in the original tuple — useful for callers
    that want to instruct the LLM to cite source indices.
    """
    sections: dict[str, list[dict[str, object]]] = {}
    order: list[str] = []
    for idx, it in enumerate(items):
        if not _is_useful(it):
            continue
        section = (it.section_title or "_unsectioned").strip() or "_unsectioned"
        if section not in sections:
            sections[section] = []
            order.append(section)
        sections[section].append({"i": idx, "t": it.text})
    return {
        "sections": [
            {"title": title, "items": sections[title]} for title in order if sections[title]
        ]
    }


def _is_useful(item: FusedItem) -> bool:
    if not item.text or not item.text.strip():
        return False
    return item.docling_label not in FURNITURE_LABELS


__all__ = ["FURNITURE_LABELS", "build_llm_context"]
