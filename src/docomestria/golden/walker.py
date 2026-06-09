"""walk_and_link — recursive traversal of the structure spec that attaches
engine evidence to every node (leaf and structural).

Also produces a flat kv_pairs list for backward-compat with the viewer.
"""

from __future__ import annotations

from .cell_linker import link_cell
from .engine_data import EngineData
from .structural import link_structural_node


def _union_bbox(bboxes):
    if not bboxes:
        return None
    x0 = min(b["x"] for b in bboxes)
    y0 = min(b["y"] for b in bboxes)
    x1 = max(b["x"] + b["w"] for b in bboxes)
    y1 = max(b["y"] + b["h"] for b in bboxes)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def _collect_bboxes(children):
    out = []
    for c in children or []:
        if not isinstance(c, dict):
            continue
        for k in ("bbox", "container_bbox"):
            if c.get(k):
                out.append(c[k])
        if c.get("children"):
            out.extend(_collect_bboxes(c["children"]))
        if c.get("pairs"):
            for p in c["pairs"]:
                if p.get("bbox"): out.append(p["bbox"])
        if c.get("rows"):
            for row in c["rows"]:
                for v in row.values():
                    if isinstance(v, dict) and v.get("bbox"):
                        out.append(v["bbox"])
        if c.get("items"):
            for it in c["items"]:
                if isinstance(it, dict) and it.get("bbox"):
                    out.append(it["bbox"])
    return out


def walk_and_link(structure: list, eng: EngineData) -> tuple[list, list, dict]:
    """Walk the structure spec, attach evidence to every node, return:
       (structure, flat_kv_pairs, stats)

    stats covers every kv_pair appended to `flat`:
      3_eng/2_eng/1_eng/0_eng — value-bearing cells, by # of engines that matched
      empty                  — cells explicitly empty (e.g. Titular 2 placeholders)
      footnote               — footnote bodies (long text, may match 0..3 engines)
      footnote_ref           — value is {"ref": "nota_X"}, no on-page text
    """
    flat: list[dict] = []
    stats = {"3_eng": 0, "2_eng": 0, "1_eng": 0, "0_eng": 0,
             "empty": 0, "footnote": 0, "footnote_ref": 0}

    def link_text_y(text, y_hint, partner=None, x_hint=None):
        if isinstance(text, tuple):
            if len(text) == 3:
                t, y, x = text
                if x is not None:
                    x_hint = x
            else:
                t, y = text
            return link_cell(eng, t, y if y is not None else y_hint,
                             partner_bbox=partner, x_hint=x_hint)
        if isinstance(text, dict) and "ref" in text:
            return {"ref": text["ref"], "cell_bbox": None, "engine_agreement": 0}
        if text is None:
            return None
        return link_cell(eng, text, y_hint, partner_bbox=partner, x_hint=x_hint)

    def visit(node, path, section_title=None, band_title=None):
        if not isinstance(node, dict):
            return
        t = node.get("type")
        if t == "section":
            title = node.get("title")
            ev = eng.find_char_bbox(title, y_hint=node.get("y_hint"))
            node["title_bbox"] = ev["bbox"] if ev else None
            new_path = path + [title]
            for c in node.get("children", []) or []:
                visit(c, new_path, title, None)
            node["container_bbox"] = _union_bbox(
                _collect_bboxes(node.get("children")))
            node["evidence"] = link_structural_node(eng, node, path)

        elif t == "kv_leaf":
            label_x_hint = node.get("label_x_hint")
            value_x_hint = node.get("x_hint")
            lev = link_text_y(node.get("label"), node.get("y_hint"),
                              x_hint=label_x_hint)
            if lev and lev.get("cell_bbox"):
                node["label_bbox"] = lev["cell_bbox"]
            partner = (lev or {}).get("cell_bbox") if isinstance(lev, dict) else None
            value = node.get("value")
            is_empty = (value is None or value == "" or value == "-")
            ev = link_text_y(value, node.get("y_hint"), partner=partner,
                             x_hint=value_x_hint) if not is_empty else None
            node["evidence"] = ev
            if ev and ev.get("cell_bbox"):
                node["bbox"] = ev["cell_bbox"]
            # Bucket: empty vs engine-link count. Real 0_eng = engine failure to find non-empty text.
            if is_empty:
                stats["empty"] += 1
            else:
                stats[f"{(ev or {}).get('engine_agreement', 0)}_eng"] += 1
            flat.append({
                "label": node["label"], "value": node.get("value") or "",
                "section": section_title, "band": band_title,
                "column_header": None, "row_y": node.get("y_hint"),
                "rule": "structured-kv-leaf", "confidence": "HIGH",
                "label_bbox": node.get("label_bbox"),
                "value_bboxes": [node.get("bbox")] if node.get("bbox") else [],
                "evidence": {"path": "/".join(path),
                             "engine_agreement": (ev or {}).get("engine_agreement", 0)},
            })

        elif t == "kv_group":
            for p in node.get("pairs", []) or []:
                label_x_hint = p.get("label_x_hint")
                value_x_hint = p.get("x_hint")
                lev = link_text_y(p.get("label"), p.get("y_hint"),
                                  x_hint=label_x_hint)
                partner = (lev or {}).get("cell_bbox") if isinstance(lev, dict) else None
                pval = p.get("value")
                is_empty = (pval is None or pval == "" or pval == "-")
                vev = link_text_y(pval, p.get("y_hint"), partner=partner,
                                  x_hint=value_x_hint) if not is_empty else None
                p["evidence"] = {"label": lev, "value": vev}
                if lev and lev.get("cell_bbox"): p["label_bbox"] = lev["cell_bbox"]
                if vev and vev.get("cell_bbox"):
                    p["bbox"] = vev["cell_bbox"]
                if is_empty:
                    stats["empty"] += 1
                else:
                    stats[f"{(vev or {}).get('engine_agreement', 0)}_eng"] += 1
                flat.append({
                    "label": p["label"], "value": p.get("value") or "",
                    "section": section_title, "band": band_title,
                    "column_header": None, "row_y": p.get("y_hint"),
                    "rule": "structured-kv-group", "confidence": "HIGH",
                    "label_bbox": p.get("label_bbox"),
                    "value_bboxes": [p.get("bbox")] if p.get("bbox") else [],
                    "evidence": {"path": "/".join(path),
                                 "engine_agreement": (vev or {}).get("engine_agreement", 0)},
                })
            bbs = [b for p in node.get("pairs", []) or []
                   for b in (p.get("bbox"), p.get("label_bbox")) if b]
            if bbs:
                node["container_bbox"] = _union_bbox(bbs)
            node["evidence"] = link_structural_node(eng, node, path)

        elif t == "table":
            table_title = node.get("title")
            cols = node.get("columns", [])
            for ri, row in enumerate(node.get("rows", []) or []):
                concepto_val = row.get(cols[0]["id"]) if cols else None
                concepto_text = concepto_val[0] if isinstance(concepto_val, tuple) else concepto_val
                concepto_y = concepto_val[1] if isinstance(concepto_val, tuple) else None
                for col in cols:
                    cid = col["id"]
                    if cid not in row:
                        continue
                    val = row[cid]
                    if val is None:
                        continue
                    # Extract the actual text for empty-detection (handles tuple values)
                    raw_text = val[0] if isinstance(val, tuple) else val
                    is_empty = (raw_text is None or raw_text == "" or raw_text == "-")
                    ev = link_text_y(val, concepto_y) if not is_empty else None
                    row[cid] = {
                        "text": raw_text,
                        "evidence": ev,
                        "bbox": (ev or {}).get("cell_bbox") if ev else None,
                    }
                    if cid == cols[0]["id"]:
                        continue
                    # Stats bucket
                    agree = 0
                    bucket = None
                    if is_empty:
                        stats["empty"] += 1
                        bucket = "empty"
                    else:
                        is_ref = isinstance(ev, dict) and "ref" in ev and ev.get("cell_bbox") is None
                        if is_ref:
                            stats["footnote_ref"] += 1
                            bucket = "footnote_ref"
                        else:
                            agree = (ev or {}).get("engine_agreement", 0) if ev else 0
                            stats[f"{agree}_eng"] += 1
                            bucket = f"{agree}_eng"
                    col_label = col.get("label", "")
                    group = col.get("group")
                    col_header = f"{group} / {col_label}" if group else col_label
                    cell_concept_bbox = (
                        row.get(cols[0]["id"], {}).get("bbox")
                        if isinstance(row.get(cols[0]["id"]), dict) else None
                    )
                    flat.append({
                        "label": str(concepto_text or ""),
                        "value": (str(row[cid]["text"]) if not isinstance(row[cid]["text"], dict)
                                  else f"→{row[cid]['text'].get('ref')}"),
                        "section": section_title, "band": table_title,
                        "column_header": col_header,
                        "row_y": concepto_y, "rule": "structured-table-cell",
                        "confidence": "HIGH",
                        "label_bbox": cell_concept_bbox,
                        "value_bboxes": [row[cid].get("bbox")] if row[cid].get("bbox") else [],
                        "evidence": {"path": "/".join(path), "row": ri,
                                     "engine_agreement": agree, "bucket": bucket},
                    })
            notes = node.get("notes") or {}
            for nid, ntext in notes.items():
                ev = link_text_y(ntext, node.get("notes_y_hint"))
                flat.append({
                    "label": nid, "value": ntext,
                    "section": section_title, "band": table_title,
                    "column_header": None, "row_y": node.get("notes_y_hint"),
                    "rule": "structured-footnote", "confidence": "HIGH",
                    "label_bbox": None,
                    "value_bboxes": [(ev or {}).get("cell_bbox")] if ev and ev.get("cell_bbox") else [],
                    "evidence": {"path": "/".join(path),
                                 "engine_agreement": (ev or {}).get("engine_agreement", 0)},
                })
                stats["footnote"] += 1
            bbs = []
            for row in node.get("rows", []) or []:
                for cid in [c["id"] for c in cols]:
                    cell = row.get(cid)
                    if isinstance(cell, dict) and cell.get("bbox"):
                        bbs.append(cell["bbox"])
            if bbs:
                node["bbox"] = _union_bbox(bbs)
            node["evidence"] = link_structural_node(eng, node, path)

        elif t == "array":
            for item in node.get("items", []) or []:
                idx = item.get("index")
                col_hdr = f"Titular {idx}" if idx else None
                for fname, sub in list(item.items()):
                    if not isinstance(sub, dict):
                        continue
                    sub_title = sub.get("title", fname)
                    for k, v in list(sub.items()):
                        if k in ("title", "y_hint"):
                            continue
                        if not isinstance(v, tuple):
                            continue
                        txt, y = v
                        if txt is None:
                            flat.append({
                                "label": k.replace("_", " "), "value": "",
                                "section": section_title, "band": sub_title,
                                "column_header": col_hdr, "row_y": y,
                                "rule": "structured-array-item-empty",
                                "confidence": "HIGH",
                                "label_bbox": None, "value_bboxes": [],
                                "evidence": {"path": "/".join(path), "item": idx},
                            })
                            stats["empty"] += 1
                            continue
                        ev = link_cell(eng, txt, y)
                        sub[k] = {"text": txt, "evidence": ev,
                                  "bbox": ev.get("cell_bbox")}
                        agree = ev.get("engine_agreement", 0)
                        stats[f"{agree}_eng"] += 1
                        flat.append({
                            "label": k.replace("_", " "), "value": txt,
                            "section": section_title, "band": sub_title,
                            "column_header": col_hdr, "row_y": y,
                            "rule": "structured-array-item", "confidence": "HIGH",
                            "label_bbox": None,
                            "value_bboxes": [ev.get("cell_bbox")] if ev.get("cell_bbox") else [],
                            "evidence": {"path": "/".join(path), "item": idx,
                                         "engine_agreement": agree},
                        })
            bbs = []
            for item in node.get("items", []) or []:
                for sub in item.values():
                    if not isinstance(sub, dict): continue
                    for vv in sub.values():
                        if isinstance(vv, dict) and vv.get("bbox"):
                            bbs.append(vv["bbox"])
            if bbs:
                node["container_bbox"] = _union_bbox(bbs)
            node["evidence"] = link_structural_node(eng, node, path)

        elif t == "prose_block":
            # Text-only paragraph block: produces a structure node + 0 KVs.
            # Used for legal preamble, descriptions, intro sentences.
            text = node.get("text") or ""
            ev = link_cell(eng, text, node.get("y_hint")) if text else None
            node["bbox"] = (ev or {}).get("cell_bbox")
            node["evidence"] = {
                "text_signal": ev,
                "structural_signals": {
                    "kind": "prose_block",
                    "label": node.get("label", "prose"),
                    "engine_agreement": (ev or {}).get("engine_agreement", 0),
                },
            }

        elif t == "noise":
            # Page footer/watermark/sidebar text. Goes into noise[] list, not kv_pairs.
            # Skipped from stats buckets (not value-bearing).
            text = node.get("text") or ""
            ev = link_cell(eng, text, node.get("y_hint")) if text else None
            node["bbox"] = (ev or {}).get("cell_bbox") or node.get("bbox")
            node["evidence"] = {
                "text_signal": ev,
                "kind": node.get("kind", "noise"),
            }

        elif t == "signature_placeholder":
            # Empty signature box: 1 empty KV + structure node with bbox.
            label = node.get("label", "Firma")
            lev = link_cell(eng, label, node.get("y_hint"))
            if lev and lev.get("cell_bbox"):
                node["label_bbox"] = lev["cell_bbox"]
                node["bbox"] = lev["cell_bbox"]
            node["evidence"] = {
                "label_signal": lev,
                "status": "empty",
                "structural_signals": {"kind": "signature_placeholder"},
            }
            stats["empty"] += 1
            flat.append({
                "label": label, "value": node.get("value") or "",
                "section": section_title, "band": band_title,
                "column_header": None, "row_y": node.get("y_hint"),
                "rule": "structured-signature-placeholder", "confidence": "HIGH",
                "label_bbox": node.get("label_bbox"),
                "value_bboxes": [],
                "evidence": {"path": "/".join(path),
                             "engine_agreement": (lev or {}).get("engine_agreement", 0),
                             "bucket": "empty"},
            })

        elif t == "free_text_list":
            for it in node.get("items", []) or []:
                lev = link_cell(eng, it["label"], it.get("y_hint"))
                partner = (lev or {}).get("cell_bbox") if lev else None
                ival = it.get("value")
                is_empty = (ival is None or ival == "" or ival == "-")
                vev = (link_cell(eng, ival, it.get("y_hint"), partner_bbox=partner)
                       if not is_empty else None)
                it["label_evidence"] = lev; it["value_evidence"] = vev
                if lev and lev.get("cell_bbox"): it["label_bbox"] = lev["cell_bbox"]
                if vev and vev.get("cell_bbox"):
                    it["bbox"] = vev["cell_bbox"]
                if is_empty:
                    stats["empty"] += 1
                else:
                    stats[f"{(vev or {}).get('engine_agreement', 0)}_eng"] += 1
                flat.append({
                    "label": it["label"], "value": it.get("value", ""),
                    "section": section_title, "band": node.get("title"),
                    "column_header": None, "row_y": it.get("y_hint"),
                    "rule": "structured-free-text-item", "confidence": "HIGH",
                    "label_bbox": it.get("label_bbox"),
                    "value_bboxes": [it.get("bbox")] if it.get("bbox") else [],
                    "evidence": {"path": "/".join(path),
                                 "engine_agreement": (vev or {}).get("engine_agreement", 0)},
                })
            bbs = [b for it in node.get("items", []) or []
                   for b in (it.get("bbox"), it.get("label_bbox")) if b]
            if bbs:
                node["container_bbox"] = _union_bbox(bbs)
            node["evidence"] = link_structural_node(eng, node, path)

    for n in structure:
        visit(n, [])
    return structure, flat, stats
