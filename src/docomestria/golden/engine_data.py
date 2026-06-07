"""EngineData — loads pdfplumber chars + LiteParse spans + Docling blocks for
one PDF page and provides all geometric/text matchers used by the golden
builder.

The PDF is read once; atoms must already be cached at
.planning/extraction/atoms/<pdf-stem>-p<NN>.atoms.json by scripts/extract_atoms.py.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pdfplumber  # type: ignore[import-not-found]


def _norm(s: str) -> str:
    """lowercase + strip accents + collapse whitespace — for text matching."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower().strip())


class EngineData:
    """All engine output for one PDF page, in page-relative pt coordinates."""

    def __init__(self, pdf_path: Path, atoms_path: Path, page_num: int = 1):
        self.pdf_path = Path(pdf_path)
        self.atoms_path = Path(atoms_path)
        self.page_num = page_num
        self._load()

    def _load(self) -> None:
        with pdfplumber.open(str(self.pdf_path)) as pdf:
            page = pdf.pages[self.page_num - 1]
            self.off = float(page.mediabox[1])
            self.width, self.height = page.width, page.height
            raw_chars = page.chars
        # Normalise chars: page-relative y
        self.chars: list[dict] = []
        for c in raw_chars:
            self.chars.append({
                "text": c["text"],
                "x0": float(c["x0"]), "x1": float(c["x1"]),
                "y": float(c["top"]) - self.off,
                "y_bot": float(c["bottom"]) - self.off,
                "size": float(c.get("size") or 0),
                "fontname": c.get("fontname", ""),
            })
        # Group chars into y-rows + reconstruct text with smart spaces
        rows: list[dict] = []
        for c in self.chars:
            placed = False
            for r in rows:
                if abs(r["y"] - c["y"]) < 3:
                    r["chars"].append(c)
                    r["y"] = min(r["y"], c["y"])
                    placed = True
                    break
            if not placed:
                rows.append({"y": c["y"], "chars": [c]})
        rows.sort(key=lambda r: r["y"])
        self.rows: list[dict] = []
        for r in rows:
            chs = sorted(r["chars"], key=lambda c: c["x0"])
            text = ""
            pos_map: list = []
            last_x1 = None
            for ch in chs:
                if last_x1 is not None and (ch["x0"] - last_x1) > 1.2:
                    text += " "; pos_map.append(None)
                text += ch["text"]; pos_map.append(ch)
                last_x1 = ch["x1"]
            self.rows.append({"y": r["y"], "text": text,
                              "pos_map": pos_map, "chars": chs})
        # Atoms
        atoms_doc = json.loads(self.atoms_path.read_text(encoding="utf-8"))
        # Validate: atoms file must match the PDF + page we're building for.
        # Without this, evidence is silently false when paths are swapped.
        atoms_pdf = atoms_doc.get("pdf") or ""
        atoms_page = atoms_doc.get("page")
        if atoms_pdf:
            atoms_pdf_stem = Path(atoms_pdf).stem
            if atoms_pdf_stem != self.pdf_path.stem:
                raise ValueError(
                    f"Atoms/PDF mismatch:\n"
                    f"  atoms says pdf={atoms_pdf_stem!r}\n"
                    f"  builder asked for pdf={self.pdf_path.stem!r}\n"
                    f"  atoms_path={self.atoms_path}"
                )
        if atoms_page is not None and int(atoms_page) != int(self.page_num):
            raise ValueError(
                f"Atoms/page mismatch:\n"
                f"  atoms says page={atoms_page}\n"
                f"  builder asked for page={self.page_num}\n"
                f"  atoms_path={self.atoms_path}"
            )
        self.atoms = atoms_doc
        self.spans = atoms_doc["atoms"]["spans"]
        self.rects = atoms_doc["atoms"]["rects"]
        self.blocks = atoms_doc["atoms"]["blocks"]

    # ----- char-level text matching ---------------------------------------
    def find_char_bbox(self, target: str, y_hint: float | None = None,
                       y_tolerance: float = 25) -> dict | None:
        """Find bbox + char_indices for a row segment matching `target`."""
        if not target or target == "-":
            return None
        target_n = _norm(target)
        if not target_n:
            return None
        best = None
        best_dist = float("inf")
        for r in self.rows:
            if y_hint is not None and abs(r["y"] - y_hint) > y_tolerance:
                continue
            txt_n = _norm(r["text"])
            idx = txt_n.find(target_n)
            if idx < 0:
                continue
            # Build per-raw-char → norm-index map
            raw_to_norm: list[int] = []
            raw_norm_text = ""
            for ch in r["text"]:
                if not ch.strip():
                    nch = " "
                else:
                    nch = "".join(c for c in unicodedata.normalize("NFKD", ch.lower())
                                  if not unicodedata.combining(c))
                if nch == " " and raw_norm_text.endswith(" "):
                    raw_to_norm.append(len(raw_norm_text) - 1)
                    continue
                raw_norm_text += nch
                raw_to_norm.append(len(raw_norm_text) - 1)
            try:
                norm_start = idx
                norm_end = idx + len(target_n) - 1
                raw_start = next(i for i, n in enumerate(raw_to_norm) if n >= norm_start)
                raw_end = next(i for i, n in enumerate(raw_to_norm) if n >= norm_end)
            except StopIteration:
                continue
            pm = r["pos_map"]
            cs = raw_start
            while cs < len(pm) and pm[cs] is None:
                cs += 1
            ce = raw_end
            while ce > 0 and (ce >= len(pm) or pm[ce] is None):
                ce -= 1
            if cs > ce:
                continue
            matched = [pm[i] for i in range(cs, ce + 1) if pm[i] is not None]
            if not matched:
                continue
            x0 = min(c["x0"] for c in matched)
            x1 = max(c["x1"] for c in matched)
            y0 = min(c["y"] for c in matched)
            y1 = max(c["y_bot"] for c in matched)
            char_idx = [self.chars.index(c) for c in matched]
            dist = 0 if y_hint is None else abs(r["y"] - y_hint)
            if dist < best_dist:
                best_dist = dist
                best = {
                    "bbox": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0},
                    "char_indices": char_idx,
                    "row_y": r["y"],
                }
        return best

    # ----- LiteParse span matching ----------------------------------------
    def find_span(self, target: str, y_hint: float | None = None,
                  y_tolerance: float = 25) -> tuple[int | None, dict | None]:
        if not target or target == "-":
            return None, None
        target_n = _norm(target)
        best_id, best_span, best_dist = None, None, float("inf")
        for i, sp in enumerate(self.spans):
            sp_n = _norm(sp.get("text", ""))
            if target_n in sp_n or sp_n in target_n:
                sy = sp.get("bbox", {}).get("y", 0)
                if y_hint is not None and abs(sy - y_hint) > y_tolerance:
                    continue
                dist = 0 if y_hint is None else abs(sy - y_hint)
                if dist < best_dist:
                    best_id, best_span, best_dist = i, sp, dist
        return best_id, best_span

    # ----- Docling block / table-cell matching ----------------------------
    def find_docling_cell(self, target: str, y_hint: float | None = None,
                          y_tolerance: float = 25) -> tuple[str | None, dict | None]:
        if not target or target == "-":
            return None, None
        target_n = _norm(target)
        for b in self.blocks:
            if b.get("label") != "table":
                continue
            cells = b.get("cells") or []
            for ri, row in enumerate(cells):
                if not isinstance(row, list):
                    row = [row]
                for ci, c in enumerate(row):
                    if not isinstance(c, dict):
                        continue
                    ctxt = _norm(c.get("text") or "")
                    if not ctxt:
                        continue
                    if target_n in ctxt or ctxt in target_n:
                        bbox = c.get("bbox")
                        if y_hint is not None and bbox:
                            if abs(bbox.get("y", 0) - y_hint) > y_tolerance:
                                continue
                        return f"{b.get('self_ref')}/cells[{ri}][{ci}]", c
        for b in self.blocks:
            btxt = _norm(b.get("text") or "")
            if not btxt:
                continue
            if target_n in btxt or btxt in target_n:
                bbox = b.get("bbox")
                if y_hint is not None and bbox:
                    if abs(bbox.get("y", 0) - y_hint) > y_tolerance + 30:
                        continue
                return b.get("self_ref"), b
        return None, None

    # ----- containing pdfplumber rect (smallest containing) ---------------
    def find_rect(self, bbox: dict) -> tuple[str | None, dict | None]:
        if not bbox:
            return None, None
        cx = bbox["x"] + bbox["w"] / 2
        cy = bbox["y"] + bbox["h"] / 2
        best, best_area = None, float("inf")
        for r in self.rects:
            rb = r.get("bbox")
            if not rb:
                continue
            if rb["x"] <= cx <= rb["x"] + rb["w"] and rb["y"] <= cy <= rb["y"] + rb["h"]:
                area = rb["w"] * rb["h"]
                if area < best_area:
                    best_area, best = area, r
        if best:
            return best.get("id"), best
        return None, None

    def find_enclosing_rect(self, bbox: dict) -> tuple[str | None, dict | None]:
        """Smallest substantial rect that fully encloses bbox."""
        if not bbox:
            return None, None
        x0, y0 = bbox["x"], bbox["y"]
        x1, y1 = x0 + bbox["w"], y0 + bbox["h"]
        best, best_area = None, float("inf")
        for r in self.rects:
            if not r.get("is_substantial"):
                continue
            rb = r.get("bbox")
            if not rb:
                continue
            rx0, ry0 = rb["x"], rb["y"]
            rx1, ry1 = rx0 + rb["w"], ry0 + rb["h"]
            if rx0 <= x0 + 2 and ry0 <= y0 + 2 and rx1 >= x1 - 2 and ry1 >= y1 - 2:
                area = rb["w"] * rb["h"]
                if area < best_area:
                    best_area, best = area, r
        if best:
            return best.get("id"), best
        return None, None

    def find_enclosing_docling_block(self, bbox: dict,
                                     prefer_labels: tuple = ()) -> dict | None:
        if not bbox:
            return None
        x0, y0 = bbox["x"], bbox["y"]
        x1, y1 = x0 + bbox["w"], y0 + bbox["h"]
        best, best_score = None, float("inf")
        for b in self.blocks:
            bb = b.get("bbox")
            if not bb:
                continue
            bx0, by0 = bb["x"], bb["y"]
            bx1, by1 = bx0 + bb["w"], by0 + bb["h"]
            if bx0 <= x0 + 3 and by0 <= y0 + 3 and bx1 >= x1 - 3 and by1 >= y1 - 3:
                area = bb["w"] * bb["h"]
                bonus = -1e9 if (b.get("label") in prefer_labels) else 0
                score = area + bonus
                if score < best_score:
                    best_score, best = score, b
        return best

    def count_edges_inside(self, bbox: dict) -> dict:
        if not bbox:
            return {"vertical": 0, "horizontal": 0}
        x0, y0 = bbox["x"], bbox["y"]
        x1, y1 = x0 + bbox["w"], y0 + bbox["h"]
        v = sum(1 for e in self.atoms["atoms"].get("vertical_edges", [])
                if x0 <= e.get("x", 1e9) <= x1
                and e.get("y1", 0) >= y0 and e.get("y0", 1e9) <= y1)
        h = sum(1 for e in self.atoms["atoms"].get("horizontal_edges", [])
                if y0 <= e.get("y", 1e9) <= y1
                and e.get("x1", 0) >= x0 and e.get("x0", 1e9) <= x1)
        return {"vertical": v, "horizontal": h}

    # ----- colon detector (KV signal) -------------------------------------
    @property
    def colons(self) -> list[dict]:
        if not hasattr(self, "_colons"):
            self._colons = [c for c in self.chars if c["text"] == ":"]
        return self._colons

    def colons_inside(self, bbox: dict) -> int:
        if not bbox:
            return 0
        x0, y0 = bbox["x"], bbox["y"]
        x1, y1 = x0 + bbox["w"], y0 + bbox["h"]
        return sum(1 for c in self.colons
                   if x0 <= c["x0"] <= x1 and y0 <= c["y"] <= y1)

    def colon_between(self, label_bbox: dict, value_bbox: dict,
                      y_tolerance: float = 4) -> dict | None:
        if not label_bbox or not value_bbox:
            return None
        l_right = label_bbox["x"] + label_bbox["w"]
        v_left = value_bbox["x"]
        if v_left < l_right:
            l_right, v_left = value_bbox["x"] + value_bbox["w"], label_bbox["x"]
        row_y = (label_bbox["y"] + value_bbox["y"]) / 2
        for c in self.colons:
            if abs(c["y"] - row_y) > y_tolerance:
                continue
            if l_right - 2 <= c["x0"] <= v_left + 2:
                return {"x": c["x0"], "y": c["y"], "size": c["size"]}
        return None

    def detect_value_extent(self, value_bbox: dict,
                            container_rect_bbox: dict | None = None,
                            y_tolerance: float = 4) -> dict:
        """Classify what signal ENDS the value's extent on the right."""
        if not value_bbox:
            return {"boundary_type": "unknown"}
        v_right = value_bbox["x"] + value_bbox["w"]
        v_y = value_bbox["y"] + value_bbox["h"] / 2
        right_chars = [c for c in self.chars
                       if c["x0"] > v_right - 1
                       and abs(c["y"] - v_y) < y_tolerance + 4]
        right_chars.sort(key=lambda c: c["x0"])
        if not right_chars:
            if container_rect_bbox:
                cell_right = container_rect_bbox["x"] + container_rect_bbox["w"]
                return {"boundary_type": "cell_edge",
                        "gap_pt": cell_right - v_right,
                        "ends_at_x": cell_right}
            return {"boundary_type": "row_end", "gap_pt": None}
        next_ch = right_chars[0]
        gap = next_ch["x0"] - v_right
        next_colon = next((c for c in right_chars if c["text"] == ":"), None)
        if next_colon:
            between = sorted(
                (c for c in right_chars if c["x0"] < next_colon["x0"]),
                key=lambda c: c["x0"],
            )
            next_label_text = "".join(c["text"] for c in between).strip()
            return {
                "boundary_type": "next_colon_label",
                "gap_pt": gap,
                "next_label_text": next_label_text,
                "next_colon_x": next_colon["x0"],
                "ends_at_x": between[0]["x0"] if between else next_colon["x0"],
            }
        if next_ch["text"] == "," or (gap < 2 and next_ch["text"] == ","):
            after_comma = [c for c in right_chars if c["x0"] > next_ch["x1"]]
            tail = "".join(c["text"] for c in after_comma).strip()[:60]
            return {"boundary_type": "comma_separator",
                    "gap_pt": gap, "tail_after_comma": tail,
                    "ends_at_x": next_ch["x0"]}
        if gap > 15:
            return {"boundary_type": "cell_edge",
                    "gap_pt": gap, "ends_at_x": next_ch["x0"]}
        return {"boundary_type": "continuation",
                "gap_pt": gap,
                "next_text": "".join(c["text"] for c in right_chars[:8])}

    def detect_repeats(self, target: str, y_tolerance: float = 5) -> list[dict]:
        if not target:
            return []
        target_n = _norm(target)
        hits = []
        for sp in self.spans:
            sp_n = _norm(sp.get("text", ""))
            if target_n in sp_n or sp_n in target_n:
                hits.append({"source": "liteparse", "bbox": sp.get("bbox"),
                             "y": sp.get("bbox", {}).get("y")})
        for r in self.rows:
            if target_n in _norm(r["text"]):
                hits.append({"source": "chars", "bbox": None, "y": r["y"]})
        return hits
