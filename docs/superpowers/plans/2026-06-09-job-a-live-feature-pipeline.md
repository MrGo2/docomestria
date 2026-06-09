# Job A — Live-Feature Pipeline & Retrain — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute the role-classifier's features for production PDFs directly from the three engines (LiteParse + Docling + pdfplumber), label those live items from the golden annotations, and retrain/validate the classifier on exactly what production computes.

**Architecture:** A new `live_features.py` iterates LiteParse items (the production base unit) and builds the full 50-column `FIELDS` row per item, reusing pure helpers from `text_features.py`, `golden/training_table.py`, and `fusion.py`. A new `live_labels.py` transfers golden roles onto those rows by normalized-text + bbox-overlap; unmatched items become `noise`. Two glue scripts (mirroring the golden-world `build_training_table.py` / `train_role_classifier.py`) build the CSV and run the acceptance gate (`evaluate_oof` GroupKFold-by-pdf). The golden builder is **not modified** — we import its pure helpers.

**Tech Stack:** Python 3.12, pdfplumber, Docling, LiteParse v2, scikit-learn (`HistGradientBoostingClassifier`), pandas, pytest.

**Spec:** `docs/superpowers/specs/2026-06-09-live-engine-fusion-substrate-design.md` (v3.1). Do not re-litigate the design.

---

## Ground rules for the implementer

- **Run tests with the project binary, not rtk:** `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest -q`. `pyproject.toml` sets `pythonpath = ["src"]` for **pytest only** — so tests `import docomestria` without `PYTHONPATH`. **Standalone scripts get no such help**: every script under `scripts/` must insert `ROOT/src` on `sys.path` before importing `docomestria` (copy the preamble from `scripts/build_training_table.py:12-15`). The script tasks below include that preamble — do not drop it.
- **Line numbers in this plan are hints, not contracts.** They drift. Each implementation task's **Step 1 is "Read the cited function and confirm its current signature"** before writing code. Trust the *names and behavior* documented here; verify the *line*.
- **Two bbox shapes coexist.** Engine dataclasses (`LiteItem`, `DoclingBlock`, `VisualRect`) carry a `BBox` dataclass (`.x/.y/.w/.h`, top-left origin, y grows down). The golden pure helpers (`_overlap_frac`, `_norm`) and label transfer operate on **dict** bboxes (`{"x","y","w","h"}`). Convert with the `_bbox_to_dict` helper built in Task 2. The `fusion.py` helpers (`_best_docling_block`, `_smallest_containing_rect`, `_find_cell`) take the **dataclass** `LiteItem`/`DoclingBlock`/`VisualRect` directly — pass them unconverted.
- **Do NOT modify** `golden/training_table.py`, `golden/cell_linker.py`, or `fusion.py`. Import their pure helpers.
- **Do NOT `git stash --include-untracked`** (regression baseline at `.regression/baseline.json`). The pre-existing modified `.planning/extraction/drafts/*.json` are prior golden work — leave them untouched.
- **Output goes to a *live* namespace** so it never clobbers the golden `role_table.csv`:
  - `.planning/extraction/training/live_role_table.csv`
  - `.planning/extraction/training/live_role_model.pkl`
  - `.planning/extraction/training/live_role_model_report.{md,json}`, `live_role_model_confusion.csv`, `live_coverage.csv`

---

## Decisions to confirm at plan review (Codex gate + Carlos)

The spec's **recommended defaults stand** unless Carlos overrides. Surface these to Codex; if any are flagged as deliverable-changing, escalate to Carlos before execution.

1. **Acceptance bar:** macro-F1 ≥ **0.85** and every role F1 > 0.5 (spec default; alt 0.86).
2. **Coverage floor:** ≥ **90%** of annotated items overall, ≥ **70%** per annotated role (spec default).
3. **Helper reuse:** **import** the pure helpers (`content_flags`, `case_class`, `_onehot_case`, `signal_features` sub-helpers, `_overlap_frac`, `_norm`, `is_bold`, `walk_structure`); do **not** fork (spec recommendation).
4. **NEW — live `compound_span` definition.** Golden sets `compound_span=1` when one LiteParse span produced both a key and a value (colon-split). The live base unit is the raw LiteItem, so the live analog is: **`compound_span = 1` if the item text has a real interior colon with non-trivial text on both sides** (`^\s*\S.*:\s*\S`), i.e. one span carrying `label: value`. This is a small feature-definition call. Default as stated; flag for confirmation.
5. **NEW — live `colon_present`** is a **real** geometric colon test (fixing the golden quirk where it was `1` even with no colon): true if the item text contains `:` OR a detached `:` word sits on the item's text line at/just past its right edge (tolerance `0.5 × line-height`). Default as stated.
6. **Zero-fill** the two 0.0-importance, live-uncomputable columns `docling_column_header` / `docling_row_header` with constant `0` (spec; keeps the `FIELDS` schema intact so `evaluate_oof`'s fixed `FEATURE_COLS` indexing never `KeyError`s).
7. **NEW — words, not chars.** The spec mentions "chars/words" (§Scope 1). After mapping the consumers, **no `FIELDS` column needs sub-word char geometry**: `colon_present` is satisfied by a standalone `:` *word* (pdfplumber splits a detached colon into its own word), and `pdfplumber_present` is word-overlap. Emitting per-char bboxes would be dead code (YAGNI). **Decision: emit words only.** If review insists on char-level geometry for a future feature, add `extract_chars` then — not now. Flag for confirmation.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `src/docomestria/models.py` | MODIFY | Add `WordItem` dataclass (pdfplumber word + bbox). |
| `src/docomestria/engines/pdfplumber.py` | MODIFY | Add `extract_words(pdf)` and `extract_page_sizes(pdf)`; add `_words_from_page` pure helper. |
| `src/docomestria/engines/__init__.py` | MODIFY | Export `extract_words`, `extract_page_sizes`. |
| `src/docomestria/live_features.py` | CREATE | `build_live_rows(...)` → one full 50-col `FIELDS` dict per LiteItem (role left blank). |
| `src/docomestria/live_labels.py` | CREATE | `golden_annotated_items(golden)` + `transfer_labels(rows, golden_items)` → labeled rows + coverage report. |
| `scripts/build_live_feature_table.py` | CREATE | Enumerate golden corpus → run engines live per PDF → build rows → transfer labels → write `live_role_table.csv` + `live_coverage.csv`. |
| `scripts/train_live_role_classifier.py` | CREATE | Read CSV → enforce gate (coverage floor + macro-F1 + per-role F1) → reports → `fit_final_model` → `live_role_model.pkl`. |
| `tests/test_pdfplumber_words.py` | CREATE | `_words_from_page` pure conversion. |
| `tests/test_live_features.py` | CREATE | Per-item feature rows from synthetic engine outputs (in-cell, over-signature, missing-engine, colon present/absent). |
| `tests/test_live_labels.py` | CREATE | Label transfer (match, no-match→noise, coverage). |
| `tests/test_live_gate.py` | CREATE | Integration: live table → `evaluate_oof` ≥ 0.85 + coverage floor. Marked `@pytest.mark.integration`. |

**Reused (imported, never modified):**
- `docomestria.text_features`: `content_flags(text) -> dict`, `case_class(text) -> str`.
- `docomestria.golden.training_table`: `FIELDS`, `_onehot_case(value) -> dict`, `_overlap_frac(a, b) -> float`, `walk_structure(structure, spans, path="") -> list[Item]`, `write_csv(rows, path)`.
- `docomestria.golden.engine_data`: `_norm(s) -> str`.
- `docomestria.structural.classify`: `is_bold(font_name) -> bool`.
- `docomestria.fusion`: `_best_docling_block(item, blocks)`, `_smallest_containing_rect(item, rects)`, `_find_cell(item, tables)`.
- `docomestria.training.role_classifier`: `load_dataset(path)`, `evaluate_oof(df, n_splits=5, random_state=0) -> dict`, `feature_importances(df, ...) -> list[tuple[str,float]]`, `fit_final_model(df, random_state=0) -> dict`, `render_report_md(result, importances) -> str`.

---

## Task 1: `WordItem` dataclass + pdfplumber word/page-size emitter

**Files:**
- Modify: `src/docomestria/models.py` (add `WordItem` near `LiteItem`, ~line 62)
- Modify: `src/docomestria/engines/pdfplumber.py` (add `_words_from_page`, `extract_words`, `extract_page_sizes`)
- Modify: `src/docomestria/engines/__init__.py`
- Test: `tests/test_pdfplumber_words.py`

- [ ] **Step 1: Read the anchors.** Open `models.py` and confirm the `BBox` (4 fields `x,y,w,h`) and `LiteItem` dataclasses. Open `engines/pdfplumber.py` and confirm `extract_visual_rects` opens via `pdfplumber.open(str(pdf_path))`, iterates `pdf.pages` (1-based page index), and builds `BBox(x=x0, y=top, w=x1-x0, h=bottom-top)` (top-left origin). Open `engines/__init__.py` and confirm the three existing exports.

- [ ] **Step 2: Add the `WordItem` dataclass.** In `models.py`, after `LiteItem`:

```python
@dataclass(frozen=True)
class WordItem:
    """One whitespace-delimited word extracted by pdfplumber (for colon tests
    and per-item pdfplumber presence). Top-left origin, y grows downward."""
    text: str
    bbox: BBox
    page: int
```

- [ ] **Step 3: Write the failing test for the pure conversion helper.** `tests/test_pdfplumber_words.py`:

```python
from docomestria.engines.pdfplumber import _words_from_page
from docomestria.models import WordItem


def test_words_from_page_converts_pdfplumber_dicts_to_top_left_bbox():
    raw = [
        {"text": "Nombre:", "x0": 10.0, "x1": 55.0, "top": 100.0, "bottom": 112.0},
        {"text": "Adrian", "x0": 60.0, "x1": 95.0, "top": 100.0, "bottom": 112.0},
    ]
    words = _words_from_page(raw, page=1)
    assert [type(w) for w in words] == [WordItem, WordItem]
    w0 = words[0]
    assert w0.text == "Nombre:"
    assert w0.page == 1
    # bbox is (x0, top, x1-x0, bottom-top) — top-left origin
    assert (w0.bbox.x, w0.bbox.y, w0.bbox.w, w0.bbox.h) == (10.0, 100.0, 45.0, 12.0)


def test_words_from_page_skips_blank_text():
    raw = [{"text": "   ", "x0": 0.0, "x1": 1.0, "top": 0.0, "bottom": 1.0}]
    assert _words_from_page(raw, page=1) == []
```

- [ ] **Step 4: Run it, verify it fails.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_pdfplumber_words.py -q`. Expected: FAIL with `ImportError`/`cannot import name '_words_from_page'`.

- [ ] **Step 5: Implement the helper + emitters** in `engines/pdfplumber.py`. Add the `WordItem` import to the existing models import line, then:

```python
def _words_from_page(raw_words: list[dict], page: int) -> list[WordItem]:
    """Convert pdfplumber `page.extract_words()` dicts to WordItems (top-left origin)."""
    out: list[WordItem] = []
    for w in raw_words:
        text = (w.get("text") or "").strip()
        if not text:
            continue
        x0 = float(w["x0"]); x1 = float(w["x1"])
        top = float(w["top"]); bottom = float(w["bottom"])
        out.append(WordItem(text=text, bbox=BBox(x=x0, y=top, w=x1 - x0, h=bottom - top), page=page))
    return out


def extract_words(pdf_path: str | Path) -> list[WordItem]:
    """Extract whitespace-delimited words with bboxes from every page."""
    out: list[WordItem] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            out.extend(_words_from_page(page.extract_words() or [], page_no))
    return out


def extract_page_sizes(pdf_path: str | Path) -> dict[int, tuple[float, float]]:
    """Map 1-based page number → (width_pt, height_pt)."""
    sizes: dict[int, tuple[float, float]] = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            sizes[page_no] = (float(getattr(page, "width", 0.0)), float(getattr(page, "height", 0.0)))
    return sizes
```

- [ ] **Step 6: Export the new functions** in `engines/__init__.py`:

```python
from .pdfplumber import extract_page_sizes, extract_visual_rects, extract_words
```

and add `"extract_page_sizes"`, `"extract_words"` to `__all__`.

- [ ] **Step 7: Run tests, verify pass.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_pdfplumber_words.py -q`. Expected: 2 passed.

- [ ] **Step 8: Commit.**

```bash
git add src/docomestria/models.py src/docomestria/engines/pdfplumber.py src/docomestria/engines/__init__.py tests/test_pdfplumber_words.py
git commit -m "feat: add pdfplumber word + page-size emitters for live features"
```

---

## Task 2: `live_features.py` — per-item base features (content, typography, case, geometry)

**Files:**
- Create: `src/docomestria/live_features.py`
- Test: `tests/test_live_features.py`

- [ ] **Step 1: Read the anchors.** Confirm `text_features.content_flags(text) -> dict` (returns `digit_ratio, has_currency, has_date, has_percent, has_iban, has_nif, starts_paren, ends_colon, n_numeric_tokens, len_chars`) and `text_features.case_class(text) -> str` (`"UPPER"/"lower"/"Title"/"mixed"/"none"`). Confirm `golden.training_table._onehot_case(value) -> dict` (keys `case_upper/case_lower/case_title/case_mixed`) and that `FIELDS` is the 50-col list. Confirm `structural.classify.is_bold(font_name) -> bool`.

- [ ] **Step 2: Write the failing test** for the base-row builder. `tests/test_live_features.py`:

```python
from docomestria.models import BBox, LiteItem
from docomestria.live_features import _base_row, _bbox_to_dict


def test_base_row_geometry_normalised_by_page_size():
    it = LiteItem(text="NOMBRE:", bbox=BBox(x=60.0, y=120.0, w=90.0, h=12.0),
                  font_name="Helvetica-Bold", font_size=10.0, page=1)
    row = _base_row(it, page_size_pt=(600.0, 800.0))
    # geometry normalised to unit square
    assert row["x"] == 60.0 / 600.0
    assert row["y"] == 120.0 / 800.0
    assert row["w"] == 90.0 / 600.0
    assert row["h"] == 12.0 / 800.0
    # typography
    assert row["is_bold"] == 1
    assert row["font_size"] == 10.0
    # case one-hot (UPPER)
    assert row["case_upper"] == 1 and row["case_lower"] == 0
    # content (from content_flags)
    assert row["ends_colon"] is True or row["ends_colon"] == 1
    # provenance carried
    assert row["text"] == "NOMBRE:"
    assert row["page"] == 1
    assert row["liteparse_present"] == 1


def test_bbox_to_dict_roundtrip():
    assert _bbox_to_dict(BBox(x=1.0, y=2.0, w=3.0, h=4.0)) == {"x": 1.0, "y": 2.0, "w": 3.0, "h": 4.0}
```

- [ ] **Step 3: Run it, verify it fails.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_live_features.py -q`. Expected: FAIL with `ModuleNotFoundError: docomestria.live_features`.

- [ ] **Step 4: Create `live_features.py` with the base-row builder.**

```python
"""Build live role-classifier feature rows (the FIELDS schema) for a production
PDF page, directly from the three engines. Mirrors golden/training_table.py's
row semantics but computes everything from LIVE engine outputs (no golden signal
dict) and fixes the colon quirk. The golden builder is not modified."""

from __future__ import annotations

import re
import statistics

from .models import BBox, DoclingBlock, LiteItem, VisualRect, WordItem
from .text_features import case_class, content_flags
from .structural.classify import is_bold
from .golden.training_table import FIELDS, _onehot_case


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

    # provenance
    row["pdf"] = ""           # filled by build_live_rows
    row["page"] = it.page
    row["text"] = text
    row["node_path"] = ""     # live items have no golden node path
    row["source_node_type"] = "live_item"
    row["in_table"] = 0       # set in engine-match step
    row["table_id"] = ""
    row["row_idx"] = ""
    row["col_id"] = ""
    # label left blank for label transfer
    row["role"] = ""

    # geometry (normalised 0-1)
    row["x"] = it.bbox.x / pw
    row["y"] = it.bbox.y / ph
    row["w"] = it.bbox.w / pw
    row["h"] = it.bbox.h / ph

    # typography
    row["font_size"] = it.font_size if it.font_size is not None else ""
    row["font_size_ratio"] = ""      # set in neighbour/median step
    row["is_bold"] = 1 if is_bold(it.font_name) else 0
    row.update(_onehot_case(case_class(text)))

    # content (from the item's own text)
    row.update(content_flags(text))

    # liteparse is always present (it IS a liteparse item)
    row["liteparse_present"] = 1

    return row
```

- [ ] **Step 5: Run tests, verify pass.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_live_features.py -q`. Expected: 2 passed.

- [ ] **Step 6: Commit.**

```bash
git add src/docomestria/live_features.py tests/test_live_features.py
git commit -m "feat: live_features base-row builder (content/typography/geometry)"
```

---

## Task 3: `live_features.py` — engine-match features (docling, rect, cell, presence, colon, compound)

**Files:**
- Modify: `src/docomestria/live_features.py`
- Test: `tests/test_live_features.py` (add cases)

- [ ] **Step 1: Read the anchors.** Confirm in `fusion.py`: `_best_docling_block(item, blocks) -> (DoclingBlock|None, str, float)`, `_smallest_containing_rect(item, rects) -> VisualRect|None`, `_find_cell(item, tables) -> (table_id, row, col, BBox)|None`. Confirm the **sort-by-area precondition** (`blocks.sort(key=lambda b: b.bbox.area)`, ascending) — the live builder must sort docling blocks by area before calling `_best_docling_block`. Confirm `DoclingBlock` carries `.content_layer` and `VisualRect` carries `.rect_type` (values include `"signature_field"`).

- [ ] **Step 2: Write the failing tests** (append to `tests/test_live_features.py`):

```python
from docomestria.models import DoclingBlock, VisualRect, WordItem
from docomestria.live_features import _engine_features


def _item(text="Nombre", x=60.0, y=120.0, w=40.0, h=12.0, page=1):
    return LiteItem(text=text, bbox=BBox(x=x, y=y, w=w, h=h),
                    font_name="Helvetica", font_size=10.0, page=page)


def test_engine_features_docling_match_pulls_content_layer_from_raw_block():
    it = _item()
    blocks = [DoclingBlock(bbox=BBox(x=0.0, y=0.0, w=600.0, h=800.0), label="text",
                           heading_level=None, content_layer="body", page=1)]
    feats = _engine_features(it, blocks, rects=[], words=[])
    assert feats["docling_present"] == 1
    assert feats["docling_content_layer"] == "body"
    assert feats["docling_label"] == "text"


def test_engine_features_missing_engines_degrade_to_zero():
    feats = _engine_features(_item(), blocks=[], rects=[], words=[])
    assert feats["docling_present"] == 0
    assert feats["pdfplumber_present"] == 0
    assert feats["inside_rect"] == 0
    assert feats["rect_is_signature_field"] == 0
    # engine_agreement = liteparse(1) + pdfplumber(0) + docling(0)
    assert feats["engine_agreement"] == 1


def test_engine_features_over_signature_rect():
    it = _item(y=700.0)
    sig = VisualRect(bbox=BBox(x=0.0, y=690.0, w=600.0, h=30.0), is_checkbox=False,
                     is_filled=False, page=1, rect_type="signature_field")
    feats = _engine_features(it, blocks=[], rects=[sig], words=[])
    assert feats["rect_is_signature_field"] == 1
    assert feats["inside_rect"] == 1


def test_engine_features_real_colon_from_detached_word():
    it = _item(text="Nombre", x=60.0, y=120.0, w=40.0, h=12.0)
    colon = WordItem(text=":", bbox=BBox(x=102.0, y=120.0, w=4.0, h=12.0), page=1)
    feats = _engine_features(it, blocks=[], rects=[], words=[colon])
    assert feats["colon_present"] == 1


def test_engine_features_no_colon_when_absent():
    feats = _engine_features(_item(text="Nombre"), blocks=[], rects=[],
                             words=[WordItem(text="Adrian", bbox=BBox(x=102.0, y=120.0, w=40.0, h=12.0), page=1)])
    assert feats["colon_present"] == 0


def test_engine_features_compound_span_interior_colon():
    feats = _engine_features(_item(text="Nombre: Adrian"), blocks=[], rects=[], words=[])
    assert feats["compound_span"] == 1
    feats2 = _engine_features(_item(text="Total:"), blocks=[], rects=[], words=[])
    assert feats2["compound_span"] == 0
```

- [ ] **Step 3: Run, verify fail.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_live_features.py -q`. Expected: FAIL (`cannot import name '_engine_features'`).

- [ ] **Step 4: Implement the engine-match helpers** in `live_features.py`. Add imports and:

```python
from .fusion import _best_docling_block, _find_cell, _smallest_containing_rect

_COMPOUND_RE = re.compile(r"^\s*\S.*:\s*\S")


def _has_real_colon(it: LiteItem, words: list[WordItem]) -> int:
    """Real colon test (fixes golden quirk): colon inside the item text, or a
    detached ':' word sitting tightly on the item's right edge and baseline.
    Tolerances are HALF the line-height on both axes (a colon hugs the key, so
    a loose box would create false positives — see Codex finding #9)."""
    if ":" in it.text:
        return 1
    ib = it.bbox
    iy_c = ib.y + ib.h / 2.0
    v_tol = 0.5 * ib.h          # tight vertical band (same baseline)
    h_tol = 0.5 * ib.h          # colon must hug the right edge, not be anywhere left
    right = ib.x + ib.w
    for w in words:
        if ":" not in w.text:
            continue
        wb = w.bbox
        if abs((wb.y + wb.h / 2.0) - iy_c) > v_tol:   # not the same line
            continue
        if right - h_tol <= wb.x <= right + h_tol:    # colon at the right edge
            return 1
    return 0


def _engine_features(it: LiteItem, blocks: list[DoclingBlock],
                     rects: list[VisualRect], words: list[WordItem]) -> dict:
    """Engine-match feature subset for one LiteItem."""
    feats: dict = {}

    # --- Docling block match (sort-by-area precondition for _best_docling_block) ---
    sorted_blocks = sorted(blocks, key=lambda b: b.bbox.area)
    block, _method, _score = _best_docling_block(it, sorted_blocks)
    if block is not None:
        feats["docling_present"] = 1
        feats["docling_label"] = block.label or ""
        feats["docling_heading_level"] = block.heading_level if block.heading_level is not None else ""
        feats["docling_content_layer"] = block.content_layer or ""   # from RAW block, not FusedItem
    else:
        feats["docling_present"] = 0
        feats["docling_label"] = ""
        feats["docling_heading_level"] = ""
        feats["docling_content_layer"] = ""

    # --- pdfplumber presence: any word overlapping the item bbox ---
    feats["pdfplumber_present"] = 1 if _any_word_overlaps(it, words) else 0

    # --- enclosing rect / table cell ---
    # Codex #5: _smallest_containing_rect / _find_cell return the FIRST containing
    # rect — fuse_from_engines sorts rects/tables by area first so "smallest" holds.
    # Reproduce that precondition here.
    sorted_rects = sorted(rects, key=lambda r: r.bbox.area)
    rect = _smallest_containing_rect(it, sorted_rects)
    feats["inside_rect"] = 1 if rect is not None else 0
    sorted_tables = sorted((r for r in rects if r.rect_type == "table"), key=lambda r: r.bbox.area)
    cell = _find_cell(it, sorted_tables)
    if cell is not None:
        table_id, row_idx, col_idx, _cell_bbox = cell
        feats["in_table"] = 1
        feats["table_id"] = str(table_id)
        feats["row_idx"] = str(row_idx)
        feats["col_id"] = str(col_idx)
    else:
        feats["in_table"] = 0
        feats["table_id"] = ""
        feats["row_idx"] = ""
        feats["col_id"] = ""

    # --- signature rect: item center inside any signature_field rect ---
    feats["rect_is_signature_field"] = 1 if _center_in_signature_rect(it, rects) else 0

    # --- live-uncomputable, 0.0-importance: zero-fill (keeps FIELDS intact) ---
    feats["docling_column_header"] = 0
    feats["docling_row_header"] = 0

    # --- colon (real test) + compound span + engine agreement ---
    feats["colon_present"] = _has_real_colon(it, words)
    feats["compound_span"] = 1 if _COMPOUND_RE.match(it.text) else 0
    feats["engine_agreement"] = 1 + feats["pdfplumber_present"] + feats["docling_present"]

    return feats


def _any_word_overlaps(it: LiteItem, words: list[WordItem]) -> bool:
    a = _bbox_to_dict(it.bbox)
    for w in words:
        if w.page != it.page:
            continue
        b = _bbox_to_dict(w.bbox)
        ix = max(0.0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
        iy = max(0.0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
        if ix * iy > 0:
            return True
    return False


def _center_in_signature_rect(it: LiteItem, rects: list[VisualRect]) -> bool:
    cx = it.bbox.x + it.bbox.w / 2.0
    cy = it.bbox.y + it.bbox.h / 2.0
    for r in rects:
        if r.rect_type != "signature_field":
            continue
        b = r.bbox
        if b.x <= cx <= b.x + b.w and b.y <= cy <= b.y + b.h:
            return True
    return False
```

> **Note for implementer:** `_best_docling_block`, `_smallest_containing_rect`, and `_find_cell` take the **dataclass** `LiteItem` and operate on `.bbox.area`/containment internally. If reading the source reveals `_find_cell` expects the full rect list (not pre-filtered to tables) or a different tuple arity, adapt the unpacking to match the *actual* signature — the names/behavior are the contract, the exact shape is what you confirmed in Step 1.

- [ ] **Step 5: Run tests, verify pass.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_live_features.py -q`. Expected: all passed.

- [ ] **Step 6: Commit.**

```bash
git add src/docomestria/live_features.py tests/test_live_features.py
git commit -m "feat: live_features engine-match features (docling/rect/cell/colon/compound)"
```

---

## Task 4: `live_features.py` — neighbour features + median font + `build_live_rows` entry point

**Files:**
- Modify: `src/docomestria/live_features.py`
- Test: `tests/test_live_features.py` (add cases)

- [ ] **Step 1: Read the anchor.** Re-read `golden/training_table.py` lines ~500–560 (the neighbour block inside `build_page_rows`): median font over numeric `font_size`; items sorted by `(y, x)`; `gap_above`/`gap_below` from prev/next item edges; `font_ratio_vs_below`; `bold_above_nonbold_below`; `is_centered` (`abs(center_x - 0.5) <= 0.06`). Mirror that logic on the live rows (which are already normalised 0-1).

- [ ] **Step 2: Write the failing test** (append):

```python
from docomestria.live_features import build_live_rows


def test_build_live_rows_full_schema_and_neighbour_order():
    from docomestria.golden.training_table import FIELDS
    items = [
        LiteItem(text="SECCION", bbox=BBox(x=60.0, y=100.0, w=120.0, h=14.0),
                 font_name="Helvetica-Bold", font_size=12.0, page=1),
        LiteItem(text="cuerpo normal", bbox=BBox(x=60.0, y=130.0, w=200.0, h=10.0),
                 font_name="Helvetica", font_size=10.0, page=1),
    ]
    rows = build_live_rows("DOC.pdf", page=1, lite_items=items, docling_blocks=[],
                           visual_rects=[], words=[], page_size_pt=(600.0, 800.0))
    assert len(rows) == 2
    # every row has exactly the FIELDS keys
    for r in rows:
        assert set(r.keys()) == set(FIELDS)
        assert r["pdf"] == "DOC.pdf"
    top, below = rows[0], rows[1]   # sorted by (y, x)
    # bold-above (12pt bold) over non-bold-below (10pt) → flag set
    assert top["bold_above_nonbold_below"] == 1
    # font ratio above/below = 12/10
    assert abs(top["font_ratio_vs_below"] - 1.2) < 1e-9
    # font_size_ratio is filled (median of {12,10})
    assert top["font_size_ratio"] != ""
    # gap_below positive (next item is lower on page → larger y)
    assert top["gap_below"] > 0


def test_build_live_rows_is_centered():
    it = LiteItem(text="TITULO", bbox=BBox(x=270.0, y=50.0, w=60.0, h=14.0),
                  font_name="Helvetica-Bold", font_size=12.0, page=1)
    rows = build_live_rows("D.pdf", 1, [it], [], [], [], (600.0, 800.0))
    # center_x = (270+30)/600 = 0.5 → centered
    assert rows[0]["is_centered"] == 1
```

- [ ] **Step 3: Run, verify fail.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_live_features.py -q`. Expected: FAIL (`cannot import name 'build_live_rows'`).

- [ ] **Step 4: Implement `build_live_rows`** in `live_features.py`:

```python
_CENTER_TOL = 0.06


def build_live_rows(pdf: str, page: int, lite_items: list[LiteItem],
                    docling_blocks: list[DoclingBlock], visual_rects: list[VisualRect],
                    words: list[WordItem], page_size_pt: tuple[float, float]) -> list[dict]:
    """One full FIELDS row per LiteItem for a single page (role left blank)."""
    page_items = [it for it in lite_items if it.page == page]
    page_blocks = [b for b in docling_blocks if b.page == page]
    page_rects = [r for r in visual_rects if r.page == page]
    page_words = [w for w in words if w.page == page]

    rows: list[dict] = []
    for it in page_items:
        row = _base_row(it, page_size_pt)
        row["pdf"] = pdf
        row.update(_engine_features(it, page_blocks, page_rects, page_words))
        rows.append((it, row))

    # median font over numeric font_size → font_size_ratio
    fonts = [it.font_size for it, _ in rows if isinstance(it.font_size, (int, float)) and it.font_size]
    median_font = statistics.median(fonts) if fonts else 0.0
    for it, row in rows:
        fs = it.font_size
        row["font_size_ratio"] = (fs / median_font) if (median_font and isinstance(fs, (int, float))) else ""
        cx = row["x"] + row["w"] / 2.0
        row["is_centered"] = 1 if abs(cx - 0.5) <= _CENTER_TOL else 0

    # neighbour features over (y, x)-sorted rows (rows are normalised 0-1)
    ordered = sorted(rows, key=lambda pr: (pr[1]["y"], pr[1]["x"]))
    for idx, (_it, row) in enumerate(ordered):
        prv = ordered[idx - 1][1] if idx > 0 else None
        nxt = ordered[idx + 1][1] if idx + 1 < len(ordered) else None
        row["gap_above"] = max(0.0, row["y"] - (prv["y"] + prv["h"])) if prv else 0.0
        row["gap_below"] = max(0.0, nxt["y"] - (row["y"] + row["h"])) if nxt else 0.0
        if nxt and isinstance(row["font_size"], (int, float)) and isinstance(nxt["font_size"], (int, float)) and nxt["font_size"]:
            row["font_ratio_vs_below"] = row["font_size"] / nxt["font_size"]
        else:
            row["font_ratio_vs_below"] = ""
        cur_bold = row["is_bold"] in (1, True)
        nxt_bold = nxt is not None and nxt["is_bold"] in (1, True)
        row["bold_above_nonbold_below"] = 1 if (cur_bold and nxt is not None and not nxt_bold) else 0

    return [row for _it, row in rows]
```

- [ ] **Step 5: Run tests, verify pass.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_live_features.py -q`. Expected: all passed.

- [ ] **Step 6: Commit.**

```bash
git add src/docomestria/live_features.py tests/test_live_features.py
git commit -m "feat: live_features neighbour features + build_live_rows entry point"
```

---

## Task 5: `live_labels.py` — golden annotated-item extraction + label transfer + coverage

**Files:**
- Create: `src/docomestria/live_labels.py`
- Test: `tests/test_live_labels.py`

- [ ] **Step 1: Read the anchors.** Confirm `golden.training_table.walk_structure(structure, spans, path="") -> list[Item]` and the `Item` dataclass fields (`text, role, bbox (dict|None), node_path, source_node_type, ...`). Confirm `_overlap_frac(a, b) -> float` (intersection / min-area, dict bboxes) and `golden.engine_data._norm(s) -> str` (NFKD + strip accents + lowercase + euro-fold + whitespace collapse). Confirm the annotated (non-noise) role strings: `key, value, section_header, table_header, signature, prose`.

- [ ] **Step 2: Write the failing tests.** `tests/test_live_labels.py`:

```python
from docomestria.live_labels import transfer_labels, ANNOTATED_ROLES


def _row(text, x, y, w=40.0, h=12.0, page=1):
    # minimal row with the keys transfer_labels reads
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "page": page, "role": ""}


def _gitem(text, x, y, role, w=40.0, h=12.0, page=1):
    return {"text": text, "bbox": {"x": x, "y": y, "w": w, "h": h}, "role": role, "page": page}


def test_transfer_labels_matches_by_norm_text_and_overlap():
    # row geometry is normalised 0-1; golden items here use the same scale for the test
    rows = [_row("Nombre", 0.1, 0.1)]
    golden = [_gitem("nombre", 0.1, 0.1, "key")]   # _norm folds case → match
    labeled, cov = transfer_labels(rows, golden)
    assert labeled[0]["role"] == "key"
    assert cov["matched"] == 1
    assert cov["per_role"]["key"]["matched"] == 1


def test_transfer_labels_unmatched_row_becomes_noise():
    rows = [_row("zzz off page", 0.9, 0.9)]
    golden = [_gitem("nombre", 0.1, 0.1, "key")]
    labeled, cov = transfer_labels(rows, golden)
    assert labeled[0]["role"] == "noise"


def test_transfer_labels_coverage_floor_per_role():
    rows = [_row("Nombre", 0.1, 0.1), _row("Apellido", 0.1, 0.2)]
    golden = [_gitem("nombre", 0.1, 0.1, "key"), _gitem("apellido", 0.1, 0.2, "key")]
    _labeled, cov = transfer_labels(rows, golden)
    assert cov["overall_pct"] == 100.0
    assert cov["per_role"]["key"]["pct"] == 100.0


def test_transfer_labels_bbox_less_table_header_matches_by_text_only():
    # golden table_header from walk_structure has bbox=None — must still match a
    # live row by normalized text alone (Codex #4).
    rows = [_row("Importe", 0.4, 0.3)]
    golden = [{"text": "importe", "bbox": None, "role": "table_header", "page": 1}]
    labeled, cov = transfer_labels(rows, golden)
    assert labeled[0]["role"] == "table_header"
    assert cov["per_role"]["table_header"]["matched"] == 1


def test_golden_annotated_items_skips_non_string_text(monkeypatch):
    # Corpus has annotated `value` items whose text is a dict like {"ref": "nota_1"}
    # (footnote refs); _norm would crash on them. golden_annotated_items must drop
    # them (Codex regression). Monkeypatch walk_structure so the test is independent
    # of the golden structure schema — golden_annotated_items only reads .role/.text/.bbox.
    import types
    import docomestria.live_labels as ll

    def _it(text, role, bbox):
        return types.SimpleNamespace(text=text, role=role, bbox=bbox)

    monkeypatch.setattr(ll, "walk_structure", lambda structure, spans: [
        _it("Nombre", "key", {"x": 10.0, "y": 10.0, "w": 40.0, "h": 12.0}),
        _it({"ref": "nota_1"}, "value", {"x": 60.0, "y": 10.0, "w": 40.0, "h": 12.0}),
    ])
    items = ll.golden_annotated_items(
        {"page_size_pt": [600.0, 800.0], "page": 1, "structure": [], "atoms": {"spans": []}})
    assert [g["text"] for g in items] == ["Nombre"]   # dict-text value dropped, no crash


def test_annotated_roles_excludes_noise():
    assert "noise" not in ANNOTATED_ROLES
    assert {"key", "value", "section_header", "table_header", "signature", "prose"} <= ANNOTATED_ROLES
```

- [ ] **Step 3: Run, verify fail.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_live_labels.py -q`. Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 4: Create `live_labels.py`.**

```python
"""Transfer golden annotation roles onto live feature rows by normalized-text +
bbox-overlap (the PRIMARY disambiguator; span_id is not unique). Unmatched live
rows become `noise`, reproducing the golden noise_items policy. Also extracts the
annotated items from a golden page JSON via walk_structure."""

from __future__ import annotations

from .golden.engine_data import _norm
from .golden.training_table import _overlap_frac, walk_structure

ANNOTATED_ROLES = {"key", "value", "section_header", "table_header", "signature", "prose"}
_MIN_OVERLAP = 0.30


def golden_annotated_items(golden: dict) -> list[dict]:
    """Annotated (non-noise) items for one golden page, geometry normalised 0-1.
    Returns dicts: {text, role, bbox:{x,y,w,h}|None, page}.
    Codex #4: `table_header` items come out of walk_structure with bbox=None — we
    KEEP them (bbox=None) so they count in the coverage denominator; transfer
    falls back to text-only matching for bbox-less items."""
    pw, ph = golden.get("page_size_pt", [1.0, 1.0])
    pw = pw or 1.0
    ph = ph or 1.0
    spans = (golden.get("atoms", {}) or {}).get("spans", [])  # walk_structure may need spans; see Step 1
    out: list[dict] = []
    for it in walk_structure(golden.get("structure", []), spans):
        if it.role not in ANNOTATED_ROLES:
            continue
        # Codex: the corpus has annotated `value` items whose text is a dict like
        # {"ref": "nota_1"} (footnote refs). _norm expects str — the golden builder
        # drops non-str text before matching (training_table.py ~461). Do the same.
        if not isinstance(it.text, str):
            continue
        bb = it.bbox
        norm_bb = (
            {"x": bb["x"] / pw, "y": bb["y"] / ph, "w": bb["w"] / pw, "h": bb["h"] / ph}
            if bb else None
        )
        out.append({"text": it.text, "role": it.role, "bbox": norm_bb, "page": golden.get("page")})
    return out


def transfer_labels(rows: list[dict], golden_items: list[dict]) -> tuple[list[dict], dict]:
    """Assign each row a golden role or `noise`. Match policy:
    - golden item WITH bbox → normalized-text equal AND overlap >= 0.30 (primary).
    - golden item WITHOUT bbox (e.g. table_header) → normalized-text equal only.
    Returns (labeled_rows, coverage_report). Input rows are not mutated (copies)."""
    used: set[int] = set()
    labeled: list[dict] = []
    matched_per_role: dict[str, int] = {}

    for row in rows:
        new = dict(row)
        r_norm = _norm(row.get("text", ""))
        r_bb = {"x": row["x"], "y": row["y"], "w": row["w"], "h": row["h"]}
        best_idx, best_ov = -1, -1.0
        for gi, g in enumerate(golden_items):
            if gi in used or _norm(g["text"]) != r_norm:
                continue
            if g["bbox"] is None:
                ov = 0.0                       # text-only match (no geometry to score)
            else:
                ov = _overlap_frac(r_bb, g["bbox"])
                if ov < _MIN_OVERLAP:
                    continue
            if ov > best_ov:
                best_idx, best_ov = gi, ov
        if best_idx >= 0:
            used.add(best_idx)
            role = golden_items[best_idx]["role"]
            new["role"] = role
            matched_per_role[role] = matched_per_role.get(role, 0) + 1
        else:
            new["role"] = "noise"
        labeled.append(new)

    # coverage of annotated (non-noise) golden items
    total_by_role: dict[str, int] = {}
    for g in golden_items:
        total_by_role[g["role"]] = total_by_role.get(g["role"], 0) + 1
    per_role = {}
    for role, total in total_by_role.items():
        m = matched_per_role.get(role, 0)
        per_role[role] = {"matched": m, "total": total, "pct": (100.0 * m / total) if total else 0.0}
    total = sum(total_by_role.values())
    matched = sum(matched_per_role.values())
    cov = {
        "matched": matched,
        "total": total,
        "overall_pct": (100.0 * matched / total) if total else 0.0,
        "per_role": per_role,
    }
    return labeled, cov
```

> **Note for implementer:** In Step 1 you confirmed how `walk_structure` is fed in `build_page_rows` (it is called with the atoms `spans`). If the golden page JSON does not itself carry `atoms.spans`, the build script (Task 6) must pass the atoms spans into `golden_annotated_items` — adapt the signature to `golden_annotated_items(golden, spans)` and thread `spans` from the atoms file. Match whatever `build_page_rows` actually does; do not guess.

- [ ] **Step 5: Run tests, verify pass.** Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_live_labels.py -q`. Expected: all passed.

- [ ] **Step 6: Commit.**

```bash
git add src/docomestria/live_labels.py tests/test_live_labels.py
git commit -m "feat: live_labels golden-role transfer + coverage report"
```

---

## Task 6: `scripts/build_live_feature_table.py` — corpus → live CSV + coverage

**Files:**
- Create: `scripts/build_live_feature_table.py`
- Reference (read, do not modify): `scripts/build_training_table.py`

- [ ] **Step 1: Read the template.** Read `scripts/build_training_table.py` fully. Note: `GOLDEN_DIR = ROOT/".planning"/"extraction"/"golden"`, `ATOMS_DIR = ROOT/".planning"/"extraction"/"atoms"`; golden files glob `*.json`, paired with atoms `f"{gp.stem}.atoms.json"`; `_has_structure(golden)` skips legacy goldens; `write_csv(rows, path)` (from `docomestria.golden.training_table`) writes atomically over `FIELDS`. Note the golden JSON carries the source PDF path under the `"pdf"` key and `page` under `"page"`.

- [ ] **Step 2: Write the script.** Engines run **per PDF** (each `extract_*` opens the whole PDF), so group golden pages by source PDF, run each engine once per PDF, then build rows per page. Cache engine outputs per PDF to avoid re-running.

```python
"""Build the LIVE-feature training table: run the three engines on each golden
PDF, compute live features per LiteItem, transfer golden roles, write CSV +
coverage. Mirrors scripts/build_training_table.py but for live features.

Run: /Users/carlos/.pyenv/versions/3.12.9/bin/python scripts/build_live_feature_table.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))   # Codex #1: scripts get no pytest pythonpath

from docomestria.engines import (
    extract_docling_blocks, extract_lite_items, extract_page_sizes,
    extract_visual_rects, extract_words,
)
from docomestria.golden.training_table import FIELDS, write_csv
from docomestria.live_features import build_live_rows
from docomestria.live_labels import golden_annotated_items, transfer_labels

GOLDEN_DIR = ROOT / ".planning" / "extraction" / "golden"
ATOMS_DIR = ROOT / ".planning" / "extraction" / "atoms"
OUT_DIR = ROOT / ".planning" / "extraction" / "training"
OUT_CSV = OUT_DIR / "live_role_table.csv"
OUT_COV = OUT_DIR / "live_coverage.csv"

MIN_PAGES = 10   # Codex #8: refuse to build a near-empty (biased) table


def _has_structure(golden: dict) -> bool:
    return bool(golden.get("structure"))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = []  # (golden_path, golden_dict, atoms_dict)
    for gp in sorted(GOLDEN_DIR.glob("*.json")):
        golden = json.loads(gp.read_text(encoding="utf-8"))
        if not _has_structure(golden):
            continue   # legacy golden without structure — out of scope, as in build_training_table
        atoms_path = ATOMS_DIR / f"{gp.stem}.atoms.json"
        if not atoms_path.exists():
            # Codex #8: hard error, not silent skip — a dropped page biases table + coverage
            raise SystemExit(f"ERROR: structure golden {gp.name} has no atoms at {atoms_path}")
        atoms = json.loads(atoms_path.read_text(encoding="utf-8"))
        pages.append((gp, golden, atoms))

    if len(pages) < MIN_PAGES:
        raise SystemExit(f"ERROR: only {len(pages)} pages (< {MIN_PAGES}); refusing to build a biased table")

    # cache engine outputs per source PDF
    cache: dict[str, dict] = {}

    def engines_for(pdf_path: str) -> dict:
        if pdf_path not in cache:
            cache[pdf_path] = {
                "lite": extract_lite_items(pdf_path),
                "docling": extract_docling_blocks(pdf_path),
                "rects": extract_visual_rects(pdf_path),
                "words": extract_words(pdf_path),
                "sizes": extract_page_sizes(pdf_path),
            }
        return cache[pdf_path]

    all_rows: list[dict] = []
    agg_total: dict[str, int] = {}     # golden annotated count per role (coverage denominator)
    agg_matched: dict[str, int] = {}   # transferred count per role (numerator)
    for gp, golden, atoms in pages:
        pdf_path = golden["pdf"]
        page = int(golden["page"])
        eng = engines_for(pdf_path)
        size = eng["sizes"].get(page, (1.0, 1.0))
        rows = build_live_rows(pdf_path, page, eng["lite"], eng["docling"],
                               eng["rects"], eng["words"], size)
        # see Task 5 Step 4 note: pass atoms spans if walk_structure needs them
        spans = (atoms.get("atoms", {}) or {}).get("spans", [])
        g_items = golden_annotated_items({**golden, "atoms": {"spans": spans}})
        labeled, cov = transfer_labels(rows, g_items)
        all_rows.extend(labeled)
        for role, d in cov["per_role"].items():
            agg_total[role] = agg_total.get(role, 0) + d["total"]
            agg_matched[role] = agg_matched.get(role, 0) + d["matched"]

    all_rows.sort(key=lambda r: (str(r["pdf"]), int(r["page"]) if str(r["page"]).isdigit() else 0,
                                 r["y"] if r["y"] != "" else 9.9, r["x"] if r["x"] != "" else 9.9))
    write_csv(all_rows, OUT_CSV)

    # Codex #2: per-role coverage CSV (role, matched, total, pct) + an __overall__ row
    overall_t = sum(agg_total.values())
    overall_m = sum(agg_matched.values())
    with open(OUT_COV, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["role", "matched", "total", "pct"])
        for role in sorted(agg_total):
            t, m = agg_total[role], agg_matched.get(role, 0)
            w.writerow([role, m, t, round(100.0 * m / t, 2) if t else 0.0])
        w.writerow(["__overall__", overall_m, overall_t,
                    round(100.0 * overall_m / overall_t, 2) if overall_t else 0.0])

    print(f"live_role_table.csv: {len(all_rows)} rows from {len(pages)} pages, "
          f"{len(cache)} PDFs → {OUT_CSV}")
    print(f"coverage: {overall_m}/{overall_t} = "
          f"{(100.0 * overall_m / overall_t) if overall_t else 0.0:.1f}% overall → {OUT_COV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Smoke-run on the real corpus** (this runs Docling — expect several minutes).

Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/python scripts/build_live_feature_table.py`
Expected: prints a row/page/PDF count; `.planning/extraction/training/live_role_table.csv` and `live_coverage.csv` exist; CSV header is the 50 `FIELDS`. If a PDF path in a golden file is missing on disk, report which and stop — do not silently skip (a skipped PDF biases the table).

- [ ] **Step 4: Commit.**

```bash
git add scripts/build_live_feature_table.py
git commit -m "feat: build_live_feature_table — corpus engines→live features→labels→CSV"
```

---

## Task 7: `scripts/train_live_role_classifier.py` — acceptance gate + artifact

**Files:**
- Create: `scripts/train_live_role_classifier.py`
- Reference (read, do not modify): `scripts/train_role_classifier.py`

- [ ] **Step 1: Read the template.** Read `scripts/train_role_classifier.py`. Note: `load_dataset(CSV_PATH)`, `evaluate_oof(df, n_splits=5, random_state=0) -> dict` (keys `macro_f1, baseline_macro_f1, per_class, confusion, labels, oof_pred, n_rows, ...`; `per_class[label]["f1-score"]`), `feature_importances(...)`, `fit_final_model(df) -> dict`, `render_report_md(result, imps)`; pkl saved via `(TRAIN_DIR/"role_model.pkl").write_bytes(pickle.dumps(artifact))`.

- [ ] **Step 2: Write the script** — same shape, but reads the **live** CSV, writes **live** artifacts, and **enforces the gate** (coverage floor + macro-F1 + per-role F1), exiting non-zero on FAIL.

```python
"""Train + GATE the live role classifier. Reads live_role_table.csv, runs
evaluate_oof (GroupKFold-by-pdf), enforces the acceptance gate, writes reports,
fits the final model artifact. Exits non-zero if the gate FAILS.

Run: /Users/carlos/.pyenv/versions/3.12.9/bin/python scripts/train_live_role_classifier.py
"""

from __future__ import annotations

import csv
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))   # Codex #1: scripts get no pytest pythonpath

from docomestria.training.role_classifier import (
    evaluate_oof, feature_importances, fit_final_model, load_dataset, render_report_md,
)

TRAIN_DIR = ROOT / ".planning" / "extraction" / "training"
CSV_PATH = TRAIN_DIR / "live_role_table.csv"
COV_PATH = TRAIN_DIR / "live_coverage.csv"

N_SPLITS = 5
RANDOM_STATE = 0
MACRO_F1_BAR = 0.85           # Decision #1
PER_ROLE_F1_FLOOR = 0.50      # spec: every role usable
COVERAGE_OVERALL = 90.0       # Decision #2
COVERAGE_PER_ROLE = 70.0


def main() -> int:
    df = load_dataset(CSV_PATH)
    result = evaluate_oof(df, n_splits=N_SPLITS, random_state=RANDOM_STATE)
    imps = feature_importances(df, n_splits=N_SPLITS, random_state=RANDOM_STATE)

    failures: list[str] = []

    # --- macro-F1 ---
    macro = result["macro_f1"]
    if macro < MACRO_F1_BAR:
        failures.append(f"macro-F1 {macro:.4f} < {MACRO_F1_BAR}")

    # --- coverage floor from the build-step file (golden totals = denominator) ---
    # Codex #2/#3: the coverage file is AUTHORITATIVE for which annotated roles must
    # exist. A missing file FAILS (build didn't run); each role's denominator comes
    # from golden, so a role cannot be hidden by the model dropping it.
    overall = 0.0
    cov_per_role: dict[str, dict] = {}
    if not COV_PATH.exists():
        failures.append(f"coverage file missing ({COV_PATH}) — build step did not run")
    else:
        with open(COV_PATH, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["role"] == "__overall__":
                    overall = float(r["pct"])
                else:
                    cov_per_role[r["role"]] = {"total": int(r["total"]), "pct": float(r["pct"])}
        if overall < COVERAGE_OVERALL:
            failures.append(f"overall coverage {overall:.1f}% < {COVERAGE_OVERALL}%")
        for role, d in cov_per_role.items():
            if d["total"] > 0 and d["pct"] < COVERAGE_PER_ROLE:
                failures.append(f"role '{role}' coverage {d['pct']:.1f}% < {COVERAGE_PER_ROLE}%")

    # --- per-role F1, keyed off the GOLDEN role set (not result['labels']) ---
    # Codex #3: looping result['labels'] is gameable (a dropped role never checked).
    # Require every golden-present annotated role to (a) appear in trained labels and
    # (b) clear the F1 floor.
    expected_roles = {role for role, d in cov_per_role.items() if d["total"] > 0}
    for role in sorted(expected_roles):
        if role not in result["labels"]:
            failures.append(f"role '{role}' present in golden but absent from trained labels")
            continue
        f1 = result["per_class"].get(role, {}).get("f1-score", 0.0)
        if f1 <= PER_ROLE_F1_FLOOR:
            failures.append(f"role '{role}' F1 {f1:.3f} <= {PER_ROLE_F1_FLOOR}")

    # --- reports ---
    (TRAIN_DIR / "live_role_model_report.md").write_text(render_report_md(result, imps), encoding="utf-8")
    payload = {k: v for k, v in result.items() if k != "oof_pred"}
    payload["top_importances"] = imps[:40]
    payload["gate"] = {"macro_f1_bar": MACRO_F1_BAR, "coverage_overall_pct": round(overall, 2),
                       "coverage_per_role": cov_per_role, "failures": failures}
    (TRAIN_DIR / "live_role_model_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with open(TRAIN_DIR / "live_role_model_confusion.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["true\\pred"] + result["labels"])
        for lab, row in zip(result["labels"], result["confusion"]):
            w.writerow([lab] + row)

    print(f"macro-F1={macro:.4f}  baseline={result['baseline_macro_f1']:.4f}  "
          f"rows={result['n_rows']}  coverage={overall:.1f}%")
    if failures:
        print("GATE: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1

    # gate passed → fit + save the deliverable artifact
    artifact = fit_final_model(df, random_state=RANDOM_STATE)
    (TRAIN_DIR / "live_role_model.pkl").write_bytes(pickle.dumps(artifact))
    print("GATE: PASS → live_role_model.pkl written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> **Note for implementer:** Confirm in Step 1 the exact key for per-class F1 in `evaluate_oof`'s return (`per_class[label]["f1-score"]` per recon). If `evaluate_oof` instead nests metrics differently, adjust the lookup — the gate semantics are the contract.

- [ ] **Step 3: Run the gate on the real table.**

Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/python scripts/train_live_role_classifier.py`
Expected: prints macro-F1, coverage, and `GATE: PASS` (writing `live_role_model.pkl`) or `GATE: FAIL` with reasons. **If FAIL: do not tune the metric.** Per spec Risk #1, fix the weakest feature/emitter (use the importance + confusion + coverage readout to localize) and re-run Task 6 → Task 7. Report the real numbers to Carlos.

- [ ] **Step 4: Commit.**

```bash
git add scripts/train_live_role_classifier.py
git commit -m "feat: train_live_role_classifier — acceptance gate + model artifact"
```

---

## Task 8: Integration gate test

**Files:**
- Create: `tests/test_live_gate.py`

- [ ] **Step 1: Write the integration test.** Marked `@pytest.mark.integration` (it runs the engines, slow). It builds the table via the script entry points and asserts the gate.

```python
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PY = "/Users/carlos/.pyenv/versions/3.12.9/bin/python"


@pytest.mark.integration
def test_live_pipeline_meets_acceptance_gate():
    build = subprocess.run([PY, str(ROOT / "scripts" / "build_live_feature_table.py")],
                           capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    table = ROOT / ".planning" / "extraction" / "training" / "live_role_table.csv"
    assert table.exists()

    train = subprocess.run([PY, str(ROOT / "scripts" / "train_live_role_classifier.py")],
                           capture_output=True, text=True)
    # gate passes → returncode 0 and the pass banner
    assert train.returncode == 0, f"GATE FAILED:\n{train.stdout}\n{train.stderr}"
    assert "GATE: PASS" in train.stdout
```

- [ ] **Step 2: Run the integration test** (slow — runs Docling on the corpus).

Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest tests/test_live_gate.py -q -m integration`
Expected: PASS (gate met). If it fails on the metric, loop back per Task 7 Step 3.

- [ ] **Step 3: Run the full unit suite** to confirm nothing regressed.

Run: `/Users/carlos/.pyenv/versions/3.12.9/bin/pytest -q -m "not integration"`
Expected: all green.

- [ ] **Step 4: Commit.**

```bash
git add tests/test_live_gate.py
git commit -m "test: integration acceptance gate for live-feature pipeline"
```

---

## Final verification (definition of done)

Per spec §Acceptance gate, report the **real** numbers (not "looks good") — use `superpowers:verification-before-completion`:

1. `live_role_table.csv` built; header = the 50 `FIELDS`; every row labeled (a role or `noise`).
2. **Coverage:** ≥ 90% of annotated items overall, ≥ 70% per annotated role (`live_coverage.csv`). Below floor → the label set drifted; fix overlap/normalization, not the threshold.
3. `evaluate_oof` pooled macro-F1 **≥ 0.85** and every role F1 > 0.5 (`live_role_model_report.md`).
4. Report delivered: per-role F1, coverage table, feature-importance readout.
5. `live_role_model.pkl` written (the A-wiring deliverable; it is `fit_final_model` on all rows — never scored as a "test").

Report to Carlos in plain language: lead with PASS/FAIL and the macro-F1 + coverage, then the per-role table, then anything weak. One decision at a time if a methodology call surfaces.

---

## Self-review (completed by plan author)

- **Spec coverage:** §Scope item 1 (char/word emitter) → Task 1; item 2 (live feature builder, full schema, fusion-helper reuse, raw-dataclass layer/rect_type, real colon, zero-fill the two cols) → Tasks 2–4; item 3 (label transfer by norm-text+overlap≥0.30, unmatched→noise, coverage tracking) → Task 5; item 4 (retrain + evaluate_oof + fit_final_model) → Task 7. §Acceptance gate (coverage floor + macro-F1 + per-role + report) → Task 7 + Final verification. §Testing (unit: emitter, builder incl. in-cell/over-signature/missing-engine, matcher incl. no-match; integration: gate) → Tasks 1,3,5,8. **No uncovered spec requirement.**
- **Out-of-scope items** (production loader, 7→5 mapping, 5-PDF/ParseBench regression) → correctly absent.
- **Type consistency:** `build_live_rows` signature is identical in Task 4 definition, Task 6 call, and tests. `transfer_labels(rows, golden_items) -> (rows, cov)` consistent Task 5 ↔ Task 6. `_bbox_to_dict`, `_base_row`, `_engine_features` names stable across tasks. Output namespace (`live_*`) consistent across Tasks 6–8.
- **Known soft spots flagged inline (not placeholders):** `_find_cell` arity, `walk_structure` spans-feeding, and `per_class` F1 key each have a "confirm in Step 1, adapt to the real signature" note — because line-numbered recon can drift and the *names/behavior* are the contract.
