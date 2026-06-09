"""Viewer with two layers on page 1 of a PDF:
- pdfplumber substantial rects (each a different HSV color)
- Docling blocks (color-coded by label: text, list_item, table, …)

Usage:
    PYTHONPATH=src python3 scripts/view_boxes_p1.py <pdf-path> [--port 8770]
"""

from __future__ import annotations

import argparse
import colorsys
import http.server
import json
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVE_DIR = ROOT / ".viewer"
DPI = 144

DOCLING_PALETTE = {
    "text": "#4a90e2",
    "list_item": "#5ac8fa",
    "section_header": "#ff3b30",
    "title": "#ff9500",
    "table": "#ff9500",
    "picture": "#af52de",
    "caption": "#34c759",
    "page_header": "#8e8e93",
    "page_footer": "#8e8e93",
    "footnote": "#8e8e93",
    "form_item": "#ff2d55",
    "checkbox_selected": "#34c759",
    "checkbox_unselected": "#c7c7cc",
    "_default": "#a0522d",
}


def _palette(n: int) -> list[str]:
    out = []
    for i in range(n):
        h = (i / max(1, n)) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 0.95)
        out.append(f"rgb({int(r*255)},{int(g*255)},{int(b*255)})")
    return out


def collect_pdfplumber_rects(pdf_path: Path, page_num: int = 1):
    """Substantial vector rects on a page (w>50, h>20), deduplicated."""
    import pdfplumber  # type: ignore[import-not-found]

    out = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_num - 1]
        media_lly = float(page.mediabox[1])
        seen = set()
        for r in page.rects or []:
            w = float(r["x1"]) - float(r["x0"])
            h = float(r["bottom"]) - float(r["top"])
            if w < 50 or h < 20:
                continue
            x = float(r["x0"])
            y = float(r["top"]) - media_lly
            key = (round(x), round(y), round(w), round(h))
            if key in seen:
                continue
            seen.add(key)
            out.append({"x": x, "y": y, "w": w, "h": h})
    out.sort(key=lambda b: (b["y"], b["x"]))
    return out


def _nav_html(current: int, pages: tuple[int, ...]) -> str:
    pages = tuple(sorted(set(pages)))
    if len(pages) <= 1:
        return f"<span style='color:#8e8e93'>page {current}</span>"
    links = []
    idx = pages.index(current) if current in pages else -1
    if idx > 0:
        prev_p = pages[idx - 1]
        links.append(f'<a href="boxes_p{prev_p}.html">← p{prev_p}</a>')
    for p in pages:
        cls = "active" if p == current else ""
        links.append(f'<a href="boxes_p{p}.html" class="{cls}">p{p}</a>')
    if idx >= 0 and idx < len(pages) - 1:
        next_p = pages[idx + 1]
        links.append(f'<a href="boxes_p{next_p}.html">p{next_p} →</a>')
    return " ".join(links)


def cluster_subtables(rects: list[dict], gap: float = 8.0) -> list[dict]:
    """Group leaf rects into sub-table clusters via connected-component
    adjacency (horizontal or vertical neighbors).

    Two rects belong to the same cluster when either:
      - their y-bands overlap (>=50% of the shorter one) AND their x-edges
        touch within ``gap`` pt → horizontal neighbors (same row), or
      - their x-bands overlap (>=50%) AND their y-edges touch within
        ``gap`` pt → vertical neighbors (same column).

    Container rects (those enclosing >=3 other rects) are dropped first so
    the outer "table" frames don't swallow the inner structure.
    """
    def contains(a: dict, b: dict, tol: float = 1.0) -> bool:
        return (a["x"] - tol <= b["x"]
                and a["y"] - tol <= b["y"]
                and a["x"] + a["w"] + tol >= b["x"] + b["w"]
                and a["y"] + a["h"] + tol >= b["y"] + b["h"]
                and (a["w"] * a["h"]) > (b["w"] * b["h"]) * 1.1)

    leaves = []
    for r in rects:
        nested = sum(1 for o in rects if o is not r and contains(r, o))
        if nested >= 3:
            continue
        leaves.append(r)

    n = len(leaves)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b

    EDGE_TOL = 4.0
    for i in range(n):
        a = leaves[i]
        ax0, ay0 = a["x"], a["y"]
        ax1, ay1 = a["x"] + a["w"], a["y"] + a["h"]
        for j in range(i + 1, n):
            b = leaves[j]
            bx0, by0 = b["x"], b["y"]
            bx1, by1 = b["x"] + b["w"], b["y"] + b["h"]
            x_gap = max(ax0, bx0) - min(ax1, bx1)
            y_gap = max(ay0, by0) - min(ay1, by1)
            # Horizontal neighbor (same row): same top AND same bottom AND
            # touching/overlapping in x.
            same_row = (abs(ay0 - by0) <= EDGE_TOL
                        and abs(ay1 - by1) <= EDGE_TOL
                        and x_gap <= gap)
            # Vertical neighbor (same column): same left AND same right AND
            # touching/overlapping in y.
            same_col = (abs(ax0 - bx0) <= EDGE_TOL
                        and abs(ax1 - bx1) <= EDGE_TOL
                        and y_gap <= gap)
            if same_row or same_col:
                union(i, j)

    groups: dict[int, list[dict]] = {}
    for i, r in enumerate(leaves):
        groups.setdefault(find(i), []).append(r)

    clusters = []
    for grp in groups.values():
        x0 = min(r["x"] for r in grp)
        y0 = min(r["y"] for r in grp)
        x1 = max(r["x"] + r["w"] for r in grp)
        y1 = max(r["y"] + r["h"] for r in grp)
        rows = len({round(r["y"] / 5) for r in grp})
        cols = len({round(r["x"] / 5) for r in grp})
        clusters.append({
            "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
            "cells": len(grp), "rows": rows, "cols": cols,
        })
    clusters.sort(key=lambda c: (c["y"], c["x"]))
    return clusters


def collect_pdfplumber_tables(pdf_path: Path, page_num: int = 1):
    """Tables detected by pdfplumber's find_tables() on a page."""
    import pdfplumber  # type: ignore[import-not-found]

    out = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_num - 1]
        media_lly = float(page.mediabox[1])
        page_w_pt = float(page.width)
        page_h_pt = float(page.height)
        try:
            tables = page.find_tables() or []
        except Exception:
            tables = []
        for tidx, t in enumerate(tables):
            bbox = getattr(t, "bbox", None)
            if bbox is None:
                continue
            x0, top, x1, bottom = bbox
            n_rows = len(getattr(t, "rows", None) or [])
            n_cols = 0
            rows = getattr(t, "rows", None) or []
            if rows:
                n_cols = max(len(getattr(r, "cells", None) or []) for r in rows)
            out.append({
                "x": float(x0),
                "y": float(top) - media_lly,
                "w": float(x1 - x0),
                "h": float(bottom - top),
                "rows": n_rows,
                "cols": n_cols,
                "id": f"p{page_num}-t{tidx}",
            })
    out.sort(key=lambda b: (b["y"], b["x"]))
    return out, page_w_pt, page_h_pt


def _case_class(text: str) -> str:
    """Classify a text span by letter case.

    Returns one of: ``UPPER`` (>=80% letters are upper), ``lower`` (>=80%
    are lower), ``Title`` (each word starts upper, rest lower —
    >=70% of words match), ``mixed`` (everything else with letters),
    ``none`` (no letters at all).
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "none"
    up = sum(1 for c in letters if c.isupper())
    lo = sum(1 for c in letters if c.islower())
    if up / len(letters) >= 0.80:
        return "UPPER"
    if lo / len(letters) >= 0.80:
        return "lower"
    # Title-case heuristic: each word starts with upper letter.
    words = [w for w in text.split() if any(ch.isalpha() for ch in w)]
    if words:
        starts_upper = sum(1 for w in words
                           if next((c for c in w if c.isalpha()), "").isupper())
        if starts_upper / len(words) >= 0.70:
            return "Title"
    return "mixed"


def collect_lite_cases(pdf_path: Path, page_num: int = 1):
    """LiteParse spans on a page annotated with their case class."""
    from docomestria.engines import extract_lite_items

    out = []
    for it in extract_lite_items(str(pdf_path)):
        if it.page != page_num:
            continue
        b = it.bbox
        text = it.text or ""
        out.append({
            "x": b.x, "y": b.y, "w": b.w, "h": b.h,
            "text": text[:80], "case": _case_class(text),
            "size": it.font_size or 0.0,
        })
    return out


def collect_lite_all(pdf_path: Path, page_num: int = 1):
    """All LiteParse v2 spans on a page (enriched: bold, case, size)."""
    from docomestria.engines import extract_lite_items
    from docomestria.structural.classify import is_bold

    out = []
    for it in extract_lite_items(str(pdf_path)):
        if it.page != page_num:
            continue
        b = it.bbox
        text = it.text or ""
        out.append({
            "x": b.x, "y": b.y, "w": b.w, "h": b.h,
            "text": text,
            "bold": is_bold(it.font_name),
            "case": _case_class(text),
            "size": it.font_size or 0.0,
        })
    return out


_NUM_TOKEN = __import__("re").compile(r"\b\d[\d.,/\-]*\b")


def annotate_boxes_with_content(boxes: list[dict], lite_all: list[dict]) -> None:
    """For each box, compute numeric + case stats from spans inside it.

    A span is "inside" a box when its bbox center lies within the box.
    Adds: ``digit_ratio``, ``n_nums``, ``n_chars``, ``samples``,
    plus ``cases`` ({UPPER,Title,lower,mixed,none}→count) and
    ``case_label`` = the dominant case (UPPER/Title/lower/mixed).
    """
    for box in boxes:
        bx0 = box["x"]; by0 = box["y"]
        bx1 = bx0 + box["w"]; by1 = by0 + box["h"]
        chars_total = 0
        chars_digit = 0
        nums: list[str] = []
        cases: dict[str, int] = {}
        for sp in lite_all:
            cx = sp["x"] + sp["w"] / 2
            cy = sp["y"] + sp["h"] / 2
            if not (bx0 <= cx <= bx1 and by0 <= cy <= by1):
                continue
            text = sp["text"]
            chars_total += len(text)
            chars_digit += sum(1 for ch in text if ch.isdigit())
            nums.extend(_NUM_TOKEN.findall(text))
            cl = _case_class(text)
            cases[cl] = cases.get(cl, 0) + 1
        box["n_chars"] = chars_total
        box["digit_ratio"] = (chars_digit / chars_total) if chars_total else 0.0
        box["n_nums"] = len(nums)
        box["samples"] = nums[:3]
        box["cases"] = cases
        # Dominant case excluding 'none'.
        letter_cases = {k: v for k, v in cases.items() if k != "none"}
        box["case_label"] = (
            max(letter_cases, key=letter_cases.get) if letter_cases else "none"
        )


def collect_lite_bold(pdf_path: Path, page_num: int = 1):
    """LiteParse v2 bold spans on a page (font name matches bold tokens)."""
    from docomestria.engines import extract_lite_items
    from docomestria.structural.classify import is_bold

    out = []
    for it in extract_lite_items(str(pdf_path)):
        if it.page != page_num or not is_bold(it.font_name):
            continue
        b = it.bbox
        out.append({
            "x": b.x, "y": b.y, "w": b.w, "h": b.h,
            "text": (it.text or "")[:120],
            "font": it.font_name or "",
            "size": it.font_size or 0.0,
        })
    out.sort(key=lambda b: (b["y"], b["x"]))
    return out


def collect_docling_tables(pdf_path: Path, page_num: int = 1):
    """Docling blocks labelled 'table' on a page."""
    from docomestria.engines import extract_docling_blocks

    blocks = extract_docling_blocks(str(pdf_path))
    out = []
    for b in blocks:
        if b.page != page_num or b.label != "table":
            continue
        bb = b.bbox
        n_rows = len(b.cells) if b.cells else 0
        n_cols = max((len(r) for r in b.cells), default=0) if b.cells else 0
        out.append({
            "x": bb.x,
            "y": bb.y,
            "w": bb.w,
            "h": bb.h,
            "rows": n_rows,
            "cols": n_cols,
            "text": (b.text or "")[:80],
        })
    out.sort(key=lambda b: (b["y"], b["x"]))
    return out


ROLE_COLOR = {
    "LABEL":         "#5ac8fa",   # cyan — bold lower text
    "VALUE_NUMERIC": "#ff9500",   # orange — has digits
    "VALUE_TEXT":    "#ff2d55",   # magenta — UPPER text content
    "HEADER":        "#ff3b30",   # red — bold UPPER
    "SUB_HEADER":    "#34c759",   # green — bold lower (sub-section)
    "CLARIFIER":     "#ffd60a",   # yellow — parenthetical
    "EMPTY":         "#3a3a3c",   # dark gray
    "MIXED":         "#8e8e93",   # gray
}


def _guess_role(profile: dict) -> str:
    """Map a per-cell profile dict to a role tag."""
    if profile["n_spans"] == 0:
        return "EMPTY"
    case = profile["case_dom"]
    bold = profile["bold_ratio"]
    digit = profile["digit_ratio"]
    sample = profile.get("sample_text", "")
    if sample.startswith("(") and case == "lower":
        return "CLARIFIER"
    if bold >= 0.5 and case == "UPPER":
        return "HEADER"
    if bold >= 0.5 and case == "lower":
        return "SUB_HEADER"
    if bold >= 0.5:
        return "LABEL"
    if digit >= 0.25 or case == "none":
        return "VALUE_NUMERIC"
    if case == "UPPER":
        return "VALUE_TEXT"
    if case == "lower":
        return "LABEL"
    return "MIXED"


def profile_rects(rects: list[dict], lite_all: list[dict]) -> None:
    """Mutate each rect to add a content profile + role guess.

    Adds: ``n_spans``, ``case_dom``, ``bold_ratio``, ``digit_ratio``,
    ``size_median``, ``sample_text``, ``role``.
    """
    from statistics import median

    for r in rects:
        rx0, ry0 = r["x"], r["y"]
        rx1, ry1 = rx0 + r["w"], ry0 + r["h"]
        inside = []
        for sp in lite_all:
            cx = sp["x"] + sp["w"] / 2
            cy = sp["y"] + sp["h"] / 2
            if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
                inside.append(sp)
        if not inside:
            r.update(n_spans=0, case_dom="empty", bold_ratio=0.0,
                     digit_ratio=0.0, size_median=0.0, sample_text="",
                     role="EMPTY")
            continue
        cases = {}
        bold = 0
        digit_chars = 0
        chars = 0
        sizes = []
        for sp in inside:
            cl = sp.get("case") or _case_class(sp["text"])
            cases[cl] = cases.get(cl, 0) + 1
            if sp.get("bold"):
                bold += 1
            text = sp["text"]
            chars += len(text)
            digit_chars += sum(c.isdigit() for c in text)
            sz = sp.get("size") or 0.0
            if sz:
                sizes.append(sz)
        # Dominant case excluding 'none' if possible.
        letter_cases = {k: v for k, v in cases.items() if k != "none"}
        case_dom = (max(letter_cases, key=letter_cases.get)
                    if letter_cases else max(cases, key=cases.get))
        sample = inside[0]["text"]
        profile = {
            "n_spans": len(inside),
            "case_dom": case_dom,
            "bold_ratio": bold / len(inside),
            "digit_ratio": (digit_chars / chars) if chars else 0.0,
            "size_median": median(sizes) if sizes else 0.0,
            "sample_text": sample,
        }
        profile["role"] = _guess_role(profile)
        r.update(profile)


def column_coherence(rects: list[dict], tol: float = 4.0) -> list[dict]:
    """Group rects into x-band columns and report role coherence.

    Returns list of {x0, x1, n_rects, role_dist, coherent_role}.
    """
    groups: dict[tuple[float, float], list[dict]] = {}
    for r in rects:
        x0 = round(r["x"] / tol) * tol
        x1 = round((r["x"] + r["w"]) / tol) * tol
        groups.setdefault((x0, x1), []).append(r)
    out = []
    for (x0, x1), grp in groups.items():
        roles: dict[str, int] = {}
        for r in grp:
            roles[r["role"]] = roles.get(r["role"], 0) + 1
        top_role, top_n = max(roles.items(), key=lambda kv: kv[1])
        coherent = top_role if top_n / len(grp) >= 0.8 else None
        out.append({
            "x0": x0, "x1": x1, "n_rects": len(grp),
            "role_dist": roles, "coherent_role": coherent,
        })
    return sorted(out, key=lambda c: c["x0"])


CASE_COLOR = {
    "UPPER": "#ff3b30",   # red
    "Title": "#34c759",   # green
    "lower": "#5ac8fa",   # cyan
    "mixed": "#ff9500",   # orange
    "none":  "#8e8e93",   # gray
}


def build_html(image_url: str, plumber: list[dict], docling: list[dict],
               rects: list[dict], clusters: list[dict], bold: list[dict],
               cases: list[dict],
               page_w_pt: float, page_h_pt: float, pdf_name: str,
               page_num: int = 1, all_pages: tuple[int, ...] = (1,)) -> str:
    scale = DPI / 72.0
    img_w = int(round(page_w_pt * scale))
    img_h = int(round(page_h_pt * scale))

    P_COLOR = "#ff9500"  # pdfplumber tables — orange
    D_COLOR = "#34c759"  # docling tables — green
    R_COLOR = "#8e8e93"  # raw substantial rects — gray
    B_COLOR = "#ff2d55"  # liteparse bold spans — magenta/red

    p_overlays, p_legend = [], []
    for i, b in enumerate(plumber, start=1):
        x = b["x"] * scale; y = b["y"] * scale
        w = b["w"] * scale; h = b["h"] * scale
        p_overlays.append(
            f'<div class="box plumber" style="left:{x:.1f}px;top:{y:.1f}px;'
            f'width:{w:.1f}px;height:{h:.1f}px;border-color:{P_COLOR};'
            f'background:rgba(255,149,0,0.10);">'
            f'<span class="tag" style="background:{P_COLOR}">P{i} {b["rows"]}×{b["cols"]}</span></div>'
        )
        p_legend.append(
            f'<li><span class="swatch" style="background:{P_COLOR}"></span>'
            f'P{i} &nbsp; {b["w"]:.0f}×{b["h"]:.0f} pt &nbsp; grid {b["rows"]}×{b["cols"]}</li>'
        )

    d_overlays, d_legend_items = [], []
    for i, b in enumerate(docling, start=1):
        x = b["x"] * scale; y = b["y"] * scale
        w = b["w"] * scale; h = b["h"] * scale
        title = (b.get("text") or "").replace('"', '&quot;')
        d_overlays.append(
            f'<div class="box docling" title="{title}" '
            f'style="left:{x:.1f}px;top:{y:.1f}px;'
            f'width:{w:.1f}px;height:{h:.1f}px;border-color:{D_COLOR};'
            f'background:rgba(52,199,89,0.10);">'
            f'<span class="tag" style="background:{D_COLOR}">D{i} {b["rows"]}×{b["cols"]}</span></div>'
        )
        d_legend_items.append(
            f'<li><span class="swatch" style="background:{D_COLOR}"></span>'
            f'D{i} &nbsp; {b["w"]:.0f}×{b["h"]:.0f} pt &nbsp; cells {b["rows"]}×{b["cols"]}</li>'
        )

    r_overlays, r_legend_items = [], []
    for i, b in enumerate(rects, start=1):
        x = b["x"] * scale; y = b["y"] * scale
        w = b["w"] * scale; h = b["h"] * scale
        r_overlays.append(
            f'<div class="box rect" style="left:{x:.1f}px;top:{y:.1f}px;'
            f'width:{w:.1f}px;height:{h:.1f}px;border-color:{R_COLOR};">'
            f'<span class="tag" style="background:{R_COLOR}">R{i}</span></div>'
        )
        r_legend_items.append(
            f'<li><span class="swatch" style="background:{R_COLOR}"></span>'
            f'R{i} &nbsp; {b["w"]:.0f}×{b["h"]:.0f} pt @ ({b["x"]:.0f},{b["y"]:.0f})</li>'
        )

    c_palette = _palette(max(1, len(clusters)))
    c_overlays, c_legend_items = [], []
    for i, (b, c) in enumerate(zip(clusters, c_palette), start=1):
        x = b["x"] * scale; y = b["y"] * scale
        w = b["w"] * scale; h = b["h"] * scale
        bg = c.replace("rgb(", "rgba(").replace(")", ",0.12)")
        ratio = b.get("digit_ratio", 0.0)
        n_nums = b.get("n_nums", 0)
        if n_nums == 0:
            num_badge = "txt"
        elif ratio >= 0.5:
            num_badge = f"NUM {n_nums}"
        else:
            num_badge = f"#{n_nums}"
        samples = ", ".join(b.get("samples", []))
        case_lbl = b.get("case_label", "—")
        case_col = CASE_COLOR.get(case_lbl, "#8e8e93")
        c_overlays.append(
            f'<div class="box cluster" style="left:{x:.1f}px;top:{y:.1f}px;'
            f'width:{w:.1f}px;height:{h:.1f}px;border-color:{c};background:{bg};">'
            f'<span class="tag" style="background:{c}">S{i} {b["rows"]}×{b["cols"]} · {num_badge} · '
            f'<span style="background:{case_col};padding:0 4px;border-radius:2px">{case_lbl}</span></span></div>'
        )
        c_legend_items.append(
            f'<li><span class="swatch" style="background:{c}"></span>'
            f'S{i} &nbsp; {b["w"]:.0f}×{b["h"]:.0f} pt · '
            f'{b["cells"]} cells · grid {b["rows"]}×{b["cols"]} · '
            f'<strong>{num_badge}</strong> ({ratio*100:.0f}% dig) · '
            f'<span style="color:{case_col}">{case_lbl}</span> '
            f'<em style="color:#8e8e93">{samples}</em></li>'
        )

    b_overlays, b_legend_items = [], []
    for i, sp in enumerate(bold, start=1):
        x = sp["x"] * scale; y = sp["y"] * scale
        w = sp["w"] * scale; h = sp["h"] * scale
        title = f'{sp["font"]} {sp["size"]:.1f}pt — {sp["text"]}'.replace('"', '&quot;')
        b_overlays.append(
            f'<div class="box bold" title="{title}" '
            f'style="left:{x:.1f}px;top:{y:.1f}px;'
            f'width:{w:.1f}px;height:{h:.1f}px;border-color:{B_COLOR};'
            f'background:rgba(255,45,85,0.18);"></div>'
        )
    # Compact legend (just summary)
    b_legend_html = (
        f'<li><span class="swatch" style="background:{B_COLOR}"></span>'
        f'{len(bold)} bold spans (hover for text+font)</li>'
        if bold else '<li style="color:#8e8e93">— none —</li>'
    )

    # Cell-role overlays — one per rect, coloured by inferred role.
    role_overlays = []
    role_counts: dict[str, int] = {}
    for r in rects:
        role = r.get("role", "EMPTY")
        role_counts[role] = role_counts.get(role, 0) + 1
        color = ROLE_COLOR.get(role, "#8e8e93")
        x = r["x"] * scale; y = r["y"] * scale
        w = r["w"] * scale; h = r["h"] * scale
        bg = (
            "rgba(" + ",".join(str(int(color.lstrip("#")[j:j+2], 16))
                               for j in (0, 2, 4)) + ",0.20)"
        )
        sample = (r.get("sample_text") or "")[:60].replace('"', '&quot;')
        title = (f'{role} · case={r.get("case_dom","-")} · '
                 f'bold={r.get("bold_ratio",0)*100:.0f}% · '
                 f'digits={r.get("digit_ratio",0)*100:.0f}% · '
                 f'size={r.get("size_median",0):.1f} · "{sample}"')
        role_overlays.append(
            f'<div class="box role" title="{title}" '
            f'style="left:{x:.1f}px;top:{y:.1f}px;'
            f'width:{w:.1f}px;height:{h:.1f}px;border-color:{color};'
            f'background:{bg};">'
            f'<span class="tag" style="background:{color}">{role[:4]}</span></div>'
        )
    role_legend = "".join(
        f'<li><span class="swatch" style="background:{ROLE_COLOR.get(rl, "#8e8e93")}"></span>'
        f'<strong>{rl}</strong> &times;{n}</li>'
        for rl, n in sorted(role_counts.items(), key=lambda kv: -kv[1])
    ) or '<li style="color:#8e8e93">— none —</li>'

    # Column coherence summary.
    col_bands = column_coherence(rects)
    col_legend = "".join(
        f'<li><code>x={b["x0"]:.0f}-{b["x1"]:.0f}</code> ({b["n_rects"]} cells) → '
        f'<strong style="color:{ROLE_COLOR.get(b["coherent_role"], "#8e8e93")}">'
        f'{b["coherent_role"] or "mixed"}</strong> '
        f'<em style="color:#8e8e93">{b["role_dist"]}</em></li>'
        for b in col_bands
    ) or '<li style="color:#8e8e93">— none —</li>'

    case_overlays = []
    case_counts: dict[str, int] = {}
    for sp in cases:
        cl = sp["case"]
        case_counts[cl] = case_counts.get(cl, 0) + 1
        color = CASE_COLOR.get(cl, "#8e8e93")
        x = sp["x"] * scale; y = sp["y"] * scale
        w = sp["w"] * scale; h = sp["h"] * scale
        bg = (
            "rgba(" + ",".join(str(int(color.lstrip("#")[j:j+2], 16))
                               for j in (0, 2, 4)) + ",0.20)"
        )
        title = f'{cl} · size={sp["size"]:.1f} · {sp["text"]}'.replace('"', '&quot;')
        case_overlays.append(
            f'<div class="box case" title="{title}" '
            f'style="left:{x:.1f}px;top:{y:.1f}px;'
            f'width:{w:.1f}px;height:{h:.1f}px;border-color:{color};'
            f'background:{bg};"></div>'
        )
    case_legend = "".join(
        f'<li><span class="swatch" style="background:{CASE_COLOR.get(cl, "#8e8e93")}"></span>'
        f'<strong>{cl}</strong> &times;{n}</li>'
        for cl, n in sorted(case_counts.items(), key=lambda kv: -kv[1])
    ) or '<li style="color:#8e8e93">— none —</li>'

    p_legend_html = "".join(p_legend) or '<li style="color:#8e8e93">— none —</li>'
    d_legend_html = "".join(d_legend_items) or '<li style="color:#8e8e93">— none —</li>'
    r_legend_html = "".join(r_legend_items) or '<li style="color:#8e8e93">— none —</li>'
    c_legend_html = "".join(c_legend_items) or '<li style="color:#8e8e93">— none —</li>'

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Boxes p1 — {pdf_name}</title>
<style>
  body {{ margin:0; font-family:-apple-system,system-ui,sans-serif;
         background:#1d1d1f; color:#e1e1e3; display:grid;
         grid-template-columns:1fr 340px; height:100vh; }}
  header {{ grid-column:1/-1; padding:8px 16px; background:#000;
            border-bottom:1px solid #333; font-size:13px;
            display:flex; gap:16px; align-items:center; }}
  header h1 {{ font-size:14px; margin:0; font-weight:600; }}
  .nav a {{ color:#00d4ff; text-decoration:none; padding:2px 6px;
            border-radius:3px; font-size:12px; }}
  .nav a:hover {{ background:#2c2c2e; }}
  .nav a.active {{ background:#00d4ff; color:#000; font-weight:600; }}
  body {{ grid-template-rows:auto 1fr; }}
  #pane {{ overflow:auto; padding:16px; background:#2c2c2e; }}
  .page {{ position:relative; width:{img_w}px; height:{img_h}px;
           margin:0 auto; box-shadow:0 4px 20px rgba(0,0,0,0.6); background:#fff; }}
  .page img {{ display:block; width:100%; height:100%; }}
  .box {{ position:absolute; border:2px solid; border-radius:2px;
          box-sizing:border-box; pointer-events:auto; }}
  .box.docling {{ border-style:dashed; }}
  .box.rect {{ border-style:dotted; border-width:1px;
                background:transparent !important; }}
  .box.cluster {{ border-width:3px; }}
  .box.bold {{ border-width:1px; }}
  .box.case {{ border-width:1px; }}
  .box.role {{ border-width:2px; }}
  .page.drawing {{ cursor:crosshair; }}
  .page.drawing img {{ pointer-events:none; }}
  .page.drawing .box {{ pointer-events:none; }}
  #draw-rect {{ position:absolute; border:2px solid #00d4ff;
                background:rgba(0,212,255,0.15); pointer-events:none;
                box-sizing:border-box; display:none; }}
  .userbox {{ position:absolute; border:2px solid #00d4ff;
              background:rgba(0,212,255,0.10); box-sizing:border-box;
              pointer-events:auto; }}
  .userbox .tag {{ position:absolute; top:-12px; left:-2px;
                   background:#00d4ff; color:#000; font-weight:700;
                   font-family:ui-monospace,monospace; padding:1px 6px;
                   font-size:10px; border-radius:3px; }}
  #draw-toggle {{ background:#00d4ff; color:#000; border:none;
                  padding:4px 12px; border-radius:4px; cursor:pointer;
                  font-weight:600; font-size:12px; }}
  #draw-toggle.active {{ background:#ff2d55; color:#fff; }}
  #user-panel {{ margin-top:16px; padding-top:12px;
                 border-top:1px solid #333; }}
  #user-list li {{ display:flex; justify-content:space-between;
                    align-items:center; gap:8px; }}
  #user-list button {{ background:none; border:1px solid #555; color:#e1e1e3;
                       padding:1px 6px; border-radius:3px; cursor:pointer;
                       font-size:10px; }}
  #user-actions {{ display:flex; gap:6px; margin-top:6px; }}
  #user-actions button {{ flex:1; background:#2c2c2e; color:#e1e1e3;
                          border:1px solid #444; padding:4px 8px;
                          border-radius:4px; cursor:pointer; font-size:11px; }}
  #coord-readout {{ font-family:ui-monospace,monospace; color:#00d4ff;
                    margin-left:auto; font-size:11px; }}
  .box.docling:hover {{ background:rgba(255,255,255,0.25) !important; z-index:10; }}
  .tag {{ position:absolute; top:-12px; left:-2px; color:#fff;
          font-size:9px; padding:1px 5px; border-radius:3px;
          font-weight:700; font-family:ui-monospace,monospace; }}
  #legend {{ overflow:auto; padding:12px; background:#1d1d1f;
             border-left:1px solid #333; font-size:12px; }}
  #legend h2 {{ font-size:11px; text-transform:uppercase; letter-spacing:1px;
                color:#8e8e93; margin:12px 0 6px; }}
  #legend ul {{ list-style:none; margin:0; padding:0; }}
  #legend li {{ padding:3px 6px; border-bottom:1px solid #2c2c2e;
                font-family:ui-monospace,monospace; font-size:11px; }}
  .swatch {{ display:inline-block; width:10px; height:10px;
             margin-right:8px; vertical-align:middle; border-radius:2px; }}
  .toggle {{ display:flex; gap:8px; }}
  .toggle label {{ display:flex; align-items:center; gap:4px;
                   cursor:pointer; user-select:none; }}
</style></head><body>
<header>
  <h1>{pdf_name}</h1>
  <span class="nav">{_nav_html(page_num, all_pages)}</span>
  <span>{len(plumber)} pdfplumber · {len(docling)} docling · {len(rects)} raw · {len(clusters)} sub-tables · {len(bold)} bold</span>
  <span class="toggle">
    <label><input type="checkbox" id="t_plumber"> pdfplumber</label>
    <label><input type="checkbox" id="t_docling"> docling</label>
    <label><input type="checkbox" id="t_rects"> raw rects</label>
    <label><input type="checkbox" id="t_clusters" checked> sub-tables</label>
    <label><input type="checkbox" id="t_bold" checked> bold (lite)</label>
    <label><input type="checkbox" id="t_case"> case (lite)</label>
    <label><input type="checkbox" id="t_roles" checked> cell roles</label>
  </span>
  <button id="draw-toggle">✏ Draw box</button>
  <span id="coord-readout">—</span>
</header>
<div id="pane">
  <div class="page">
    <img src="{image_url}" alt="page 1">
    <div id="layer_plumber" style="display:none">{''.join(p_overlays)}</div>
    <div id="layer_docling" style="display:none">{''.join(d_overlays)}</div>
    <div id="layer_rects" style="display:none">{''.join(r_overlays)}</div>
    <div id="layer_clusters">{''.join(c_overlays)}</div>
    <div id="layer_bold">{''.join(b_overlays)}</div>
    <div id="layer_case" style="display:none">{''.join(case_overlays)}</div>
    <div id="layer_roles">{''.join(role_overlays)}</div>
    <div id="layer_user"></div>
    <div id="draw-rect"></div>
  </div>
</div>
<aside id="legend">
  <h2>sub-tables (clustering)</h2>
  <ul>{c_legend_html}</ul>
  <h2>bold spans (liteparse v2)</h2>
  <ul>{b_legend_html}</ul>
  <h2>text case (liteparse v2)</h2>
  <ul>{case_legend}</ul>
  <h2>cell roles (per pdfplumber rect)</h2>
  <ul>{role_legend}</ul>
  <h2>column coherence (x-bands)</h2>
  <ul>{col_legend}</ul>
  <h2>pdfplumber tables</h2>
  <ul>{p_legend_html}</ul>
  <h2>docling tables</h2>
  <ul>{d_legend_html}</ul>
  <h2>raw rects (w&gt;50, h&gt;20)</h2>
  <ul>{r_legend_html}</ul>
  <div id="user-panel">
    <h2>your annotations</h2>
    <ul id="user-list"></ul>
    <div id="user-actions">
      <button id="btn-copy">Copy JSON</button>
      <button id="btn-clear">Clear all</button>
    </div>
    <p style="color:#8e8e93;font-size:11px;margin-top:8px">
      Click &quot;✏ Draw box&quot;, then drag on the page. Coords in PDF pt,
      page-relative (top-left origin). Auto-saved to
      <code>.viewer/annotations.json</code>.
    </p>
  </div>
</aside>
<script>
  const bind = (cb, layer, on) => {{
    const el = document.getElementById(layer);
    el.style.display = on ? '' : 'none';
    document.getElementById(cb).checked = on;
    document.getElementById(cb).onchange = e => el.style.display = e.target.checked ? '' : 'none';
  }};
  bind('t_plumber', 'layer_plumber', false);
  bind('t_docling', 'layer_docling', false);
  bind('t_rects', 'layer_rects', false);
  bind('t_clusters', 'layer_clusters', true);
  bind('t_bold', 'layer_bold', true);
  bind('t_case', 'layer_case', false);
  bind('t_roles', 'layer_roles', true);

  // ── Draw mode: click-drag to make a rectangle. Coords reported in PDF pt. ──
  const SCALE = {DPI / 72.0};
  const pageEl = document.querySelector('.page');
  const drawRect = document.getElementById('draw-rect');
  const userLayer = document.getElementById('layer_user');
  const userList = document.getElementById('user-list');
  const readout = document.getElementById('coord-readout');
  const toggle = document.getElementById('draw-toggle');
  const PAGE_W = {page_w_pt:.3f};
  const PAGE_H = {page_h_pt:.3f};

  let drawing = false;
  let active = false;
  let start = null;
  const userBoxes = [];

  toggle.onclick = () => {{
    active = !active;
    toggle.classList.toggle('active', active);
    toggle.textContent = active ? '✕ Stop drawing' : '✏ Draw box';
    pageEl.classList.toggle('drawing', active);
  }};

  function pageCoords(ev) {{
    const r = pageEl.getBoundingClientRect();
    return {{
      px: ev.clientX - r.left,
      py: ev.clientY - r.top,
    }};
  }}

  pageEl.addEventListener('mousedown', (ev) => {{
    if (!active) return;
    ev.preventDefault();
    const {{ px, py }} = pageCoords(ev);
    drawing = true;
    start = {{ px, py }};
    drawRect.style.left = px + 'px';
    drawRect.style.top = py + 'px';
    drawRect.style.width = '0px';
    drawRect.style.height = '0px';
    drawRect.style.display = 'block';
  }});

  pageEl.addEventListener('mousemove', (ev) => {{
    if (!drawing) return;
    const {{ px, py }} = pageCoords(ev);
    const x = Math.min(start.px, px);
    const y = Math.min(start.py, py);
    const w = Math.abs(px - start.px);
    const h = Math.abs(py - start.py);
    drawRect.style.left = x + 'px';
    drawRect.style.top = y + 'px';
    drawRect.style.width = w + 'px';
    drawRect.style.height = h + 'px';
    readout.textContent = `x=${{(x/SCALE).toFixed(1)}}  y=${{(y/SCALE).toFixed(1)}}  w=${{(w/SCALE).toFixed(1)}}  h=${{(h/SCALE).toFixed(1)}} pt`;
  }});

  pageEl.addEventListener('mouseup', (ev) => {{
    if (!drawing) return;
    drawing = false;
    drawRect.style.display = 'none';
    const {{ px, py }} = pageCoords(ev);
    const px0 = Math.min(start.px, px);
    const py0 = Math.min(start.py, py);
    const w = Math.abs(px - start.px);
    const h = Math.abs(py - start.py);
    if (w < 4 || h < 4) return;
    const box = {{
      x: px0 / SCALE,
      y: py0 / SCALE,
      w: w / SCALE,
      h: h / SCALE,
      page: 1,
    }};
    userBoxes.push(box);
    renderUserBoxes();
    persist();
  }});

  function renderUserBoxes() {{
    userLayer.innerHTML = '';
    userList.innerHTML = '';
    userBoxes.forEach((b, i) => {{
      const div = document.createElement('div');
      div.className = 'userbox';
      div.style.left = (b.x * SCALE) + 'px';
      div.style.top = (b.y * SCALE) + 'px';
      div.style.width = (b.w * SCALE) + 'px';
      div.style.height = (b.h * SCALE) + 'px';
      const tag = document.createElement('span');
      tag.className = 'tag';
      tag.textContent = 'U' + (i + 1);
      div.appendChild(tag);
      userLayer.appendChild(div);

      const li = document.createElement('li');
      li.innerHTML = `<span><strong>U${{i+1}}</strong> <code>x=${{b.x.toFixed(1)}} y=${{b.y.toFixed(1)}} w=${{b.w.toFixed(1)}} h=${{b.h.toFixed(1)}}</code></span>`;
      const del = document.createElement('button');
      del.textContent = '✕';
      del.onclick = () => {{ userBoxes.splice(i, 1); renderUserBoxes(); persist(); }};
      li.appendChild(del);
      userList.appendChild(li);
    }});
  }}

  function persist() {{
    fetch('/annotations', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        pdf: {json.dumps(pdf_name)},
        page: 1,
        page_w: PAGE_W,
        page_h: PAGE_H,
        boxes: userBoxes,
      }}),
    }}).catch(() => {{}});
  }}

  document.getElementById('btn-copy').onclick = async () => {{
    const j = JSON.stringify(userBoxes, null, 2);
    try {{ await navigator.clipboard.writeText(j); readout.textContent = 'copied!'; }}
    catch {{ window.prompt('Copy JSON:', j); }}
  }};
  document.getElementById('btn-clear').onclick = () => {{
    userBoxes.length = 0;
    renderUserBoxes();
    persist();
  }};

  // Keyboard shortcut: D toggles draw mode.
  document.addEventListener('keydown', (ev) => {{
    if (ev.key === 'd' || ev.key === 'D') toggle.click();
    if (ev.key === 'Escape' && active) toggle.click();
  }});
</script>
</body></html>
"""


ANNOTATIONS_PATH = SERVE_DIR / "annotations.json"


class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        return

    def do_POST(self):  # noqa: N802
        if self.path != "/annotations":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            self.send_error(400, "bad json")
            return
        ANNOTATIONS_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[annotations] saved {len(payload.get('boxes', []))} box(es) → "
              f"{ANNOTATIONS_PATH}")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


def _process_page(pdf_path: Path, pn: int, all_pages: tuple[int, ...]) -> Path:
    print(f"=== page {pn} of {pdf_path.name} ===")
    plumber, page_w, page_h = collect_pdfplumber_tables(pdf_path, pn)
    print(f"  pdfplumber: {len(plumber)} table(s)")
    rects = collect_pdfplumber_rects(pdf_path, pn)
    print(f"  pdfplumber: {len(rects)} substantial rect(s)")
    clusters = cluster_subtables(rects)
    print(f"  clusters: {len(clusters)}")
    lite_all = collect_lite_all(pdf_path, pn)
    bold = collect_lite_bold(pdf_path, pn)
    cases = collect_lite_cases(pdf_path, pn)
    case_counts: dict[str, int] = {}
    for sp in cases:
        case_counts[sp["case"]] = case_counts.get(sp["case"], 0) + 1
    print(f"  liteparse: {len(lite_all)} spans, {len(bold)} bold, "
          f"cases={dict(sorted(case_counts.items(), key=lambda kv: -kv[1]))}")
    annotate_boxes_with_content(clusters, lite_all)
    profile_rects(rects, lite_all)
    role_counts: dict[str, int] = {}
    for r in rects:
        role_counts[r["role"]] = role_counts.get(r["role"], 0) + 1
    print(f"  cell roles: {dict(sorted(role_counts.items(), key=lambda kv: -kv[1]))}")
    col_bands = column_coherence(rects)
    print(f"  column bands: {len(col_bands)}")
    for b in col_bands:
        print(f"    x={b['x0']:.0f}-{b['x1']:.0f}  n={b['n_rects']}  "
              f"→ {b['coherent_role'] or 'mixed'}  {b['role_dist']}")

    cache = SERVE_DIR / f".docling-tables-{pdf_path.stem}-p{pn}.json"
    if cache.exists():
        docling = json.loads(cache.read_text())
        print(f"  docling: {len(docling)} table(s) (cached)")
    else:
        print(f"  docling: running model …")
        docling = collect_docling_tables(pdf_path, pn)
        cache.write_text(json.dumps(docling))
        print(f"  docling: {len(docling)} table(s)")

    img_stem = f"page{pn}-{pdf_path.stem}"
    img_path = SERVE_DIR / f"{img_stem}-{pn:02d}.png"
    if not img_path.exists():
        import subprocess
        subprocess.run(
            ["/opt/homebrew/bin/pdftoppm", "-r", str(DPI),
             "-f", str(pn), "-l", str(pn),
             "-png", str(pdf_path), str(SERVE_DIR / img_stem)],
            check=True,
        )

    html = build_html(f"/{img_path.name}", plumber, docling, rects, clusters,
                      bold, cases, page_w, page_h, f"{pdf_path.name}",
                      page_num=pn, all_pages=all_pages)
    out_html = SERVE_DIR / f"boxes_p{pn}.html"
    out_html.write_text(html, encoding="utf-8")
    return out_html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--page", type=int, default=None,
                    help="single page (alias for --pages N)")
    ap.add_argument("--pages", type=str, default=None,
                    help="comma list, e.g. '1,2,3' or '1-3'")
    ap.add_argument("--all-pages", action="store_true",
                    help="process every page of the PDF")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return 2

    # Resolve page list.
    if args.all_pages:
        import pdfplumber  # type: ignore[import-not-found]
        with pdfplumber.open(str(pdf_path)) as pdf:
            page_list = tuple(range(1, len(pdf.pages) + 1))
    elif args.pages:
        s = set()
        for tok in args.pages.split(","):
            tok = tok.strip()
            if "-" in tok:
                a, b = tok.split("-", 1)
                s.update(range(int(a), int(b) + 1))
            elif tok:
                s.add(int(tok))
        page_list = tuple(sorted(s))
    else:
        page_list = (args.page or 1,)

    SERVE_DIR.mkdir(exist_ok=True)
    first_html = None
    for pn in page_list:
        out = _process_page(pdf_path, pn, page_list)
        if first_html is None:
            first_html = out

    import os
    os.chdir(SERVE_DIR)
    with socketserver.TCPServer(("127.0.0.1", args.port), _Handler) as srv:
        url = f"http://127.0.0.1:{args.port}/{first_html.name}"
        print(f"Serving at {url}  (Ctrl-C to stop)")
        if not args.no_browser:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
