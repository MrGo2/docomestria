"""Launch a local HTTP viewer for one PDF + its structural extraction.

Builds a single self-contained HTML page that shows the PDF on the left
(rendered via PDF.js) and the extracted pairs grouped by section /
subsection on the right, with bbox overlays you can hover to highlight.

Usage:
    PYTHONPATH=src python3 scripts/view_extraction.py <pdf-path> [--port 8765]
"""

from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

from docomestria.engines import (
    extract_docling_blocks,
    extract_lite_items,
    extract_visual_rects,
)
from docomestria.structural import structural_extract_from_engines

ROOT = Path(__file__).resolve().parent.parent


def build_html(pdf_url: str, payload: dict, pdf_name: str) -> str:
    """Return the viewer HTML, embedding the extraction payload inline."""
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Docomestria — {pdf_name}</title>
<script src="https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.min.mjs" type="module"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: -apple-system, system-ui, sans-serif;
    background: #f6f6f7; color: #1d1d1f;
    display: grid; grid-template-columns: 1fr 480px; height: 100vh;
  }}
  header {{
    grid-column: 1 / -1;
    padding: 8px 16px; background: #fff; border-bottom: 1px solid #e1e1e3;
    display: flex; align-items: center; gap: 12px;
    font-size: 13px;
  }}
  header h1 {{ font-size: 14px; margin: 0; font-weight: 600; }}
  header .meta {{ color: #6e6e73; display: flex; gap: 12px; }}
  header .badge {{
    background: #1d1d1f; color: #fff; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 600;
  }}
  body {{ grid-template-rows: auto 1fr; }}
  #pdf-pane {{ overflow: auto; padding: 16px; }}
  .page-container {{ position: relative; margin: 0 auto 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .page-container canvas {{ display: block; }}
  .overlay {{
    position: absolute; border: 1.5px solid transparent; border-radius: 2px;
    pointer-events: none; transition: background 0.15s, border 0.15s;
  }}
  .overlay.label {{ border-color: rgba(0, 100, 220, 0.0); }}
  .overlay.value {{ border-color: rgba(0, 180, 90, 0.0); }}
  .overlay.active.label {{ border-color: rgba(0, 100, 220, 0.9); background: rgba(0, 100, 220, 0.18); }}
  .overlay.active.value {{ border-color: rgba(0, 180, 90, 0.9); background: rgba(0, 180, 90, 0.18); }}
  #pairs-pane {{
    overflow: auto; padding: 12px; background: #fff; border-left: 1px solid #e1e1e3;
    font-size: 13px;
  }}
  .section {{ margin-bottom: 16px; }}
  .section-title {{
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; color: #6e6e73; padding: 4px 6px; margin-bottom: 4px;
    border-bottom: 1px solid #e1e1e3;
  }}
  .subsection-title {{
    font-size: 11px; font-weight: 500; color: #424245;
    padding: 4px 12px; margin-top: 4px; background: #f6f6f7;
  }}
  .pair {{
    padding: 6px 10px; border-radius: 4px; margin: 2px 0;
    cursor: pointer; display: grid; grid-template-columns: 1fr auto; gap: 4px;
    transition: background 0.1s;
  }}
  .pair:hover {{ background: #f0f0f2; }}
  .pair.active {{ background: #e8f0fe; }}
  .pair-text {{ display: flex; flex-direction: column; min-width: 0; }}
  .pair-label {{ font-weight: 500; color: #1d1d1f; word-wrap: break-word; }}
  .pair-value {{ color: #424245; font-family: ui-monospace, monospace; font-size: 12px; word-wrap: break-word; }}
  .pair-meta {{ display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }}
  .conf {{ font-size: 10px; padding: 1px 6px; border-radius: 3px; font-weight: 600; }}
  .conf.HIGH {{ background: #d4edda; color: #155724; }}
  .conf.MEDIUM {{ background: #fff3cd; color: #856404; }}
  .conf.LOW {{ background: #f8d7da; color: #721c24; }}
  .rule {{ font-size: 9px; color: #8e8e93; }}
  .typed {{
    font-size: 10px; color: #007aff; font-family: ui-monospace, monospace;
    padding: 1px 4px; background: rgba(0, 122, 255, 0.08); border-radius: 3px;
  }}
  #filter {{
    width: 100%; padding: 6px 10px; border: 1px solid #d2d2d7; border-radius: 6px;
    font-size: 13px; margin-bottom: 8px;
  }}
  .empty-msg {{ color: #8e8e93; padding: 12px; text-align: center; font-size: 12px; }}
</style>
</head>
<body>
<header>
  <h1>{pdf_name}</h1>
  <div class="meta">
    <span><span class="badge">{payload['doc_type'].upper()}</span> conf {payload['doc_type_confidence']}</span>
    <span>{payload['pair_count']} pares</span>
    <span>{payload['page_count']} págs</span>
    <span>schema v{payload['schema_version']}</span>
  </div>
</header>
<div id="pdf-pane"></div>
<div id="pairs-pane">
  <input id="filter" placeholder="Filtrar pares…" type="text">
  <div id="pairs-list"></div>
</div>
<script type="module">
import * as pdfjsLib from "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.min.mjs";
pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.worker.min.mjs";

const payload = {json.dumps(payload, ensure_ascii=False)};
const pdfUrl = {json.dumps(pdf_url)};
const SCALE = 1.5;

const pageOverlays = new Map();      // page number → array of overlay <div>s with metadata
const pageDims = new Map();          // page number → {{w, h}} in PDF pt
const overlayByPairId = new Map();   // pair id → array of overlays (label + value)
const pairCards = [];                // {{ el, pair, id }}

function renderPdf() {{
  pdfjsLib.getDocument(pdfUrl).promise.then(async (pdf) => {{
    const pane = document.getElementById("pdf-pane");
    for (let i = 1; i <= pdf.numPages; i++) {{
      const page = await pdf.getPage(i);
      const viewport = page.getViewport({{ scale: SCALE }});
      const container = document.createElement("div");
      container.className = "page-container";
      container.style.width = viewport.width + "px";
      container.style.height = viewport.height + "px";
      container.dataset.page = i;
      pane.appendChild(container);

      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      container.appendChild(canvas);
      await page.render({{ canvasContext: canvas.getContext("2d"), viewport }}).promise;

      pageDims.set(i, {{ w: viewport.width, h: viewport.height }});
      pageOverlays.set(i, container);
      drawOverlays(i);
    }}
  }});
}}

function drawOverlays(pageNum) {{
  const container = pageOverlays.get(pageNum);
  if (!container) return;
  const dims = pageDims.get(pageNum);
  // Walk every pair on this page; the engine reports bbox in PDF points top-left origin.
  for (const [pairId, pair] of allPairs) {{
    if (pair.page !== pageNum) continue;
    const bb = pair.bbox;
    if (!bb) continue;
    const labelEl = document.createElement("div");
    labelEl.className = "overlay label";
    labelEl.style.left = (bb.x * SCALE) + "px";
    labelEl.style.top = (bb.y * SCALE) + "px";
    labelEl.style.width = (bb.w * SCALE) + "px";
    labelEl.style.height = (bb.h * SCALE) + "px";
    container.appendChild(labelEl);
    if (!overlayByPairId.has(pairId)) overlayByPairId.set(pairId, []);
    overlayByPairId.get(pairId).push(labelEl);
  }}
}}

const allPairs = new Map();  // pair id → pair dict
const pairsListEl = document.getElementById("pairs-list");

function renderPairs() {{
  let nextId = 0;
  for (const section of payload.sections) {{
    const secEl = document.createElement("div");
    secEl.className = "section";
    if (section.title) {{
      const t = document.createElement("div");
      t.className = "section-title";
      t.textContent = section.title;
      secEl.appendChild(t);
    }}
    for (const sub of section.subsections) {{
      if (sub.title) {{
        const st = document.createElement("div");
        st.className = "subsection-title";
        st.textContent = sub.title;
        secEl.appendChild(st);
      }}
      for (const pair of sub.pairs) {{
        const id = nextId++;
        allPairs.set(id, pair);
        const pairEl = document.createElement("div");
        pairEl.className = "pair";
        pairEl.dataset.pairId = id;
        const text = document.createElement("div");
        text.className = "pair-text";
        const lbl = document.createElement("div");
        lbl.className = "pair-label";
        lbl.textContent = pair.label || "(sin etiqueta)";
        const val = document.createElement("div");
        val.className = "pair-value";
        val.textContent = pair.value || "—";
        text.appendChild(lbl);
        text.appendChild(val);
        if (pair.typed) {{
          const typed = document.createElement("span");
          typed.className = "typed";
          typed.textContent = pair.typed.kind + ":" + JSON.stringify(pair.typed.value);
          text.appendChild(typed);
        }}
        const meta = document.createElement("div");
        meta.className = "pair-meta";
        const conf = document.createElement("span");
        conf.className = "conf " + pair.confidence;
        conf.textContent = pair.confidence + " " + pair.score.toFixed(2);
        const rule = document.createElement("span");
        rule.className = "rule";
        rule.textContent = pair.rule + (pair.column_index ? " · col " + pair.column_index : "");
        meta.appendChild(conf);
        meta.appendChild(rule);
        pairEl.appendChild(text);
        pairEl.appendChild(meta);
        pairEl.addEventListener("mouseenter", () => activatePair(id));
        pairEl.addEventListener("mouseleave", () => deactivatePair(id));
        pairEl.addEventListener("click", () => {{
          deactivateAll();
          activatePair(id);
          const overlays = overlayByPairId.get(id) || [];
          if (overlays.length) overlays[0].scrollIntoView({{ block: "center", behavior: "smooth" }});
        }});
        secEl.appendChild(pairEl);
        pairCards.push({{ el: pairEl, pair, id }});
      }}
    }}
    pairsListEl.appendChild(secEl);
  }}
}}

function activatePair(id) {{
  for (const card of pairCards) if (card.id === id) card.el.classList.add("active");
  const overlays = overlayByPairId.get(id) || [];
  for (const o of overlays) o.classList.add("active");
}}
function deactivatePair(id) {{
  for (const card of pairCards) if (card.id === id) card.el.classList.remove("active");
  const overlays = overlayByPairId.get(id) || [];
  for (const o of overlays) o.classList.remove("active");
}}
function deactivateAll() {{
  for (const card of pairCards) card.el.classList.remove("active");
  for (const arr of overlayByPairId.values()) for (const o of arr) o.classList.remove("active");
}}

document.getElementById("filter").addEventListener("input", (e) => {{
  const q = e.target.value.toLowerCase();
  for (const card of pairCards) {{
    const hit = !q || (card.pair.label + " " + card.pair.value).toLowerCase().includes(q);
    card.el.style.display = hit ? "" : "none";
  }}
}});

renderPairs();
renderPdf();
</script>
</body>
</html>
"""


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Quiet handler — log less noise."""

    def log_message(self, format, *args):  # noqa: A002
        return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="Path to the PDF file to extract + view.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return 2

    print(f"Running engines on {pdf_path.name} …")
    docling = extract_docling_blocks(str(pdf_path))
    lite = extract_lite_items(str(pdf_path))
    plumber = extract_visual_rects(str(pdf_path))
    print(f"  docling: {len(docling)} blocks")
    print(f"  liteparse: {len(lite)} items")
    print(f"  pdfplumber: {len(plumber)} rects")

    print("Running structural extraction …")
    res = structural_extract_from_engines(docling, lite, plumber)
    payload = res.to_json()
    print(
        f"  doc_type={payload['doc_type']}@{payload['doc_type_confidence']}  "
        f"{payload['pair_count']} pairs  {payload['page_count']} pages"
    )

    # Serve from a temp dir holding (a) the HTML and (b) the PDF.
    serve_root = ROOT / ".viewer"
    serve_root.mkdir(exist_ok=True)
    pdf_link = serve_root / pdf_path.name
    if pdf_link.exists() or pdf_link.is_symlink():
        pdf_link.unlink()
    pdf_link.symlink_to(pdf_path)
    html = build_html(f"/{pdf_path.name}", payload, pdf_path.name)
    html_path = serve_root / "index.html"
    html_path.write_text(html, encoding="utf-8")

    import os
    os.chdir(serve_root)

    with socketserver.TCPServer(("127.0.0.1", args.port), _Handler) as srv:
        url = f"http://127.0.0.1:{args.port}/"
        print(f"\nServing at {url}  (Ctrl-C to stop)")
        if not args.no_browser:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
