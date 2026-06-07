"""Visual review viewer for all golden KIE extractions.

Reads every .planning/extraction/golden/*.json, resolves the source PDF,
renders each page on demand, overlays sections + KV pair bboxes, and
serves a single-page HTML where you can browse PDFs/pages with a sidebar.

Usage:
    PYTHONPATH=src python3 scripts/view_goldens.py [--port 8772]
"""

from __future__ import annotations

import argparse
import http.server
import io
import json
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import pdfplumber  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / ".planning" / "extraction" / "golden"
ATOMS_DIR = ROOT / ".planning" / "extraction" / "atoms"
CACHE_DIR = ROOT / ".viewer" / "golden_cache"
DATASET_ROOT = Path("/Users/carlos/Edelwyss/Projects/docomestria/Dataset")
DPI = 144  # pdfplumber default = 72; 2× → crisp without huge files


def _resolve_pdf(pdf_field: str) -> Path | None:
    """Best-effort resolution of the `pdf` field in a golden JSON."""
    p = Path(pdf_field)
    if p.is_absolute() and p.exists():
        return p
    # Try as relative to Dataset root
    direct = DATASET_ROOT / pdf_field
    if direct.exists():
        return direct
    # Search by basename across Dataset
    stem = p.name if p.name.endswith(".pdf") else p.name + ".pdf"
    for cand in DATASET_ROOT.rglob("*.pdf"):
        if cand.name == stem or cand.stem == p.stem:
            return cand
    return None


def _golden_stem_to_atoms(golden_path: Path) -> Path:
    """Atoms file lives at .planning/extraction/atoms/<same-stem>.atoms.json."""
    stem = golden_path.stem  # e.g. "BBVA_0608-...-p02"
    return ATOMS_DIR / f"{stem}.atoms.json"


def _index_goldens() -> list[dict]:
    """Scan goldens, group by PDF, return a flat list of entries."""
    entries = []
    for gp in sorted(GOLDEN_DIR.glob("*.json")):
        try:
            d = json.loads(gp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[skip broken] {gp.name}: {e}", file=sys.stderr)
            continue
        pdf_path = _resolve_pdf(d.get("pdf", ""))
        if pdf_path is None:
            print(f"[skip no pdf] {gp.name}", file=sys.stderr)
            continue
        # Counts for sidebar badges
        kvs = d.get("kv_pairs", [])
        sec = d.get("sections", [])
        h = sum(1 for k in kvs if (k.get("confidence") or "").upper() == "HIGH")
        m = sum(1 for k in kvs if (k.get("confidence") or "").upper() == "MEDIUM")
        l = sum(1 for k in kvs if (k.get("confidence") or "").upper() == "LOW")
        entries.append({
            "golden_path": str(gp),
            "pdf_path": str(pdf_path),
            "pdf_name": pdf_path.name,
            "page": int(d.get("page", 1)),
            "sections": len(sec),
            "kv": len(kvs),
            "high": h,
            "medium": m,
            "low": l,
        })
    return entries


def _render_page_png(pdf_path: Path, page_num: int) -> bytes:
    """Render one page to PNG (cached). Returns bytes."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = pdf_path.stem.replace(" ", "_")
    cache = CACHE_DIR / f"{safe_name}-p{page_num:02d}-{DPI}.png"
    if cache.exists():
        return cache.read_bytes()
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_num - 1]
        im = page.to_image(resolution=DPI)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        png = buf.getvalue()
    cache.write_bytes(png)
    return png


def _enrich_golden(golden_path: Path) -> dict:
    """Read golden + resolve bboxes from atoms (spans) or sections (cells).

    Strategy per KV:
      1. evidence.label_span_id → atoms.spans[id].bbox  (fine-grained)
      2. fallback: find cell in sections.bands.rows whose text == kv.label
         (used when extractor only had docling_block_id / rect_id evidence).
    """
    d = json.loads(golden_path.read_text(encoding="utf-8"))
    atoms_path = _golden_stem_to_atoms(golden_path)
    spans = []
    if atoms_path.exists():
        try:
            atoms = json.loads(atoms_path.read_text(encoding="utf-8"))
            spans = atoms.get("atoms", {}).get("spans", [])
        except Exception:
            spans = []

    def span_bbox(span_id):
        if span_id is None:
            return None
        try:
            sp = spans[span_id]
            return sp.get("bbox")
        except (IndexError, TypeError):
            return None

    # Build a text → bbox map from all cells (for fallback)
    cell_by_text: dict[str, list[dict]] = {}
    for sec in d.get("sections", []) or []:
        for band in sec.get("bands", []) or []:
            for row in band.get("rows", []) or []:
                for cell in row.get("cells", []) or []:
                    txt = (cell.get("text") or "").strip()
                    bx = cell.get("bbox")
                    if txt and bx:
                        cell_by_text.setdefault(txt, []).append(bx)

    def fallback_bbox(text: str | None, row_y: float | None):
        """Find the cell bbox best matching `text` (and closest row_y)."""
        if not text:
            return None
        text = text.strip()
        cands = cell_by_text.get(text) or []
        if not cands:
            # try partial match (first 30 chars)
            key = next((k for k in cell_by_text if k.startswith(text[:30])), None)
            if key:
                cands = cell_by_text[key]
        if not cands:
            return None
        if row_y is None or len(cands) == 1:
            return cands[0]
        # pick closest by y
        return min(cands, key=lambda b: abs((b.get("y") or 0) - row_y))

    enriched_kvs = []
    for k in d.get("kv_pairs", []):
        ev = k.get("evidence", {}) or {}
        row_y = k.get("row_y")
        # Preserve any hand-set bbox; only resolve if not present
        label_bbox = k.get("label_bbox")
        if not label_bbox:
            label_bbox = span_bbox(ev.get("label_span_id"))
        if not label_bbox:
            label_bbox = fallback_bbox(k.get("label"), row_y)

        existing_vbb = k.get("value_bboxes") or []
        value_bboxes = [b for b in existing_vbb if b]  # keep non-null hand-set
        if not value_bboxes:
            for vid in ev.get("value_span_ids") or []:
                b = span_bbox(vid)
                if b:
                    value_bboxes.append(b)
        if not value_bboxes:
            vb = fallback_bbox(k.get("value"), row_y)
            if vb:
                value_bboxes.append(vb)
        enriched_kvs.append({
            **k,
            "label_bbox": label_bbox,
            "value_bboxes": value_bboxes,
        })
    d["kv_pairs"] = enriched_kvs
    return d


# --- HTML --------------------------------------------------------------------

HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Golden KIE review</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, system-ui, sans-serif;
    background: #f5f5f7; color: #1d1d1f;
    display: grid;
    grid-template-columns: 260px 1fr 380px;
    grid-template-rows: 44px 1fr;
    height: 100vh; overflow: hidden;
  }
  header {
    grid-column: 1 / -1; grid-row: 1;
    background: #1d1d1f; color: #fff; padding: 0 14px;
    display: flex; align-items: center; gap: 16px; font-size: 13px;
  }
  header h1 { font-size: 14px; margin: 0; font-weight: 600; }
  header .stats { color: #c7c7cc; margin-left: auto; font-size: 12px; }
  header .toggles { display: flex; gap: 8px; }
  header .toggle {
    background: rgba(255,255,255,0.1); padding: 4px 8px;
    border-radius: 4px; cursor: pointer; user-select: none; font-size: 11px;
  }
  header .toggle.on { background: #007aff; color: white; }
  /* Sidebar */
  aside.sidebar {
    grid-row: 2; grid-column: 1; overflow-y: auto;
    background: #fff; border-right: 1px solid #d2d2d7;
    padding: 6px 0; font-size: 12px;
  }
  .pdf-group { border-bottom: 1px solid #f0f0f2; }
  .pdf-title {
    font-weight: 600; padding: 8px 10px; cursor: pointer;
    display: flex; justify-content: space-between; gap: 6px;
    background: #fafafa;
  }
  .pdf-title:hover { background: #f0f0f2; }
  .pdf-title .badge {
    font-size: 10px; color: #6e6e73; font-weight: 400;
  }
  .page-item {
    padding: 5px 10px 5px 24px; cursor: pointer;
    display: flex; justify-content: space-between; gap: 4px;
  }
  .page-item:hover { background: #f0f7ff; }
  .page-item.active { background: #007aff; color: white; }
  .page-item.active .conf { color: white; }
  .conf-row { display: flex; gap: 3px; align-items: center; font-size: 10px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .dot.H { background: #34c759; }
  .dot.M { background: #ff9500; }
  .dot.L { background: #ff3b30; }
  /* Main */
  main {
    grid-row: 2; grid-column: 2;
    overflow: auto; padding: 16px;
    display: flex; justify-content: center; align-items: flex-start;
  }
  #page-container { position: relative; }
  #page-container img { display: block; box-shadow: 0 2px 12px rgba(0,0,0,0.15); border-radius: 4px; }
  .overlay-svg {
    position: absolute; left: 0; top: 0; pointer-events: none;
  }
  .ov-label { fill: rgba(0, 122, 255, 0.15); stroke: rgba(0, 122, 255, 0.85); stroke-width: 1.5; }
  .ov-value { fill: rgba(52, 199, 89, 0.15); stroke: rgba(52, 199, 89, 0.85); stroke-width: 1.5; }
  .ov-section { fill: none; stroke: rgba(255, 149, 0, 0.7); stroke-width: 1.5; stroke-dasharray: 4 3; }
  .ov-section-title { fill: rgba(255, 149, 0, 0.25); stroke: rgba(255, 149, 0, 0.9); stroke-width: 1; }
  .ov-noise { fill: rgba(142, 142, 147, 0.12); stroke: rgba(142, 142, 147, 0.6); stroke-width: 1; stroke-dasharray: 2 2; }
  .ov-label.active, .ov-value.active { fill-opacity: 0.45; stroke-width: 2.5; }
  /* KV panel */
  aside.kvpanel {
    grid-row: 2; grid-column: 3;
    overflow-y: auto; background: #fff; border-left: 1px solid #d2d2d7;
    font-size: 12px; padding: 8px;
  }
  .tabs-bar {
    display: flex; gap: 2px; margin-bottom: 8px;
    border-bottom: 1px solid #d2d2d7;
  }
  .tab-btn {
    flex: 1; padding: 6px 8px; background: none; border: none;
    cursor: pointer; font-size: 11px; font-weight: 600;
    color: #6e6e73; border-bottom: 2px solid transparent;
  }
  .tab-btn.active { color: #007aff; border-bottom-color: #007aff; }
  .tab-btn:hover { background: #f5f5f7; }
  /* JSON tree view */
  #json-view {
    font-family: ui-monospace, "SF Mono", Consolas, monospace;
    font-size: 11px; line-height: 1.45; color: #1d1d1f;
  }
  #json-view .toolbar {
    display: flex; gap: 4px; margin-bottom: 6px;
  }
  #json-view .toolbar button {
    padding: 3px 6px; font-size: 10px; background: #f5f5f7;
    border: 1px solid #d2d2d7; border-radius: 4px; cursor: pointer;
  }
  .jt-node { padding-left: 12px; border-left: 1px dotted transparent; }
  .jt-toggle {
    display: inline-block; width: 12px; cursor: pointer; user-select: none;
    color: #8e8e93; font-size: 9px;
  }
  .jt-key { color: #af52de; font-weight: 600; }
  .jt-string { color: #c41a16; }
  .jt-number { color: #1c00cf; }
  .jt-bool { color: #aa0d91; }
  .jt-null { color: #8e8e93; font-style: italic; }
  .jt-row {
    padding: 1px 4px; border-radius: 2px;
    border-left: 2px solid transparent; cursor: default;
  }
  .jt-row.has-bbox { cursor: pointer; }
  .jt-row.has-bbox:hover { background: #f0f7ff; border-left-color: #007aff; }
  .jt-row.active { background: #e8f0fe; border-left-color: #007aff; }
  .jt-collapsed > .jt-children { display: none; }
  .jt-collapsed > .jt-row > .jt-summary { color: #8e8e93; }
  .jt-summary { color: #8e8e93; font-style: italic; }
  .jt-engine-tag {
    display: inline-block; padding: 0 4px; margin-left: 4px;
    font-size: 9px; border-radius: 2px; font-weight: 600;
    background: #34c759; color: white;
  }
  .jt-engine-tag.partial { background: #ff9500; }
  .jt-engine-tag.none { background: #ff3b30; }
  .filter-bar {
    display: flex; gap: 6px; margin-bottom: 10px;
    padding: 6px; background: #f5f5f7; border-radius: 6px;
  }
  .filter-bar button {
    flex: 1; padding: 4px 8px; border: 1px solid #d2d2d7;
    background: white; border-radius: 4px; cursor: pointer;
    font-size: 11px; font-weight: 600;
  }
  .filter-bar button.on.H { background: #34c759; color: white; border-color: #34c759; }
  .filter-bar button.on.M { background: #ff9500; color: white; border-color: #ff9500; }
  .filter-bar button.on.L { background: #ff3b30; color: white; border-color: #ff3b30; }
  .sec-block { margin-bottom: 12px; }
  .sec-title {
    font-weight: 600; font-size: 11px; text-transform: uppercase;
    color: #8e8e93; padding: 4px 6px; border-bottom: 1px solid #d2d2d7;
    margin-bottom: 4px; letter-spacing: 0.3px;
  }
  .kv-row {
    padding: 6px 8px; border-radius: 4px; margin: 2px 0;
    cursor: pointer; border-left: 3px solid transparent;
    transition: background 0.1s;
  }
  .kv-row:hover { background: #f5f5f7; }
  .kv-row.active { background: #e8f0fe; border-left-color: #007aff; }
  .kv-row.H { border-left-color: #34c759; }
  .kv-row.M { border-left-color: #ff9500; }
  .kv-row.L { border-left-color: #ff3b30; }
  .kv-label { font-weight: 600; color: #1d1d1f; word-break: break-word; }
  .kv-value {
    color: #424245; font-family: ui-monospace, monospace; font-size: 11px;
    word-break: break-word; margin-top: 2px;
  }
  .kv-meta {
    margin-top: 3px; font-size: 10px; color: #8e8e93;
    display: flex; gap: 6px; flex-wrap: wrap;
  }
  .kv-meta .tag {
    background: #f5f5f7; padding: 1px 5px; border-radius: 3px;
  }
  .empty { color: #c7c7cc; font-style: italic; }
  .nav-arrows {
    display: flex; gap: 4px; margin-left: 8px;
  }
  .nav-arrows button {
    background: rgba(255,255,255,0.1); color: white; border: none;
    padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px;
  }
  .nav-arrows button:disabled { opacity: 0.3; cursor: not-allowed; }
</style>
</head>
<body>
<header>
  <h1>Golden KIE review</h1>
  <div class="nav-arrows">
    <button id="prev-page">← prev</button>
    <button id="next-page">next →</button>
  </div>
  <div class="toggles">
    <span class="toggle on" data-tog="sec">Sections</span>
    <span class="toggle on" data-tog="lbl">Labels</span>
    <span class="toggle on" data-tog="val">Values</span>
    <span class="toggle" data-tog="noise">Noise</span>
  </div>
  <div class="stats" id="stats"></div>
</header>

<aside class="sidebar" id="sidebar"></aside>
<main>
  <div id="page-container">
    <img id="page-img" src="" alt="">
    <svg class="overlay-svg" id="overlay"></svg>
  </div>
</main>
<aside class="kvpanel">
  <div class="tabs-bar">
    <button class="tab-btn active" data-tab="kv">KV pairs</button>
    <button class="tab-btn" data-tab="json">JSON tree</button>
  </div>
  <div id="kv-tab">
    <div class="filter-bar">
      <button class="on H" data-conf="HIGH">HIGH</button>
      <button class="on M" data-conf="MEDIUM">MED</button>
      <button class="on L" data-conf="LOW">LOW</button>
    </div>
    <div id="kv-list"></div>
  </div>
  <div id="json-tab" style="display:none">
    <div class="toolbar">
      <button id="jt-expand">expand all</button>
      <button id="jt-collapse">collapse all</button>
      <button id="jt-collapse-engines">hide engine evidence</button>
    </div>
    <div id="json-view"></div>
  </div>
</aside>

<script>
const STATE = {
  index: [],
  current: null,
  data: null,
  toggles: { sec: true, lbl: true, val: true, noise: false },
  confFilter: { HIGH: true, MEDIUM: true, LOW: true },
  scale: 1,
  pageWidth: 0, pageHeight: 0,
  flat: [],  // flat list of entries for prev/next navigation
};

async function loadIndex() {
  const r = await fetch('/api/index');
  STATE.index = await r.json();
  // Flatten for navigation
  STATE.flat = [];
  for (const grp of STATE.index) {
    for (const ent of grp.entries) STATE.flat.push(ent);
  }
  renderSidebar();
  if (STATE.flat.length) await load(STATE.flat[0]);
}

function renderSidebar() {
  const sb = document.getElementById('sidebar');
  sb.innerHTML = '';
  for (const grp of STATE.index) {
    const gh = document.createElement('div'); gh.className = 'pdf-group';
    const t = document.createElement('div'); t.className = 'pdf-title';
    const totalKv = grp.entries.reduce((a, e) => a + e.kv, 0);
    t.innerHTML = `<span title="${grp.name}">${grp.short}</span>
      <span class="badge">${grp.entries.length}p · ${totalKv}kv</span>`;
    gh.appendChild(t);
    for (const ent of grp.entries) {
      const it = document.createElement('div');
      it.className = 'page-item';
      it.dataset.golden = ent.golden_path;
      it.innerHTML = `<span>p${ent.page}</span>
        <span class="conf-row">
          ${ent.high?`<span class="dot H"></span>${ent.high}`:''}
          ${ent.medium?`<span class="dot M"></span>${ent.medium}`:''}
          ${ent.low?`<span class="dot L"></span>${ent.low}`:''}
        </span>`;
      it.onclick = () => load(ent);
      gh.appendChild(it);
    }
    sb.appendChild(gh);
  }
}

async function load(ent) {
  STATE.current = ent;
  // Mark active
  document.querySelectorAll('.page-item').forEach(el => {
    el.classList.toggle('active', el.dataset.golden === ent.golden_path);
  });
  // Fetch golden
  const url = '/api/golden?path=' + encodeURIComponent(ent.golden_path);
  const r = await fetch(url);
  STATE.data = await r.json();
  STATE.pageWidth = STATE.data.page_size_pt[0];
  STATE.pageHeight = STATE.data.page_size_pt[1];
  // Set image
  const img = document.getElementById('page-img');
  img.src = '/api/page?pdf=' + encodeURIComponent(ent.pdf_path) + '&page=' + ent.page;
  img.onload = () => {
    // Calculate scale based on rendered image size vs page pt size
    STATE.scale = img.naturalWidth / STATE.pageWidth;
    renderOverlays();
  };
  renderKVList();
  renderJSONTree();
  updateStats();
}

function updateStats() {
  const d = STATE.data;
  const k = d.kv_pairs || [];
  const h = k.filter(x => (x.confidence||'').toUpperCase() === 'HIGH').length;
  const m = k.filter(x => (x.confidence||'').toUpperCase() === 'MEDIUM').length;
  const l = k.filter(x => (x.confidence||'').toUpperCase() === 'LOW').length;
  document.getElementById('stats').innerHTML =
    `${STATE.current.pdf_name} · p${d.page} · ${d.sections?.length||0} sec · ${k.length} KV
     <span style="color:#34c759">●${h}</span>
     <span style="color:#ff9500">●${m}</span>
     <span style="color:#ff3b30">●${l}</span>`;
}

function renderOverlays() {
  const svg = document.getElementById('overlay');
  const img = document.getElementById('page-img');
  svg.setAttribute('width', img.naturalWidth);
  svg.setAttribute('height', img.naturalHeight);
  svg.style.width = img.naturalWidth + 'px';
  svg.style.height = img.naturalHeight + 'px';
  svg.innerHTML = '';
  const s = STATE.scale;
  const d = STATE.data;

  // Sections
  if (STATE.toggles.sec) {
    for (const sec of d.sections || []) {
      if (sec.container_bbox) {
        const r = sec.container_bbox;
        svg.innerHTML += `<rect class="ov-section"
          x="${r.x*s}" y="${r.y*s}" width="${r.w*s}" height="${r.h*s}"/>`;
      }
      if (sec.title_bbox) {
        const r = sec.title_bbox;
        svg.innerHTML += `<rect class="ov-section-title"
          x="${r.x*s}" y="${r.y*s}" width="${r.w*s}" height="${r.h*s}"
          ><title>${escapeHtml(sec.title || '')}</title></rect>`;
      }
    }
  }
  // KV pairs
  (d.kv_pairs || []).forEach((kv, idx) => {
    const conf = (kv.confidence || '').toUpperCase();
    if (!STATE.confFilter[conf]) return;
    if (STATE.toggles.lbl && kv.label_bbox) {
      const r = kv.label_bbox;
      svg.innerHTML += `<rect class="ov-label" data-kvidx="${idx}"
        x="${r.x*s}" y="${r.y*s}" width="${r.w*s}" height="${r.h*s}"
        ><title>${escapeHtml(kv.label || '')}</title></rect>`;
    }
    if (STATE.toggles.val) {
      for (const vb of kv.value_bboxes || []) {
        svg.innerHTML += `<rect class="ov-value" data-kvidx="${idx}"
          x="${vb.x*s}" y="${vb.y*s}" width="${vb.w*s}" height="${vb.h*s}"
          ><title>${escapeHtml(kv.value || '')}</title></rect>`;
      }
    }
  });
  // Noise
  if (STATE.toggles.noise) {
    for (const n of d.noise || []) {
      const r = n.bbox;
      if (!r) continue;
      svg.innerHTML += `<rect class="ov-noise"
        x="${r.x*s}" y="${r.y*s}" width="${r.w*s}" height="${r.h*s}"
        ><title>${escapeHtml(n.reason || '')}: ${escapeHtml((n.text||'').slice(0,80))}</title></rect>`;
    }
  }
}

function renderKVList() {
  const wrap = document.getElementById('kv-list');
  const d = STATE.data;
  const kvs = d.kv_pairs || [];
  // Group by section
  const bySec = {};
  for (const kv of kvs) {
    const conf = (kv.confidence || '').toUpperCase();
    if (!STATE.confFilter[conf]) continue;
    const s = kv.section || '(no section)';
    (bySec[s] = bySec[s] || []).push(kv);
  }
  let html = '';
  if (!kvs.length) html = '<div class="empty">No KV pairs in this golden</div>';
  for (const [sec, items] of Object.entries(bySec)) {
    html += `<div class="sec-block"><div class="sec-title">${escapeHtml(sec)}</div>`;
    for (const kv of items) {
      const conf = (kv.confidence || '').toUpperCase();
      const idx = kvs.indexOf(kv);
      html += `<div class="kv-row ${conf[0]||''}" data-kvidx="${idx}">
        <div class="kv-label">${escapeHtml(kv.label || '(no label)')}</div>
        <div class="kv-value">${kv.value ? escapeHtml(kv.value) : '<span class="empty">∅</span>'}</div>
        <div class="kv-meta">
          <span class="tag">${conf}</span>
          ${kv.rule ? `<span class="tag">${escapeHtml(kv.rule)}</span>` : ''}
          ${kv.band ? `<span class="tag">${escapeHtml(kv.band)}</span>` : ''}
        </div></div>`;
    }
    html += '</div>';
  }
  wrap.innerHTML = html;
  // Wire click → highlight
  wrap.querySelectorAll('.kv-row').forEach(el => {
    el.onclick = () => {
      const idx = el.dataset.kvidx;
      document.querySelectorAll('.kv-row').forEach(x => x.classList.remove('active'));
      el.classList.add('active');
      document.querySelectorAll('#overlay rect').forEach(r => r.classList.remove('active'));
      document.querySelectorAll(`#overlay rect[data-kvidx="${idx}"]`).forEach(r => {
        r.classList.add('active');
        // Scroll into view
        const bbox = r.getBoundingClientRect();
        if (bbox.top < 80 || bbox.bottom > window.innerHeight - 20) {
          r.scrollIntoView({behavior:'smooth', block:'center'});
        }
      });
    };
  });
}

function escapeHtml(s) {
  return (s||'').toString()
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

// ---------- JSON tree renderer ----------
function findBboxIn(node) {
  // Recursively find a bbox-like object inside a node. Used to make rows clickable.
  if (!node || typeof node !== 'object') return null;
  // Direct bbox fields
  for (const k of ['cell_bbox','bbox','label_bbox','container_bbox','title_bbox']) {
    if (node[k] && typeof node[k] === 'object' && 'x' in node[k] && 'y' in node[k]) {
      return node[k];
    }
  }
  return null;
}

function engineAgreementBadge(node) {
  if (!node || typeof node !== 'object') return '';
  const ev = node.evidence;
  if (ev && typeof ev === 'object' && 'engine_agreement' in ev) {
    const n = ev.engine_agreement;
    const cls = n >= 3 ? '' : n >= 1 ? 'partial' : 'none';
    return `<span class="jt-engine-tag ${cls}">${n}/3</span>`;
  }
  return '';
}

function nodeSummary(node) {
  if (Array.isArray(node)) return `[${node.length} items]`;
  if (node && typeof node === 'object') {
    const keys = Object.keys(node);
    // For 'structure' nodes with title, show title
    if (node.title) return `"${node.title}" {${keys.length}}`;
    if (node.type) return `${node.type} {${keys.length}}`;
    if (node.label) return `"${node.label}" {${keys.length}}`;
    return `{${keys.length} keys}`;
  }
  return JSON.stringify(node);
}

function renderJSONNode(key, val, path) {
  // Returns HTML for one node
  const isObj = val && typeof val === 'object';
  const isArr = Array.isArray(val);
  const bbox = isObj ? findBboxIn(val) : null;
  const hasBbox = bbox !== null;
  const badge = isObj ? engineAgreementBadge(val) : '';
  const keyHtml = key !== null ? `<span class="jt-key">${escapeHtml(String(key))}</span>: ` : '';
  const dataBbox = hasBbox ? `data-bbox='${JSON.stringify(bbox)}'` : '';

  if (!isObj) {
    let vHtml = '';
    if (val === null) vHtml = '<span class="jt-null">null</span>';
    else if (typeof val === 'string') vHtml = `<span class="jt-string">"${escapeHtml(val)}"</span>`;
    else if (typeof val === 'number') vHtml = `<span class="jt-number">${val}</span>`;
    else if (typeof val === 'boolean') vHtml = `<span class="jt-bool">${val}</span>`;
    else vHtml = escapeHtml(String(val));
    return `<div class="jt-row" data-path="${escapeHtml(path)}">${keyHtml}${vHtml}</div>`;
  }

  const summary = nodeSummary(val);
  const children = isArr
    ? val.map((v, i) => renderJSONNode(i, v, path + '/' + i)).join('')
    : Object.entries(val).map(([k, v]) => renderJSONNode(k, v, path + '/' + k)).join('');

  // Auto-collapse engine-evidence objects, atoms, bbox internals to reduce noise
  const collapseByDefault = ['evidence','pdfplumber','liteparse','docling','rect',
                              'char_indices','pos_map','noise','atoms_summary','diagnostics'].includes(key);
  const collapsedCls = collapseByDefault ? 'jt-collapsed' : '';
  return `<div class="jt-node ${collapsedCls}" data-path="${escapeHtml(path)}">
    <div class="jt-row ${hasBbox?'has-bbox':''}" ${dataBbox} data-path="${escapeHtml(path)}">
      <span class="jt-toggle">▾</span>${keyHtml}<span class="jt-summary">${escapeHtml(summary)}</span>${badge}
    </div>
    <div class="jt-children">${children}</div>
  </div>`;
}

function renderJSONTree() {
  const wrap = document.getElementById('json-view');
  if (!STATE.data) { wrap.innerHTML = ''; return; }
  // Show the `structure` field if present, otherwise the whole doc
  const root = STATE.data.structure ? {structure: STATE.data.structure, _meta: STATE.data._meta} : STATE.data;
  wrap.innerHTML = renderJSONNode(null, root, '');
  // Wire toggle clicks
  wrap.querySelectorAll('.jt-toggle').forEach(t => {
    t.onclick = (e) => {
      e.stopPropagation();
      const node = t.closest('.jt-node');
      node.classList.toggle('jt-collapsed');
      t.textContent = node.classList.contains('jt-collapsed') ? '▸' : '▾';
    };
  });
  // Wire bbox-row clicks (highlight on page)
  wrap.querySelectorAll('.jt-row.has-bbox').forEach(row => {
    row.onclick = (e) => {
      if (e.target.classList.contains('jt-toggle')) return;
      const bb = JSON.parse(row.dataset.bbox);
      // Clear other actives
      document.querySelectorAll('.jt-row.active').forEach(r => r.classList.remove('active'));
      row.classList.add('active');
      // Draw a temporary highlight rect on the overlay
      const svg = document.getElementById('overlay');
      // Remove any temp highlight
      document.querySelectorAll('#overlay .jt-temp-hl').forEach(el => el.remove());
      const s = STATE.scale;
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('class', 'jt-temp-hl');
      rect.setAttribute('x', bb.x * s); rect.setAttribute('y', bb.y * s);
      rect.setAttribute('width', bb.w * s); rect.setAttribute('height', bb.h * s);
      rect.setAttribute('fill', 'rgba(255,59,48,0.30)');
      rect.setAttribute('stroke', 'rgba(255,59,48,0.95)');
      rect.setAttribute('stroke-width', '2.5');
      svg.appendChild(rect);
      // Scroll page to it if off-screen
      const main = document.querySelector('main');
      const targetY = bb.y * s;
      if (targetY < main.scrollTop + 60 || targetY > main.scrollTop + main.clientHeight - 60) {
        main.scrollTo({top: Math.max(0, targetY - 100), behavior: 'smooth'});
      }
    };
  });
}

// Tab switcher
document.querySelectorAll('.tab-btn').forEach(b => {
  b.onclick = () => {
    document.querySelectorAll('.tab-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    const tab = b.dataset.tab;
    document.getElementById('kv-tab').style.display = tab === 'kv' ? '' : 'none';
    document.getElementById('json-tab').style.display = tab === 'json' ? '' : 'none';
  };
});
// Expand/collapse all
document.getElementById('jt-expand').onclick = () => {
  document.querySelectorAll('#json-view .jt-node').forEach(n => {
    n.classList.remove('jt-collapsed');
    const t = n.querySelector(':scope > .jt-row > .jt-toggle');
    if (t) t.textContent = '▾';
  });
};
document.getElementById('jt-collapse').onclick = () => {
  document.querySelectorAll('#json-view .jt-node').forEach(n => {
    n.classList.add('jt-collapsed');
    const t = n.querySelector(':scope > .jt-row > .jt-toggle');
    if (t) t.textContent = '▸';
  });
};
document.getElementById('jt-collapse-engines').onclick = () => {
  // Collapse only evidence sub-trees
  document.querySelectorAll('#json-view .jt-row').forEach(r => {
    const text = (r.textContent || '').trim();
    if (['evidence','pdfplumber','liteparse','docling','rect'].some(k => text.startsWith(k + ':'))) {
      const n = r.closest('.jt-node');
      if (n) {
        n.classList.add('jt-collapsed');
        const t = n.querySelector(':scope > .jt-row > .jt-toggle');
        if (t) t.textContent = '▸';
      }
    }
  });
};

// Toggle wiring
document.querySelectorAll('header .toggle').forEach(el => {
  el.onclick = () => {
    const k = el.dataset.tog;
    STATE.toggles[k] = !STATE.toggles[k];
    el.classList.toggle('on', STATE.toggles[k]);
    renderOverlays();
  };
});
document.querySelectorAll('.filter-bar button').forEach(el => {
  el.onclick = () => {
    const c = el.dataset.conf;
    STATE.confFilter[c] = !STATE.confFilter[c];
    el.classList.toggle('on', STATE.confFilter[c]);
    renderOverlays(); renderKVList();
  };
});

// Prev/Next nav
function navTo(delta) {
  if (!STATE.current) return;
  const i = STATE.flat.findIndex(e => e.golden_path === STATE.current.golden_path);
  const j = i + delta;
  if (j < 0 || j >= STATE.flat.length) return;
  load(STATE.flat[j]);
}
document.getElementById('prev-page').onclick = () => navTo(-1);
document.getElementById('next-page').onclick = () => navTo(1);
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowLeft' || e.key === '[') navTo(-1);
  if (e.key === 'ArrowRight' || e.key === ']') navTo(1);
});

loadIndex();
</script>
</body>
</html>
"""


# --- HTTP handler ------------------------------------------------------------

INDEX_CACHE: list[dict] = []  # populated on startup


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a, **kw):  # silence stderr noise
        pass

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(path.query)
        try:
            if path.path == "/" or path.path == "/index.html":
                self._send(200, HTML.encode("utf-8"))
            elif path.path == "/api/index":
                # Group by PDF
                groups: dict[str, list[dict]] = {}
                for e in INDEX_CACHE:
                    groups.setdefault(e["pdf_name"], []).append(e)
                out = []
                for name in sorted(groups):
                    ents = sorted(groups[name], key=lambda e: e["page"])
                    short = (name
                             .replace("CONTRATO ", "C·")
                             .replace("_DOC2_CONTRATO", "")
                             .replace(".pdf", ""))[:36]
                    out.append({"name": name, "short": short, "entries": ents})
                self._send(200, json.dumps(out, ensure_ascii=False).encode("utf-8"),
                           "application/json")
            elif path.path == "/api/golden":
                gp = Path(qs.get("path", [""])[0])
                if not gp.exists() or not gp.is_file():
                    self._send(404, b"not found"); return
                d = _enrich_golden(gp)
                self._send(200, json.dumps(d, ensure_ascii=False).encode("utf-8"),
                           "application/json")
            elif path.path == "/api/page":
                pdf = Path(qs.get("pdf", [""])[0])
                page_num = int(qs.get("page", ["1"])[0])
                if not pdf.exists():
                    self._send(404, b"pdf not found"); return
                png = _render_page_png(pdf, page_num)
                self._send(200, png, "image/png")
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:
            self._send(500, f"error: {e}".encode("utf-8"), "text/plain")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8772)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)

    global INDEX_CACHE
    INDEX_CACHE = _index_goldens()
    print(f"[goldens] indexed {len(INDEX_CACHE)} golden pages")
    pdfs = sorted({e["pdf_name"] for e in INDEX_CACHE})
    print(f"[goldens] across {len(pdfs)} PDFs")

    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), Handler) as httpd:
        url = f"http://127.0.0.1:{args.port}"
        print(f"[goldens] serving at {url}")
        if not args.no_browser:
            threading.Timer(0.3, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[goldens] shutdown")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
