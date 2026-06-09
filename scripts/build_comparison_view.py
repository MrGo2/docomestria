"""Build a side-by-side HTML comparison view for one ParseBench sample PDF.

Left pane: the PDF (embedded). Right pane: tabbed view of ground truth +
each engine's raw output rendered as a sortable table with bbox / font /
label so we can eyeball what each engine sees and how it lines up with GT.

Usage:
    python scripts/build_comparison_view.py table__0000027_page1
    python scripts/build_comparison_view.py text__text_misc__012-headline-certificate-fluidpower-group-uk-limited

Writes to data/parsebench/views/<stem>.html and opens it in the default
browser.
"""

from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path

import fitz  # PyMuPDF — reliable PDF -> PNG, no poppler dependency

ROOT = Path(__file__).resolve().parent.parent / "data" / "parsebench"
PDFS_DIR = ROOT / "pdfs"
GT_DIR = ROOT / "ground_truth"
OUT_DIR = ROOT / "outputs"
VIEWS_DIR = ROOT / "views"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"failed to parse: {exc}"}


def fmt_bbox(b: dict | None) -> str:
    if not b:
        return ""
    return f"x={b['x']:.1f} y={b['y']:.1f} w={b['w']:.1f} h={b['h']:.1f}"


def render_liteparse(payload: dict | None) -> str:
    if not payload:
        return "<p class='empty'>No output</p>"
    items = payload.get("items", [])
    rows = [
        f"<tr>"
        f"<td>{i}</td>"
        f"<td class='text'>{html.escape(str(it.get('text', '')))}</td>"
        f"<td class='mono'>{fmt_bbox(it.get('bbox'))}</td>"
        f"<td class='mono'>{html.escape(str(it.get('font_name') or ''))}</td>"
        f"<td>{it.get('font_size') or ''}</td>"
        f"<td>{it.get('page')}</td>"
        f"</tr>"
        for i, it in enumerate(items)
    ]
    return (
        f"<p class='meta'>{len(items)} items · {payload.get('elapsed_seconds', '?')}s</p>"
        "<table class='engine-table'>"
        "<thead><tr><th>#</th><th>Text</th><th>BBox</th><th>Font</th><th>Size</th><th>Page</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_pdfplumber(payload: dict | None) -> str:
    if not payload:
        return "<p class='empty'>No output</p>"
    items = payload.get("items", [])
    rows = []
    for i, it in enumerate(items):
        cells = it.get("cells")
        cells_summary = ""
        if cells:
            n_rows = len(cells)
            n_cols = max((len(r) for r in cells), default=0)
            cells_summary = f"{n_rows}×{n_cols} cells"
        rows.append(
            f"<tr>"
            f"<td>{i}</td>"
            f"<td class='mono'>{html.escape(it.get('rect_id') or '')}</td>"
            f"<td>{html.escape(it.get('rect_type', ''))}</td>"
            f"<td class='mono'>{fmt_bbox(it.get('bbox'))}</td>"
            f"<td>{'✓' if it.get('is_checkbox') else ''}</td>"
            f"<td>{'✓' if it.get('is_filled') else ''}</td>"
            f"<td>{cells_summary}</td>"
            f"<td>{it.get('page')}</td>"
            f"</tr>"
        )
    return (
        f"<p class='meta'>{len(items)} rects · {payload.get('elapsed_seconds', '?')}s</p>"
        "<table class='engine-table'>"
        "<thead><tr><th>#</th><th>ID</th><th>Type</th><th>BBox</th>"
        "<th>Checkbox</th><th>Filled</th><th>Cells</th><th>Page</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_docling(payload: dict | None) -> str:
    if not payload:
        return "<p class='empty'>No output</p>"
    items = payload.get("items", [])
    rows = []
    for i, it in enumerate(items):
        text_preview = (it.get("text") or "").strip().replace("\n", " ⏎ ")
        if len(text_preview) > 120:
            text_preview = text_preview[:117] + "…"
        cells = it.get("cells")
        cells_summary = ""
        if cells:
            n_rows = len(cells)
            n_cols = max((len(r) for r in cells), default=0)
            cells_summary = f"{n_rows}×{n_cols} cells"
        rows.append(
            f"<tr>"
            f"<td>{i}</td>"
            f"<td><span class='badge'>{html.escape(it.get('label', ''))}</span></td>"
            f"<td>{it.get('heading_level') or ''}</td>"
            f"<td class='text'>{html.escape(text_preview)}</td>"
            f"<td class='mono'>{fmt_bbox(it.get('bbox'))}</td>"
            f"<td>{html.escape(it.get('content_layer', ''))}</td>"
            f"<td>{cells_summary}</td>"
            f"<td>{it.get('page')}</td>"
            f"</tr>"
        )
    return (
        f"<p class='meta'>{len(items)} blocks · {payload.get('elapsed_seconds', '?')}s</p>"
        "<table class='engine-table'>"
        "<thead><tr><th>#</th><th>Label</th><th>Lvl</th><th>Text</th>"
        "<th>BBox</th><th>Layer</th><th>Cells</th><th>Page</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_ground_truth(stem: str) -> str:
    gt = GT_DIR / f"{stem}.jsonl"
    if not gt.exists():
        return "<p class='empty'>No ground truth file</p>"

    by_type: dict[str, list[dict]] = {}
    for line in gt.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        by_type.setdefault(rec.get("type", "?"), []).append(rec)

    parts = [f"<p class='meta'>{sum(len(v) for v in by_type.values())} GT records "
             f"across {len(by_type)} types</p>"]

    for tname, recs in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        parts.append(f"<h3>type: <code>{html.escape(tname)}</code> "
                     f"<span class='meta'>({len(recs)} records)</span></h3>")
        # For expected_markdown we render the HTML directly (tables).
        if tname == "expected_markdown":
            for rec in recs:
                md = rec.get("expected_markdown") or ""
                parts.append("<div class='gt-html'>" + md + "</div>")
            continue
        # Otherwise show first 5 raw records.
        for rec in recs[:5]:
            parts.append("<details><summary>"
                         f"<code>{html.escape(rec.get('id', ''))}</code>"
                         f" · tags={rec.get('tags')}</summary>"
                         f"<pre>{html.escape(json.dumps(rec, ensure_ascii=False, indent=2))}</pre>"
                         "</details>")
        if len(recs) > 5:
            parts.append(f"<p class='meta'>… {len(recs) - 5} more</p>")
    return "\n".join(parts)


CSS = """
:root { --bg:#0f1419; --fg:#e2e8f0; --muted:#64748b; --accent:#38bdf8; --border:#1e293b; --panel:#0b1018; }
* { box-sizing:border-box; }
body { margin:0; font-family: -apple-system, system-ui, sans-serif; background:var(--bg); color:var(--fg); font-size:13px; }
.toolbar { padding:8px 16px; background:var(--panel); border-bottom:1px solid var(--border); display:flex; gap:16px; align-items:center; }
.toolbar h1 { margin:0; font-size:14px; font-weight:600; }
.toolbar .sub { color:var(--muted); font-size:12px; }
.layout { display:grid; grid-template-columns: 1fr 1fr; height: calc(100vh - 41px); }
.pane { overflow:auto; border-right:1px solid var(--border); }
.pane:last-child { border-right:none; }
.tabs { display:flex; gap:0; background:var(--panel); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:10; }
.tab { padding:8px 14px; cursor:pointer; color:var(--muted); border-bottom:2px solid transparent; user-select:none; }
.tab.active { color:var(--accent); border-bottom-color:var(--accent); background:#0f172a; }
.tab-body { padding: 12px 16px; display:none; }
.tab-body.active { display:block; }
table.engine-table { width:100%; border-collapse:collapse; font-size:12px; }
table.engine-table th, table.engine-table td { padding:4px 8px; border-bottom:1px solid var(--border); text-align:left; vertical-align:top; }
table.engine-table th { background:var(--panel); position:sticky; top:33px; color:var(--muted); font-weight:500; }
table.engine-table tr:hover { background:#0a1424; }
.mono { font-family: ui-monospace, "SF Mono", monospace; color:#94a3b8; font-size:11px; }
.text { max-width:280px; word-wrap:break-word; }
.badge { display:inline-block; padding:1px 6px; background:#1e293b; border-radius:3px; color:var(--accent); font-size:11px; }
.meta { color:var(--muted); font-size:12px; margin:4px 0 12px; }
.empty { color:var(--muted); font-style:italic; padding:20px; }
.gt-html { background:#fff; color:#000; padding:12px; border-radius:4px; margin-bottom:12px; max-height:60vh; overflow:auto; }
.gt-html table { border-collapse:collapse; }
.gt-html th, .gt-html td { border:1px solid #ccc; padding:4px 8px; }
.gt-html th { background:#f1f5f9; }
details { margin:6px 0; padding:6px 10px; background:var(--panel); border-radius:4px; }
summary { cursor:pointer; color:var(--accent); }
pre { font-size:11px; line-height:1.4; color:#cbd5e1; overflow:auto; max-height:300px; margin:8px 0 0; }
h3 { font-size:13px; margin:16px 0 6px; color:#cbd5e1; }
h3 code { color:var(--accent); background:none; padding:0; }
.pdf-pages { padding: 12px; background:#1a1f2e; }
.pdf-pages img { width:100%; height:auto; display:block; margin-bottom:12px; box-shadow:0 2px 8px rgba(0,0,0,0.4); background:#fff; }
.pdf-pages .page-label { color:var(--muted); font-size:11px; margin-bottom:4px; }
"""

JS = """
function showTab(group, name) {
  document.querySelectorAll('.tab[data-group="'+group+'"]').forEach(t => t.classList.toggle('active', t.dataset.name===name));
  document.querySelectorAll('.tab-body[data-group="'+group+'"]').forEach(b => b.classList.toggle('active', b.dataset.name===name));
}
"""


def render_pdf_to_pngs(pdf_path: Path, out_dir: Path, stem: str, zoom: float = 2.0) -> list[str]:
    """Render every page of `pdf_path` to PNG. Returns list of relative paths.

    Files are written next to the HTML view (same dir) so the <img> src can use
    a relative path that works without a web server.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc, start=1):
            png = out_dir / f"{stem}_p{i}.png"
            if not png.exists():
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                pix.save(str(png))
            paths.append(png.name)
    return paths


def build_html(stem: str) -> str:
    pdf = PDFS_DIR / f"{stem}.pdf"
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")

    page_pngs = render_pdf_to_pngs(pdf, VIEWS_DIR, stem)
    pdf_pages_html = "".join(
        f'<div class="page-label">page {i}</div>'
        f'<img src="{html.escape(p)}" alt="page {i}">'
        for i, p in enumerate(page_pngs, start=1)
    )

    gt_html = render_ground_truth(stem)
    lp = render_liteparse(load_json(OUT_DIR / "liteparse" / f"{stem}.json"))
    pp = render_pdfplumber(load_json(OUT_DIR / "pdfplumber" / f"{stem}.json"))
    dl = render_docling(load_json(OUT_DIR / "docling" / f"{stem}.json"))

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>{html.escape(stem)} — docomestria comparison</title>
<style>{CSS}</style>
</head><body>
<div class="toolbar">
  <h1>{html.escape(stem)}</h1>
  <span class="sub">{pdf.stat().st_size // 1024} KB · {pdf.name} · {len(page_pngs)} page(s)</span>
</div>
<div class="layout">
  <div class="pane">
    <div class="pdf-pages">{pdf_pages_html}</div>
  </div>
  <div class="pane">
    <div class="tabs">
      <div class="tab active" data-group="r" data-name="gt"
           onclick="showTab('r','gt')">Ground Truth</div>
      <div class="tab" data-group="r" data-name="lp"
           onclick="showTab('r','lp')">LiteParse</div>
      <div class="tab" data-group="r" data-name="pp"
           onclick="showTab('r','pp')">pdfplumber</div>
      <div class="tab" data-group="r" data-name="dl"
           onclick="showTab('r','dl')">Docling</div>
    </div>
    <div class="tab-body active" data-group="r" data-name="gt">{gt_html}</div>
    <div class="tab-body" data-group="r" data-name="lp">{lp}</div>
    <div class="tab-body" data-group="r" data-name="pp">{pp}</div>
    <div class="tab-body" data-group="r" data-name="dl">{dl}</div>
  </div>
</div>
<script>{JS}</script>
</body></html>
"""


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/build_comparison_view.py <pdf-stem>")
        print("\nAvailable stems:")
        for p in sorted(PDFS_DIR.glob("*.pdf")):
            print(f"  {p.stem}")
        sys.exit(1)

    stem = sys.argv[1].removesuffix(".pdf")
    VIEWS_DIR.mkdir(parents=True, exist_ok=True)
    target = VIEWS_DIR / f"{stem}.html"
    target.write_text(build_html(stem), encoding="utf-8")
    print(f"Wrote {target}")

    # Open in default browser.
    subprocess.run(["open", str(target)], check=False)


if __name__ == "__main__":
    main()
