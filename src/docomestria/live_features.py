"""Build live role-classifier feature rows (the FIELDS schema) for a production
PDF page, directly from the three engines. Mirrors golden/training_table.py's
row semantics but computes everything from LIVE engine outputs (no golden signal
dict) and fixes the colon quirk. The golden builder is not modified."""

from __future__ import annotations

from .golden.training_table import FIELDS, _onehot_case
from .models import BBox, LiteItem
from .structural.classify import is_bold
from .text_features import case_class, content_flags


def _bbox_to_dict(bb: BBox) -> dict:
    return {"x": bb.x, "y": bb.y, "w": bb.w, "h": bb.h}


def _base_row(it: LiteItem, page_size_pt: tuple[float, float]) -> dict:
    """Provenance + content + typography + case + normalised geometry for one item.
    Engine-match, colon, neighbour, and label fields are filled later."""
    pw, ph = page_size_pt
    pw = pw or 1.0
    ph = ph or 1.0
    text = it.text.strip()

    row: dict = {f: "" for f in FIELDS}  # full schema, blanks filled below

    row["pdf"] = ""  # filled by build_live_rows
    row["page"] = it.page
    row["text"] = text
    row["node_path"] = ""
    row["source_node_type"] = "live_item"
    row["in_table"] = 0
    row["table_id"] = ""
    row["row_idx"] = ""
    row["col_id"] = ""
    row["role"] = ""

    row["x"] = it.bbox.x / pw
    row["y"] = it.bbox.y / ph
    row["w"] = it.bbox.w / pw
    row["h"] = it.bbox.h / ph

    row["font_size"] = it.font_size if it.font_size is not None else ""
    row["font_size_ratio"] = ""
    row["is_bold"] = 1 if is_bold(it.font_name) else 0
    row.update(_onehot_case(case_class(text)))

    row.update(content_flags(text))

    row["liteparse_present"] = 1

    return row
