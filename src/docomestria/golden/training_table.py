"""Build the role-classification training table from golden page-files + atoms.

See docs/superpowers/specs/2026-06-08-role-classification-training-table-design.md
"""
from __future__ import annotations

import csv
import os
import statistics
from dataclasses import dataclass, field

from docomestria.golden.engine_data import _norm, _contains
from docomestria.text_features import case_class as _case_class, content_flags

# Fixed column order. Provenance first, then label, then the feature vector.
FIELDS = [
    # provenance (not features)
    "pdf", "page", "text", "node_path", "source_node_type",
    "in_table", "table_id", "row_idx", "col_id",
    # label
    "role",
    # geometry (normalised 0-1 by page size)
    "x", "y", "w", "h",
    # typography
    "font_size", "font_size_ratio", "is_bold",
    "case_upper", "case_lower", "case_title", "case_mixed",
    # content (computed from the item's own text)
    "digit_ratio", "has_currency", "has_date", "has_percent",
    "has_iban", "has_nif", "starts_paren", "ends_colon",
    "n_numeric_tokens", "len_chars",
    # context
    "inside_rect", "colon_present", "engine_agreement",
    "pdfplumber_present", "liteparse_present", "docling_present",
    "docling_column_header", "docling_row_header", "compound_span",
    # neighbour
    "is_centered", "gap_above", "gap_below",
    "font_ratio_vs_below", "bold_above_nonbold_below",
]

_FLOAT_FIELDS = {
    "x", "y", "w", "h", "font_size", "font_size_ratio", "digit_ratio",
    "gap_above", "gap_below", "font_ratio_vs_below",
}


def _fmt(field_name: str, value) -> str:
    """Format one cell: bool -> 0/1, float -> 4dp, None/'' -> '' sentinel."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if field_name in _FLOAT_FIELDS and isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return str(value)


def write_csv(rows: list[dict], path) -> None:
    """Write rows to `path` atomically (temp + rename). Byte-deterministic.

    Uses csv.writer for RFC-correct quoting: the provenance `text` field can
    contain commas, embedded newlines or CRs (real corpus has both), and the
    writer quotes those cells so the column layout never breaks. Cell *values*
    are pre-formatted by `_fmt` (bool->0/1, float->4dp, missing->"") first.
    """
    path = os.fspath(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        w.writerow(FIELDS)
        for r in rows:
            w.writerow([_fmt(f, r.get(f, "")) for f in FIELDS])
    os.replace(tmp, path)


_CASE_ONEHOT = {
    "UPPER": "case_upper",
    "lower": "case_lower",
    "Title": "case_title",
    "mixed": "case_mixed",
}


def _onehot_case(value: str) -> dict:
    out = {k: 0 for k in _CASE_ONEHOT.values()}
    col = _CASE_ONEHOT.get(value)
    if col:
        out[col] = 1
    return out  # an unrecognised value (incl. "none") leaves all four at 0


def signal_features(signal: dict | None) -> dict:
    """Extract typography/context features + span_id from a golden signal dict.

    Returns "" for absent numeric features and 0 for absent flags. `span_id`
    is the liteparse span index (or None) — used for compound detection and to
    mark atoms consumed.
    """
    lp = (signal or {}).get("liteparse") or None
    dl = (signal or {}).get("docling") or None
    case = (lp or {}).get("case_class", "")
    out = {
        "font_size": (lp or {}).get("font_size", "") if lp else "",
        "is_bold": bool((lp or {}).get("is_bold")) if lp else "",
        "liteparse_present": 1 if lp else 0,
        "pdfplumber_present": 1 if (signal or {}).get("pdfplumber") else 0,
        "docling_present": 1 if dl else 0,
        "docling_column_header": 1 if (dl or {}).get("column_header") else 0,
        "docling_row_header": 1 if (dl or {}).get("row_header") else 0,
        "inside_rect": 1 if (signal or {}).get("rect") else 0,
        "colon_present": 1 if (signal or {}).get("colon_signal") else 0,
        "engine_agreement": ((signal or {}).get("engine_agreement") or 0),
        "span_id": (lp or {}).get("span_id") if lp else None,
    }
    out.update(_onehot_case(case))
    return out


def _overlap_frac(a: dict, b: dict) -> float:
    """Intersection area / min(area) of two bboxes (0..1)."""
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    amin = min(a["w"] * a["h"], b["w"] * b["h"]) or 1.0
    return inter / amin


def rederive_signal(text: str, bbox: dict | None, spans: list[dict],
                    min_overlap: float = 0.30):
    """Find the atoms span matching `text` whose bbox overlaps `bbox`.

    Fail-closed: returns (signal, "resolved") only when exactly one candidate
    span both text-matches and overlaps >= min_overlap. Otherwise
    (None, "unresolved"). Builds a liteparse-only signal dict from the span.
    """
    if not bbox:
        return None, "unresolved"
    tn = _norm(text)
    cands = []
    for i, sp in enumerate(spans):
        if not _contains(tn, _norm(sp.get("text", ""))):
            continue
        ov = _overlap_frac(bbox, sp["bbox"])
        if ov >= min_overlap:
            cands.append((ov, i, sp))
    if len(cands) != 1:
        return None, "unresolved"
    _, idx, sp = cands[0]
    sig = {
        "text": text,
        "pdfplumber": None,
        "liteparse": {
            "span_id": idx,
            "bbox": sp["bbox"],
            "case_class": sp.get("case_class", ""),
            "is_bold": sp.get("is_bold", False),
            "font_size": sp.get("font_size", ""),
        },
        "docling": None,
        "rect": None,
        "colon_signal": None,
        "engine_agreement": 1,
    }
    return sig, "resolved"


@dataclass
class Item:
    text: str
    role: str
    bbox: dict | None
    signal: dict | None          # golden signal dict, or None (-> rederive)
    node_path: str
    source_node_type: str
    in_table: int = 0
    table_id: str = ""
    row_idx: str = ""
    col_id: str = ""
    compound_span: int = 0
    pair_id: str = ""           # links a key+value emitted from the same pair
    # filled later in build_page_rows:
    unresolved: int = 0


def _as_signal(ev) -> dict | None:
    """Normalise the many evidence shapes to a single leaf signal dict (or None).

    Known shapes:
      - already a signal: has 'liteparse'/'pdfplumber'/'docling' keys
      - wrapped: {'text_signal': <signal>} or {'title_signal': <signal>}
      - kv_group split: {'label': <signal>, 'value': <signal>} (handled by caller)
      - structural-only ({'path': ...}) -> no leaf signal -> None
    """
    if not isinstance(ev, dict):
        return None
    if any(k in ev for k in ("liteparse", "pdfplumber", "docling")):
        return ev
    for k in ("text_signal", "title_signal", "label_signal", "container_signal"):
        if isinstance(ev.get(k), dict):
            return ev[k]
    return None


_VALUE_ROLES = {"value"}
_KNOWN = {"section", "kv_group", "kv_leaf", "kv_pair", "table",
          "prose_block", "free_text_list", "signature_placeholder", "noise"}


def _emit_pair(pair, path, items):
    """kv_group pair / kv_leaf-style: emit key + value items, detect compound."""
    ev = pair.get("evidence") or {}
    lab_sig = _as_signal(ev.get("label")) if isinstance(ev.get("label"), dict) else None
    val_sig = _as_signal(ev.get("value")) if isinstance(ev.get("value"), dict) else _as_signal(ev)
    key = Item(text=pair.get("label", ""), role="key",
               bbox=pair.get("label_bbox"), signal=lab_sig,
               node_path=path + ".key", source_node_type="kv", pair_id=path)
    val = Item(text=pair.get("value", ""), role="value",
               bbox=pair.get("bbox"), signal=val_sig,
               node_path=path + ".value", source_node_type="kv", pair_id=path)
    # initial compound detection (both signals present); recomputed in
    # build_page_rows after rederive resolves label-only keys.
    ks = ((lab_sig or {}).get("liteparse") or {}).get("span_id") if lab_sig else None
    vs = ((val_sig or {}).get("liteparse") or {}).get("span_id") if val_sig else None
    if ks is not None and ks == vs:
        key.compound_span = val.compound_span = 1
    items.append(key)
    items.append(val)


def walk_structure(structure: list, spans: list, path: str = "") -> list[Item]:
    items: list[Item] = []
    for i, node in enumerate(structure or []):
        t = node.get("type")
        npath = f"{path}/{t}[{node.get('id', i)}]"
        if t == "section":
            items.append(Item(text=node.get("title", ""), role="section_header",
                              bbox=node.get("title_bbox"),
                              signal=_as_signal(node.get("evidence")),
                              node_path=npath + ".title",
                              source_node_type="section"))
            items += walk_structure(node.get("children", []), spans, npath)
        elif t == "kv_group":
            for j, pair in enumerate(node.get("pairs", [])):
                _emit_pair(pair, f"{npath}/pair[{j}]", items)
        elif t in ("kv_leaf", "kv_pair"):
            _emit_pair(node, npath, items)
        elif t == "table":
            if node.get("title"):
                items.append(Item(text=node["title"], role="section_header",
                                  bbox=node.get("title_bbox"),
                                  signal=_as_signal(node.get("evidence")),
                                  node_path=npath + ".title",
                                  source_node_type="table"))
            cols = node.get("columns", [])
            key_col = cols[0]["id"] if cols else "label"
            for c in cols:
                if c.get("label"):
                    items.append(Item(text=c["label"], role="table_header",
                                      bbox=None, signal=None,
                                      node_path=f"{npath}/col[{c['id']}].header",
                                      source_node_type="table", in_table=1,
                                      table_id=str(node.get("id", "")), col_id=str(c["id"])))
            for r, row in enumerate(node.get("rows", [])):
                for c in cols:
                    cell = row.get(c["id"])
                    if not isinstance(cell, dict) or not cell.get("text"):
                        continue
                    role = "key" if c["id"] == key_col else "value"
                    items.append(Item(text=cell["text"], role=role,
                                      bbox=cell.get("bbox"),
                                      signal=_as_signal(cell.get("evidence")),
                                      node_path=f"{npath}/row[{r}].{c['id']}",
                                      source_node_type="table", in_table=1,
                                      table_id=str(node.get("id", "")),
                                      row_idx=str(r), col_id=str(c["id"])))
        elif t == "prose_block":
            items.append(Item(text=node.get("text", ""), role="prose",
                              bbox=node.get("bbox"),
                              signal=_as_signal(node.get("evidence")),
                              node_path=npath, source_node_type="prose_block"))
        elif t == "free_text_list":
            for j, it in enumerate(node.get("items", [])):
                items.append(Item(text=it.get("text", ""), role="prose",
                                  bbox=it.get("bbox"),
                                  signal=_as_signal(it.get("evidence")),
                                  node_path=f"{npath}/item[{j}]",
                                  source_node_type="free_text_list"))
        elif t == "signature_placeholder":
            items.append(Item(text=node.get("text", ""), role="signature",
                              bbox=node.get("bbox"),
                              signal=_as_signal(node.get("evidence")),
                              node_path=npath, source_node_type="signature_placeholder"))
        elif t == "noise":
            items.append(Item(text=node.get("text", ""), role="noise",
                              bbox=node.get("bbox"),
                              signal=_as_signal(node.get("evidence")),
                              node_path=npath, source_node_type="noise"))
        elif t == "array":
            # Repeated record blocks: items[] -> named groups -> named fields.
            # A filled field is {text, evidence, bbox} (a VALUE on the page); an
            # empty field is [None, y_hint]. The field *name* is a schema label
            # with no on-page geometry, so we emit only the filled values.
            for ai, item in enumerate(node.get("items", []) or []):
                if not isinstance(item, dict):
                    continue
                for gkey, group in item.items():
                    if gkey in ("index", "filled") or not isinstance(group, dict):
                        continue
                    for fkey, fld in group.items():
                        if fkey in ("title", "y_hint") or not isinstance(fld, dict):
                            continue
                        if not fld.get("text"):
                            continue
                        items.append(Item(text=fld["text"], role="value",
                                          bbox=fld.get("bbox"),
                                          signal=_as_signal(fld.get("evidence")),
                                          node_path=f"{npath}/item[{ai}].{gkey}.{fkey}",
                                          source_node_type="array"))
        else:
            raise ValueError(f"unknown structure node type {t!r} at {npath}")
    return items


def noise_items(spans: list[dict], consumed_span_ids: set,
                annotated: list[tuple[str, dict]],
                min_overlap: float = 0.30) -> list[Item]:
    """Every atoms span not consumed by an annotated item becomes a noise Item.

    Double guard: a span is matched if its index is in consumed_span_ids OR its
    text+bbox match any annotated (text, bbox) pair (covers items linked via
    pdfplumber/docling but with no liteparse span_id).
    """
    ann = [(_norm(t), bb) for t, bb in annotated]
    out: list[Item] = []
    for i, sp in enumerate(spans):
        if i in consumed_span_ids:
            continue
        spn = _norm(sp.get("text", ""))
        matched = False
        for tn, bb in ann:
            if bb and _contains(tn, spn) and _overlap_frac(sp["bbox"], bb) >= min_overlap:
                matched = True
                break
        if matched:
            continue
        sig = {
            "text": sp.get("text", ""), "pdfplumber": None,
            "liteparse": {"span_id": i, "bbox": sp["bbox"],
                          "case_class": sp.get("case_class", ""),
                          "is_bold": sp.get("is_bold", False),
                          "font_size": sp.get("font_size", "")},
            "docling": None, "rect": None, "colon_signal": None,
            "engine_agreement": 1,
        }
        out.append(Item(text=sp.get("text", ""), role="noise",
                        bbox=sp["bbox"], signal=sig,
                        node_path=f"/atom[{i}]", source_node_type="atom"))
    return out


_CENTER_TOL = 0.06  # fraction of page width


def _item_to_partial_row(it: Item, pdf: str, page) -> dict:
    """Everything except page-level (font_size_ratio) and neighbour features."""
    sig = it.signal
    sf = signal_features(sig)
    row = {f: "" for f in FIELDS}
    row.update({
        "pdf": pdf, "page": page, "text": it.text.strip(),
        "node_path": it.node_path, "source_node_type": it.source_node_type,
        "in_table": it.in_table, "table_id": it.table_id,
        "row_idx": it.row_idx, "col_id": it.col_id, "role": it.role,
        "font_size": sf["font_size"], "is_bold": sf["is_bold"],
        "case_upper": sf["case_upper"], "case_lower": sf["case_lower"],
        "case_title": sf["case_title"], "case_mixed": sf["case_mixed"],
        "inside_rect": sf["inside_rect"], "colon_present": sf["colon_present"],
        "engine_agreement": sf["engine_agreement"],
        "pdfplumber_present": sf["pdfplumber_present"],
        "liteparse_present": sf["liteparse_present"],
        "docling_present": sf["docling_present"],
        "docling_column_header": sf["docling_column_header"],
        "docling_row_header": sf["docling_row_header"],
        "compound_span": it.compound_span,
    })
    row.update(content_flags(it.text))   # content from the item's OWN text
    return row


def build_page_rows(golden: dict, atoms: dict):
    """Return (rows, diagnostics) for one golden page-file + its atoms doc."""
    pdf = golden.get("pdf", "")
    page = golden.get("page", "")
    pw, ph = golden.get("page_size_pt", [1.0, 1.0])
    pw = pw or 1.0
    ph = ph or 1.0
    spans = (atoms.get("atoms") or {}).get("spans", [])

    items = walk_structure(golden.get("structure", []), spans)

    # resolve missing signals via atoms re-derivation; track consumption
    unresolved = 0
    for it in items:
        if (it.signal is None or not (it.signal or {}).get("liteparse")) and it.bbox:
            sig, status = rederive_signal(it.text, it.bbox, spans)
            if status == "resolved":
                it.signal = sig
            else:
                unresolved += 1

    # recompute compound_span now that label-only keys are resolved: a pair is
    # compound iff its emitted items share exactly one liteparse span_id.
    by_pair: dict = {}
    for it in items:
        if it.pair_id:
            by_pair.setdefault(it.pair_id, []).append(it)
    for grp in by_pair.values():
        sids = [((m.signal or {}).get("liteparse") or {}).get("span_id") for m in grp]
        sids = [s for s in sids if s is not None]
        compound = 1 if len(sids) >= 2 and len(set(sids)) == 1 else 0
        for m in grp:
            m.compound_span = compound

    consumed = set()
    annotated: list[tuple[str, dict]] = []
    for it in items:
        sid = ((it.signal or {}).get("liteparse") or {}).get("span_id")
        if sid is not None:
            consumed.add(sid)
        if it.bbox:
            annotated.append((it.text, it.bbox))

    items += noise_items(spans, consumed, annotated)

    # --- page-level: font_size_ratio over items that have a font_size ---
    fonts = [it.signal["liteparse"]["font_size"] for it in items
             if it.signal and (it.signal.get("liteparse") or {}).get("font_size")
             and isinstance(it.signal["liteparse"]["font_size"], (int, float))]
    median_font = statistics.median(fonts) if fonts else 0.0

    # build partial rows, attach normalised geometry
    partial = []
    for it in items:
        row = _item_to_partial_row(it, pdf, page)
        bb = it.bbox or ((it.signal or {}).get("liteparse") or {}).get("bbox")
        if bb:
            row["x"] = bb["x"] / pw
            row["y"] = bb["y"] / ph
            row["w"] = bb["w"] / pw
            row["h"] = bb["h"] / ph
            cx = (bb["x"] + bb["w"] / 2) / pw
            row["is_centered"] = 1 if abs(cx - 0.5) <= _CENTER_TOL else 0
        fs = row["font_size"]
        row["font_size_ratio"] = (fs / median_font) if (median_font and isinstance(fs, (int, float))) else ""
        partial.append((it, row))

    # --- neighbour features: sort by (y, x) in normalised space ---
    def _yx(pr):
        r = pr[1]
        return (r["y"] if r["y"] != "" else 9.9, r["x"] if r["x"] != "" else 9.9)
    ordered = sorted(partial, key=_yx)
    for idx, (it, row) in enumerate(ordered):
        nxt = ordered[idx + 1][1] if idx + 1 < len(ordered) else None
        prv = ordered[idx - 1][1] if idx > 0 else None
        if prv and prv["y"] != "" and row["y"] != "":
            row["gap_above"] = max(0.0, row["y"] - (prv["y"] + (prv["h"] or 0)))
        if nxt and nxt["y"] != "" and row["y"] != "":
            row["gap_below"] = max(0.0, nxt["y"] - (row["y"] + (row["h"] or 0)))
        if nxt and isinstance(row["font_size"], (int, float)) and isinstance(nxt["font_size"], (int, float)) and nxt["font_size"]:
            row["font_ratio_vs_below"] = row["font_size"] / nxt["font_size"]
        # only decide bold-above/nonbold-below when the next row's bold is KNOWN
        cur_bold = row["is_bold"] in (1, True)
        nxt_known = nxt is not None and nxt["is_bold"] in (0, 1, True, False)
        nxt_bold = nxt is not None and nxt["is_bold"] in (1, True)
        row["bold_above_nonbold_below"] = 1 if (cur_bold and nxt_known and not nxt_bold) else 0

    rows = [row for _, row in partial]
    diag = {"unresolved_keys": unresolved,
            "noise_atoms": sum(1 for r in rows if r["source_node_type"] == "atom"),
            "n_rows": len(rows)}
    return rows, diag
