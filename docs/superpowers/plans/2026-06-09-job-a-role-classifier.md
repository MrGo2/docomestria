# Job A — Role Classifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the role training table with Docling-block + signature-rect features (already cached on disk), then train and report a `HistGradientBoosting` role classifier that beats raw-Docling-label-alone.

**Architecture:** Two phases. **Phase 1** adds pure bbox-join feature extraction to the existing builder library (`src/docomestria/golden/training_table.py`), reading only cached atoms — no engine re-run. **Phase 2** adds a new training module (`src/docomestria/training/role_classifier.py`) + thin CLI (`scripts/train_role_classifier.py`) that loads the CSV, splits leakage-free by PDF, trains, and writes a report.

**Tech Stack:** Python, pytest (pythonpath=src, plain `pytest`), pandas, scikit-learn (`HistGradientBoostingClassifier`, `GroupKFold`, `OneHotEncoder`, `compute_sample_weight`).

**Reference spec:** `docs/superpowers/specs/2026-06-09-job-a-role-classifier-design.md`

---

## Background facts the implementer needs (verified)

- **Builder lib:** `src/docomestria/golden/training_table.py`. `FIELDS` (cols) at lines 16-38 (45 columns). `_fmt` formats cells (bool→0/1, floats in `_FLOAT_FIELDS`→4dp, `None`/`""`→`""`). `write_csv` (57-72) is atomic temp+rename, `\n`, QUOTE_MINIMAL.
- **`build_page_rows(golden, atoms)`** (389-487) is the per-page assembler. `atoms` is the full atoms JSON; spans are at `atoms["atoms"]["spans"]`, blocks at `atoms["atoms"]["blocks"]`, rects at `atoms["atoms"]["rects"]`. Page size: `pw, ph = golden.get("page_size_pt", [1.0,1.0])` (both `or 1.0`), `[width, height]` in points.
- **Item geometry is RAW points** inside the loop at line 450: `bb = it.bbox or (signal liteparse bbox)` → a dict `{x,y,w,h}`, **top-left origin**. It is normalised to 0-1 (`bb["x"]/pw`, …) when written. **Do the new bbox joins in RAW point space using `bb`** (before normalisation), same space as block/rect/cell bboxes in atoms.
- **All atoms bboxes are dicts** `{"x","y","w","h"}`, top-left origin (NOT `[x0,y0,x1,y1]`).
- **Docling block** keys: `label, content_layer, bbox, text, formatting, heading_level, self_ref, cells`. `label` ∈ {text, list_item, section_header, picture, checkbox_unselected, page_header, page_footer, checkbox_selected, footnote, table, caption}. `content_layer` ∈ {body, furniture}. `heading_level` int or null. `cells` is a **list-of-rows, each row a list of cell dicts** (null for non-tables).
- **Docling cell** keys include `bbox {x,y,w,h}`, `column_header` (bool), `row_header` (bool), `row_span`, `col_span`, `start_row_offset_idx`, …
- **`_is_signature(w, h, top, page_h)`** at `src/docomestria/engines/pdfplumber.py:37-42` is a **module-level pure function, import-safe** (heavy `import pdfplumber` is deferred inside another function). Thresholds: `SIG_MIN_WIDTH=80.0`, `SIG_MAX_HEIGHT=25.0`, `SIG_BOTTOM_RATIO=0.75`. Logic: `w>=80 and h<=25 and top/page_h>=0.75`. For an atoms rect, `top = rect bbox["y"]`, `page_h = ph`.
- **Tests:** `tests/test_training_table.py` builds fake golden/atoms as inline dicts (no fixtures dir). Run with plain `pytest` (pyproject sets `pythonpath=["src"]`). Assertions are plain `assert`, floats via `< 1e-9`.
- **CSV global order** (in `scripts/build_training_table.py:62-66`): sort key `(pdf, page, node_path, row_idx, col_id, y, x)`. New columns are **appended to the end of `FIELDS`** so existing column order is untouched.

---

## Phase 1 — Feature enrichment (builder)

### Task 1: Pure bbox-geometry helpers

**Files:**
- Modify: `src/docomestria/golden/training_table.py` (add helpers near the other geometry helpers, e.g. after `_overlap_frac`)
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_training_table.py`:

```python
from docomestria.golden.training_table import (
    _bbox_center, _point_in_bbox, find_enclosing_block,
    signature_rect_bboxes, point_in_any_bbox, find_enclosing_cell,
)


def test_bbox_center():
    assert _bbox_center({"x": 10.0, "y": 20.0, "w": 4.0, "h": 6.0}) == (12.0, 23.0)


def test_point_in_bbox():
    bb = {"x": 0.0, "y": 0.0, "w": 10.0, "h": 10.0}
    assert _point_in_bbox(5.0, 5.0, bb) is True
    assert _point_in_bbox(10.0, 10.0, bb) is True   # inclusive edge
    assert _point_in_bbox(11.0, 5.0, bb) is False


def test_find_enclosing_block_picks_smallest_area():
    item = {"x": 5.0, "y": 5.0, "w": 1.0, "h": 1.0}   # center (5.5, 5.5)
    big = {"label": "text", "bbox": {"x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0}}
    small = {"label": "section_header", "bbox": {"x": 4.0, "y": 4.0, "w": 4.0, "h": 4.0}}
    blocks = [big, small]
    assert find_enclosing_block(item, blocks) is small


def test_find_enclosing_block_none_when_outside():
    item = {"x": 500.0, "y": 500.0, "w": 1.0, "h": 1.0}
    blocks = [{"label": "text", "bbox": {"x": 0.0, "y": 0.0, "w": 10.0, "h": 10.0}}]
    assert find_enclosing_block(item, blocks) is None


def test_signature_rect_bboxes_filters_by_geometry():
    rects = [
        {"bbox": {"x": 50.0, "y": 760.0, "w": 120.0, "h": 10.0}},   # wide, short, bottom -> sig
        {"bbox": {"x": 50.0, "y": 100.0, "w": 120.0, "h": 10.0}},   # top -> not sig
        {"bbox": {"x": 50.0, "y": 760.0, "w": 40.0, "h": 10.0}},    # too narrow -> not sig
    ]
    out = signature_rect_bboxes(rects, page_h=800.0)
    assert out == [{"x": 50.0, "y": 760.0, "w": 120.0, "h": 10.0}]


def test_find_enclosing_cell_walks_grid():
    item = {"x": 35.0, "y": 165.0, "w": 2.0, "h": 2.0}   # center (36,166)
    table = {"label": "table", "bbox": {"x": 0.0, "y": 0.0, "w": 600.0, "h": 800.0},
             "cells": [[{"bbox": {"x": 33.0, "y": 163.0, "w": 83.0, "h": 7.5},
                         "column_header": True, "row_header": False}]]}
    other = {"label": "text", "bbox": {"x": 0.0, "y": 0.0, "w": 10.0, "h": 10.0}, "cells": None}
    cell = find_enclosing_cell(item, [other, table])
    assert cell["column_header"] is True
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_training_table.py -k "bbox or enclosing or signature_rect" -v`
Expected: FAIL — `ImportError: cannot import name '_bbox_center'`.

- [ ] **Step 3: Implement the helpers**

Add to `src/docomestria/golden/training_table.py` (import the predicate at top with the other imports):

```python
from docomestria.engines.pdfplumber import _is_signature
```

```python
def _bbox_center(bb: dict) -> tuple[float, float]:
    return (bb["x"] + bb["w"] / 2.0, bb["y"] + bb["h"] / 2.0)


def _point_in_bbox(px: float, py: float, bb: dict) -> bool:
    return (bb["x"] <= px <= bb["x"] + bb["w"]
            and bb["y"] <= py <= bb["y"] + bb["h"])


def find_enclosing_block(item_bbox: dict, blocks: list[dict]) -> dict | None:
    """Smallest-area Docling block whose bbox contains the item's center. None if outside all."""
    cx, cy = _bbox_center(item_bbox)
    best = None
    best_area = None
    for b in blocks:
        bb = b.get("bbox")
        if not bb or not _point_in_bbox(cx, cy, bb):
            continue
        area = bb["w"] * bb["h"]
        if best_area is None or area < best_area:
            best, best_area = b, area
    return best


def signature_rect_bboxes(rects: list[dict], page_h: float) -> list[dict]:
    """Bboxes of rects classified as signature fields (wide, short, bottom-of-page)."""
    out = []
    for r in rects:
        bb = r.get("bbox")
        if not bb:
            continue
        if _is_signature(bb["w"], bb["h"], bb["y"], page_h):
            out.append(bb)
    return out


def point_in_any_bbox(px: float, py: float, bboxes: list[dict]) -> bool:
    return any(_point_in_bbox(px, py, bb) for bb in bboxes)


def find_enclosing_cell(item_bbox: dict, blocks: list[dict]) -> dict | None:
    """First Docling table cell whose bbox contains the item's center. None if not in a table cell."""
    cx, cy = _bbox_center(item_bbox)
    for b in blocks:
        if b.get("label") != "table" or not b.get("cells"):
            continue
        for row in b["cells"]:
            for cell in row:
                cb = cell.get("bbox")
                if cb and _point_in_bbox(cx, cy, cb):
                    return cell
    return None
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `pytest tests/test_training_table.py -k "bbox or enclosing or signature_rect" -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "feat: pure bbox-join helpers for Docling-block/cell/signature-rect lookup"
```

---

### Task 2: Add the four new feature columns to FIELDS

**Files:**
- Modify: `src/docomestria/golden/training_table.py:16-38` (`FIELDS`) and `:40-43` (`_FLOAT_FIELDS`)
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing test**

```python
def test_fields_has_new_docling_and_signature_columns():
    from docomestria.golden.training_table import FIELDS
    for col in ("docling_label", "docling_heading_level",
                "docling_content_layer", "rect_is_signature_field"):
        assert col in FIELDS
    # appended at the end so existing column order is preserved
    assert FIELDS[-4:] == ["docling_label", "docling_heading_level",
                           "docling_content_layer", "rect_is_signature_field"]
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_training_table.py::test_fields_has_new_docling_and_signature_columns -v`
Expected: FAIL — `assert 'docling_label' in FIELDS`.

- [ ] **Step 3: Append the columns**

Edit `FIELDS` (lines 16-38) — add after the neighbour group's last entry `"bold_above_nonbold_below",`:

```python
    # docling-layout (enclosing block) + signature rect
    "docling_label", "docling_heading_level",
    "docling_content_layer", "rect_is_signature_field",
]
```

`docling_heading_level` is an integer written via `str()` (default `_fmt` path) — do **not** add it to `_FLOAT_FIELDS`. `docling_label`/`docling_content_layer` are strings; `rect_is_signature_field` is a bool (→0/1). No `_FLOAT_FIELDS` change needed.

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_training_table.py::test_fields_has_new_docling_and_signature_columns -v`
Expected: PASS.

- [ ] **Step 5: Run the full existing suite to confirm no regression**

Run: `pytest tests/test_training_table.py -v`
Expected: PASS — existing rows now carry 4 extra empty (`""`) columns; geometry/content/determinism tests unaffected.

- [ ] **Step 6: Commit**

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "feat: add docling-label + signature-rect feature columns to FIELDS"
```

---

### Task 3: Populate the new features in build_page_rows

**Files:**
- Modify: `src/docomestria/golden/training_table.py` — the `build_page_rows` partial-row loop (lines 447-460, where raw `bb` is in scope)
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing test**

```python
def _atoms_two_spans_with_docling():
    a = _atoms_two_spans()  # existing helper: spans for "Nº Modelo" / "F_AS-5"
    a["atoms"]["blocks"] = [
        # encloses the "Nº Modelo" key span (center ~ (90, 29))
        {"label": "section_header", "content_layer": "body", "heading_level": 2,
         "bbox": {"x": 50.0, "y": 20.0, "w": 80.0, "h": 14.0}, "cells": None},
    ]
    a["atoms"]["rects"] = [
        # wide/short/bottom rect -> signature, encloses neither span (both near top)
        {"bbox": {"x": 50.0, "y": 760.0, "w": 200.0, "h": 10.0}},
    ]
    return a


def test_build_page_rows_populates_docling_block_features():
    rows, _ = build_page_rows(_golden_with_two_kv(), _atoms_two_spans_with_docling())
    key = {r["role"]: r for r in rows}["key"]   # "Nº Modelo"
    assert key["docling_label"] == "section_header"
    assert key["docling_heading_level"] == 2
    assert key["docling_content_layer"] == "body"


def test_build_page_rows_signature_rect_flag():
    # add a span sitting inside the bottom signature rect
    a = _atoms_two_spans_with_docling()
    a["atoms"]["spans"].append(
        {"text": "Firma del titular", "bbox": {"x": 60.0, "y": 762.0, "w": 90.0, "h": 8.0},
         "font_size": 9.0, "is_bold": False, "case_class": "Title"})
    g = _golden_with_two_kv()  # the new span is unannotated -> becomes a noise row
    rows, _ = build_page_rows(g, a)
    sig_rows = [r for r in rows if r["text"] == "Firma del titular"]
    assert len(sig_rows) == 1
    assert sig_rows[0]["rect_is_signature_field"] == 1
    # the top key span is NOT in a signature rect
    key = {r["role"]: r for r in rows if r["role"] == "key"}["key"]
    assert key["rect_is_signature_field"] == 0


def test_build_page_rows_no_blocks_key_is_safe():
    # existing _atoms_two_spans() has no "blocks"/"rects" keys -> must not crash, cols empty
    rows, _ = build_page_rows(_golden_with_two_kv(), _atoms_two_spans())
    key = {r["role"]: r for r in rows}["key"]
    assert key["docling_label"] == ""
    assert key["rect_is_signature_field"] == 0
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_training_table.py -k "docling_block_features or signature_rect_flag or no_blocks_key" -v`
Expected: FAIL — `KeyError`/`assert '' == 'section_header'` (features not populated).

- [ ] **Step 3: Implement population in build_page_rows**

Before the partial loop (just before line 447 `partial = []`), compute the page-level block/rect context once:

```python
    _blocks = (atoms.get("atoms") or {}).get("blocks") or []
    _rects = (atoms.get("atoms") or {}).get("rects") or []
    _sig_bboxes = signature_rect_bboxes(_rects, ph)
```

Inside the loop, within the `if bb:` block (after the geometry normalisation at lines 452-457, where raw `bb` is available), add:

```python
        if bb:
            # ... existing x/y/w/h/is_centered normalisation ...
            cx, cy = _bbox_center(bb)
            blk = find_enclosing_block(bb, _blocks)
            if blk is not None:
                row["docling_label"] = blk.get("label") or ""
                hl = blk.get("heading_level")
                row["docling_heading_level"] = hl if hl is not None else ""
                row["docling_content_layer"] = blk.get("content_layer") or ""
            row["rect_is_signature_field"] = 1 if point_in_any_bbox(cx, cy, _sig_bboxes) else 0
```

Note: `rect_is_signature_field` must default to `0` (not `""`) even when there are no signature rects — set it for every item that has a `bb`. Items with no `bb` keep the FIELDS default `""`; that is acceptable (rare; matches how other geometry cols behave).

- [ ] **Step 4: Run tests, verify they pass**

Run: `pytest tests/test_training_table.py -k "docling_block_features or signature_rect_flag or no_blocks_key" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run full suite**

Run: `pytest tests/test_training_table.py -v`
Expected: PASS (all, including determinism).

- [ ] **Step 6: Commit**

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "feat: populate docling-block label/heading/layer + signature-rect features per item"
```

---

### Task 4: Fix the docling-header silent-zero bug (re-derived/noise rows)

**Files:**
- Modify: `src/docomestria/golden/training_table.py` — same `build_page_rows` loop
- Test: `tests/test_training_table.py`

**Context:** `rederive_signal` / `noise_items` set `docling=None`, so `signal_features` forces `docling_column_header`/`docling_row_header` to `0` for those rows even when the item sits in a real Docling table cell. Fix: when the item has no Docling signal (`row["docling_present"] == 0`), look up the enclosing table cell and use its real header flags.

- [ ] **Step 1: Write the failing test**

```python
def test_build_page_rows_recovers_docling_header_for_noise_in_table_cell():
    a = _atoms_two_spans()
    # a noise span landing inside a table header cell
    a["atoms"]["spans"].append(
        {"text": "Concepto", "bbox": {"x": 35.0, "y": 165.0, "w": 50.0, "h": 7.0},
         "font_size": 9.0, "is_bold": True, "case_class": "Title"})
    a["atoms"]["blocks"] = [
        {"label": "table", "content_layer": "body", "heading_level": None,
         "bbox": {"x": 0.0, "y": 0.0, "w": 600.0, "h": 800.0},
         "cells": [[{"bbox": {"x": 33.0, "y": 163.0, "w": 83.0, "h": 7.5},
                     "column_header": True, "row_header": False}]]},
    ]
    rows, _ = build_page_rows(_golden_with_two_kv(), a)
    noise = [r for r in rows if r["text"] == "Concepto"][0]
    assert noise["docling_present"] == 0          # still no full docling signal
    assert noise["docling_column_header"] == 1     # recovered from the enclosing cell
    assert noise["docling_row_header"] == 0
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_training_table.py::test_build_page_rows_recovers_docling_header_for_noise_in_table_cell -v`
Expected: FAIL — `assert 0 == 1` (header forced to 0 today).

- [ ] **Step 3: Implement the recovery**

In the same `if bb:` block in `build_page_rows`, after the block/signature population from Task 3, add:

```python
            if row["docling_present"] == 0:
                cell = find_enclosing_cell(bb, _blocks)
                if cell is not None:
                    row["docling_column_header"] = 1 if cell.get("column_header") else 0
                    row["docling_row_header"] = 1 if cell.get("row_header") else 0
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_training_table.py::test_build_page_rows_recovers_docling_header_for_noise_in_table_cell -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + commit**

Run: `pytest tests/test_training_table.py -v` → PASS.

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "fix: recover docling column/row-header for re-derived/noise rows from enclosing table cell"
```

---

### Task 5: Regenerate the enriched CSV and sanity-check coverage

**Files:**
- Output: `.planning/extraction/training/role_table.csv` (regenerated)
- No test file — this is a verification step with a one-off check.

- [ ] **Step 1: Regenerate the table**

Run: `python3 scripts/build_training_table.py`
Expected: prints page/row totals, exits 0, rewrites `role_table.csv`.

- [ ] **Step 2: Verify new-column coverage is non-trivial (not all-NaN)**

Run:
```bash
python3 -c "
import pandas as pd
df = pd.read_csv('.planning/extraction/training/role_table.csv')
print('rows', len(df), 'cols', df.shape[1])
for c in ['docling_label','docling_heading_level','docling_content_layer','rect_is_signature_field']:
    nonempty = df[c].notna().sum()
    print(c, 'non-empty:', int(nonempty))
print('docling_label values:')
print(df['docling_label'].value_counts(dropna=False).to_string())
print('signature rows:', int((df['rect_is_signature_field']==1).sum()))
"
```
Expected: `cols` == 49 (45 + 4). `docling_label` non-empty for a large fraction (most items fall inside a Docling block); value_counts shows `text/section_header/list_item/...`. `rect_is_signature_field` has some 1s (signatures exist on contract pages). If `docling_label` is ~all empty → the bbox join is mis-aligned (coordinate space) — STOP and debug before Phase 2.

- [ ] **Step 3: Commit the regenerated CSV**

```bash
git add .planning/extraction/training/role_table.csv
git commit -m "data: regenerate role_table.csv with docling-block + signature features (49 cols)"
```

---

## Phase 2 — Training & report

### Task 6: Ensure scikit-learn + pandas are available

**Files:**
- Modify: `pyproject.toml` (only if missing)

- [ ] **Step 1: Check availability**

Run: `python3 -c "import sklearn, pandas; print(sklearn.__version__, pandas.__version__)"`
Expected: prints two versions. If `ModuleNotFoundError`, go to Step 2; else skip to Task 7.

- [ ] **Step 2: Add the deps**

Run: `uv add scikit-learn pandas`
Expected: updates `pyproject.toml` + lockfile, installs. Re-run Step 1 to confirm.

- [ ] **Step 3: Commit (only if pyproject changed)**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add scikit-learn + pandas for role-classifier training"
```

---

### Task 7: Dataset loading, column split, and (text,role) dedup

**Files:**
- Create: `src/docomestria/training/__init__.py` (empty)
- Create: `src/docomestria/training/role_classifier.py`
- Test: `tests/test_role_classifier.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_role_classifier.py`:

```python
import pandas as pd
from docomestria.training.role_classifier import (
    FEATURE_COLS, CATEGORICAL_COLS, LABEL_COL, GROUP_COL,
    load_dataset, dedupe_text_role,
)


def _tiny_df():
    return pd.DataFrame([
        {"pdf": "A", "text": "Total", "role": "key", "x": 0.1, "docling_label": "text"},
        {"pdf": "A", "text": "Total", "role": "key", "x": 0.1, "docling_label": "text"},  # dup
        {"pdf": "B", "text": "100 EUR", "role": "value", "x": 0.5, "docling_label": "text"},
    ])


def test_column_constants_partition_cleanly():
    # features and provenance must not overlap; label/group are provenance
    assert LABEL_COL == "role"
    assert GROUP_COL == "pdf"
    assert "docling_label" in CATEGORICAL_COLS
    assert "role" not in FEATURE_COLS and "pdf" not in FEATURE_COLS
    assert "text" not in FEATURE_COLS


def test_dedupe_text_role_drops_exact_dups():
    df, dropped = dedupe_text_role(_tiny_df())
    assert dropped == 1
    assert len(df) == 2


def test_load_dataset_reads_empty_as_nan(tmp_path):
    p = tmp_path / "t.csv"
    # one numeric col empty -> NaN; categorical empty -> NaN
    p.write_text("pdf,text,role,x,docling_label\nA,Foo,key,,text\n", encoding="utf-8")
    df = load_dataset(p)
    assert pd.isna(df.loc[0, "x"])
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_role_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError: docomestria.training.role_classifier`.

- [ ] **Step 3: Implement the module skeleton**

Create `src/docomestria/training/__init__.py` (empty file).

Create `src/docomestria/training/role_classifier.py`:

```python
"""Job A — role classifier: load, split, baseline, train, report.

Trains a HistGradientBoosting classifier on .planning/extraction/training/role_table.csv
to predict the per-item `role`, evaluated leakage-free by PDF, and compares against a
raw-Docling-label baseline. See docs/superpowers/specs/2026-06-09-role-classifier...md.
"""
from __future__ import annotations

import pandas as pd

LABEL_COL = "role"
GROUP_COL = "pdf"

# Provenance columns excluded from X (leak the answer or aren't real signals).
PROVENANCE_COLS = [
    "pdf", "page", "text", "node_path", "source_node_type",
    "in_table", "table_id", "row_idx", "col_id", "role",
]

# Low-cardinality categorical strings (one-hot encoded; rest are numeric).
CATEGORICAL_COLS = ["docling_label", "docling_content_layer"]

# The 35 original + 4 new feature columns, minus provenance. Built at import from a
# canonical list so it stays in sync with the CSV header.
_ALL_FEATURES = [
    "x", "y", "w", "h", "font_size", "font_size_ratio", "is_bold",
    "case_upper", "case_lower", "case_title", "case_mixed",
    "digit_ratio", "has_currency", "has_date", "has_percent", "has_iban",
    "has_nif", "starts_paren", "ends_colon", "n_numeric_tokens", "len_chars",
    "inside_rect", "colon_present", "engine_agreement", "pdfplumber_present",
    "liteparse_present", "docling_present", "docling_column_header",
    "docling_row_header", "compound_span", "is_centered", "gap_above",
    "gap_below", "font_ratio_vs_below", "bold_above_nonbold_below",
    "docling_label", "docling_heading_level", "docling_content_layer",
    "rect_is_signature_field",
]
FEATURE_COLS = list(_ALL_FEATURES)
NUMERIC_COLS = [c for c in FEATURE_COLS if c not in CATEGORICAL_COLS]


def load_dataset(path) -> pd.DataFrame:
    """Read the role table; empty cells -> NaN. Categorical cols kept as strings."""
    df = pd.read_csv(path, dtype={c: "string" for c in CATEGORICAL_COLS})
    return df


def dedupe_text_role(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop exact-duplicate (text, role) rows (keep first). Returns (df, n_dropped)."""
    before = len(df)
    out = df.drop_duplicates(subset=["text", LABEL_COL], keep="first").reset_index(drop=True)
    return out, before - len(out)
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `pytest tests/test_role_classifier.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/training/__init__.py src/docomestria/training/role_classifier.py tests/test_role_classifier.py
git commit -m "feat: role-classifier dataset loading, column split, (text,role) dedup"
```

---

### Task 8: Docling-label baseline (train-fold majority + noise fallback)

**Files:**
- Modify: `src/docomestria/training/role_classifier.py`
- Test: `tests/test_role_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
from docomestria.training.role_classifier import docling_baseline_predict


def test_docling_baseline_majority_and_fallback():
    train = pd.DataFrame([
        {"docling_label": "section_header", "role": "section_header"},
        {"docling_label": "section_header", "role": "section_header"},
        {"docling_label": "text", "role": "prose"},
        {"docling_label": "text", "role": "key"},
        {"docling_label": "text", "role": "prose"},   # text -> prose majority
        {"docling_label": None, "role": "noise"},
        {"docling_label": None, "role": "noise"},      # global majority -> noise
    ])
    test = pd.DataFrame([
        {"docling_label": "section_header"},   # -> section_header
        {"docling_label": "text"},             # -> prose
        {"docling_label": None},               # missing -> global majority (noise)
        {"docling_label": "caption"},          # unseen -> global majority (noise)
    ])
    preds, fallback_share = docling_baseline_predict(train, test)
    assert list(preds) == ["section_header", "prose", "noise", "noise"]
    assert abs(fallback_share - 0.5) < 1e-9   # 2 of 4 test rows hit fallback
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_role_classifier.py::test_docling_baseline_majority_and_fallback -v`
Expected: FAIL — `ImportError: docling_baseline_predict`.

- [ ] **Step 3: Implement**

Add to `role_classifier.py`:

```python
def docling_baseline_predict(train: pd.DataFrame, test: pd.DataFrame) -> tuple[list, float]:
    """Predict role = train-fold majority role per docling_label; missing/unseen -> global
    train majority. Returns (predictions, share_of_test_rows_using_fallback)."""
    global_majority = train[LABEL_COL].mode().iloc[0]
    label_to_role = {}
    for lab, grp in train.groupby(train["docling_label"], dropna=True):
        label_to_role[lab] = grp[LABEL_COL].mode().iloc[0]
    preds, fallback = [], 0
    for lab in test["docling_label"]:
        if pd.isna(lab) or lab not in label_to_role:
            preds.append(global_majority)
            fallback += 1
        else:
            preds.append(label_to_role[lab])
    return preds, (fallback / len(test) if len(test) else 0.0)
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_role_classifier.py::test_docling_baseline_majority_and_fallback -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/training/role_classifier.py tests/test_role_classifier.py
git commit -m "feat: raw-Docling-label baseline with train-majority + noise fallback"
```

---

### Task 9: Feature matrix encoding (one-hot categoricals + numeric NaN)

**Files:**
- Modify: `src/docomestria/training/role_classifier.py`
- Test: `tests/test_role_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from docomestria.training.role_classifier import build_encoder, encode_features


def test_encode_features_onehot_and_numeric_nan():
    train = pd.DataFrame([
        {"x": 0.1, "docling_label": "text", "docling_content_layer": "body"},
        {"x": 0.2, "docling_label": "section_header", "docling_content_layer": "body"},
    ])
    test = pd.DataFrame([
        {"x": np.nan, "docling_label": "caption", "docling_content_layer": "furniture"},  # all unseen
    ])
    enc = build_encoder(train[["x", "docling_label", "docling_content_layer"]],
                        numeric=["x"], categorical=["docling_label", "docling_content_layer"])
    Xtr = encode_features(enc, train[["x", "docling_label", "docling_content_layer"]],
                          numeric=["x"], categorical=["docling_label", "docling_content_layer"])
    Xte = encode_features(enc, test[["x", "docling_label", "docling_content_layer"]],
                          numeric=["x"], categorical=["docling_label", "docling_content_layer"])
    assert Xtr.shape[0] == 2 and Xte.shape[0] == 1
    assert Xtr.shape[1] == Xte.shape[1]          # same width despite unseen categories
    assert np.isnan(Xte[0, 0])                    # numeric NaN preserved (first col = x)
    # unseen categories -> all-zero one-hot block (handle_unknown="ignore")
    assert Xte[0, 1:].sum() == 0.0
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_role_classifier.py -k encode_features -v`
Expected: FAIL — `ImportError: build_encoder`.

- [ ] **Step 3: Implement**

Add to `role_classifier.py` (imports at top):

```python
import numpy as np
from sklearn.preprocessing import OneHotEncoder
```

```python
def build_encoder(train_X: pd.DataFrame, numeric: list[str], categorical: list[str]):
    """Fit a OneHotEncoder on the categorical columns of the TRAIN fold only."""
    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    ohe.fit(train_X[categorical].astype("string").fillna("__nan__"))
    return ohe


def encode_features(ohe, X: pd.DataFrame, numeric: list[str], categorical: list[str]) -> np.ndarray:
    """Numeric block (float, NaN preserved) hstacked with the one-hot categorical block.
    Column order: numeric columns first (in `numeric` order), then one-hot block."""
    num = X[numeric].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    cat = ohe.transform(X[categorical].astype("string").fillna("__nan__"))
    return np.hstack([num, cat])
```

Note: `"__nan__"` makes "missing category" its own one-hot column fit on train; unseen test categories still map to all-zero via `handle_unknown="ignore"`. Numeric NaN flows to HGB which handles it natively.

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_role_classifier.py -k encode_features -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/training/role_classifier.py tests/test_role_classifier.py
git commit -m "feat: one-hot + numeric-NaN feature encoding for role classifier"
```

---

### Task 10: GroupKFold pooled-OOF training + evaluation

**Files:**
- Modify: `src/docomestria/training/role_classifier.py`
- Test: `tests/test_role_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
from docomestria.training.role_classifier import evaluate_oof


def _synthetic_dataset(n_pdfs=6, per_pdf=40):
    # learnable signal: docling_label maps cleanly to role, plus a numeric separator
    import itertools
    roles = ["key", "value", "noise", "section_header"]
    rows = []
    for p in range(n_pdfs):
        for i in range(per_pdf):
            r = roles[i % len(roles)]
            rows.append({
                "pdf": f"PDF{p}", "text": f"t{p}_{i}", "role": r,
                "x": 0.1 if r == "key" else 0.8, "y": (i % 10) / 10.0,
                "font_size": 12.0 if r == "section_header" else 9.0,
                "docling_label": {"key": "text", "value": "text",
                                  "noise": "page_footer",
                                  "section_header": "section_header"}[r],
                "docling_content_layer": "furniture" if r == "noise" else "body",
                "docling_heading_level": 1 if r == "section_header" else "",
                # remaining feature cols default 0 (filled below)
            })
    df = pd.DataFrame(rows)
    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = 0
    return df


def test_evaluate_oof_returns_pooled_metrics_and_beats_nothing_gracefully():
    df = _synthetic_dataset()
    result = evaluate_oof(df, n_splits=3, random_state=0)
    # required report keys
    for k in ("macro_f1", "per_class", "confusion", "labels",
              "baseline_macro_f1", "baseline_fallback_share",
              "n_rows", "n_dropped_dups", "sklearn_version"):
        assert k in result
    # one OOF prediction per (deduped) row
    assert len(result["oof_pred"]) == result["n_rows"]
    # learnable synthetic data -> model should be strong
    assert result["macro_f1"] > 0.8


def test_evaluate_oof_is_deterministic():
    df = _synthetic_dataset()
    a = evaluate_oof(df, n_splits=3, random_state=0)
    b = evaluate_oof(df, n_splits=3, random_state=0)
    assert a["macro_f1"] == b["macro_f1"]
    assert a["confusion"] == b["confusion"]
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_role_classifier.py -k evaluate_oof -v`
Expected: FAIL — `ImportError: evaluate_oof`.

- [ ] **Step 3: Implement**

Add to `role_classifier.py` (imports):

```python
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import f1_score, classification_report, confusion_matrix
```

```python
def _new_model(random_state: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(random_state=random_state)


def evaluate_oof(df: pd.DataFrame, n_splits: int = 5, random_state: int = 0) -> dict:
    """Dedup, then GroupKFold-by-pdf; collect pooled out-of-fold predictions for the model
    and the Docling baseline; return a metrics dict (all computed on pooled OOF)."""
    df, n_dropped = dedupe_text_role(df)
    y = df[LABEL_COL].to_numpy()
    groups = df[GROUP_COL].to_numpy()
    labels = sorted(pd.unique(y).tolist())

    oof_pred = np.empty(len(df), dtype=object)
    base_pred = np.empty(len(df), dtype=object)
    fallback_shares = []

    gkf = GroupKFold(n_splits=n_splits)
    for tr_idx, te_idx in gkf.split(df, y, groups):
        tr, te = df.iloc[tr_idx], df.iloc[te_idx]
        ohe = build_encoder(tr[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
        Xtr = encode_features(ohe, tr[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
        Xte = encode_features(ohe, te[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
        ytr = tr[LABEL_COL].to_numpy()
        sw = compute_sample_weight("balanced", ytr)
        model = _new_model(random_state)
        model.fit(Xtr, ytr, sample_weight=sw)
        oof_pred[te_idx] = model.predict(Xte)
        bp, fb = docling_baseline_predict(tr, te)
        base_pred[te_idx] = np.array(bp, dtype=object)
        fallback_shares.append(fb)

    report = classification_report(y, oof_pred, labels=labels,
                                   output_dict=True, zero_division=0)
    cm = confusion_matrix(y, oof_pred, labels=labels).tolist()
    return {
        "macro_f1": float(f1_score(y, oof_pred, labels=labels, average="macro", zero_division=0)),
        "baseline_macro_f1": float(f1_score(y, base_pred, labels=labels, average="macro", zero_division=0)),
        "baseline_fallback_share": float(np.mean(fallback_shares)),
        "per_class": {lab: report[lab] for lab in labels},
        "confusion": cm,
        "labels": labels,
        "oof_pred": oof_pred.tolist(),
        "n_rows": len(df),
        "n_dropped_dups": n_dropped,
        "sklearn_version": sklearn.__version__,
    }
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `pytest tests/test_role_classifier.py -k evaluate_oof -v`
Expected: PASS (2 tests). The synthetic data is cleanly learnable so `macro_f1 > 0.8`.

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/training/role_classifier.py tests/test_role_classifier.py
git commit -m "feat: GroupKFold pooled-OOF training + eval with balanced weights"
```

---

### Task 11: Permutation importances + final model persistence

**Files:**
- Modify: `src/docomestria/training/role_classifier.py`
- Test: `tests/test_role_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
import pickle
from docomestria.training.role_classifier import fit_final_model, feature_importances


def test_fit_final_model_pickles_and_predicts(tmp_path):
    df, _ = dedupe_text_role(_synthetic_dataset())
    artifact = fit_final_model(df, random_state=0)
    assert set(artifact) >= {"model", "ohe", "feature_cols", "numeric_cols",
                             "categorical_cols", "labels", "sklearn_version"}
    p = tmp_path / "m.pkl"
    p.write_bytes(pickle.dumps(artifact))
    loaded = pickle.loads(p.read_bytes())
    X = encode_features(loaded["ohe"], df[FEATURE_COLS].head(3),
                        loaded["numeric_cols"], loaded["categorical_cols"])
    preds = loaded["model"].predict(X)
    assert len(preds) == 3


def test_feature_importances_ranked_named():
    df = _synthetic_dataset()
    imps = feature_importances(df, n_splits=3, random_state=0, n_repeats=2)
    # list of (feature_name, importance) sorted desc; names are real feature cols (or one-hot expansions)
    assert imps[0][1] >= imps[-1][1]
    assert all(isinstance(name, str) for name, _ in imps)
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_role_classifier.py -k "final_model or feature_importances" -v`
Expected: FAIL — `ImportError: fit_final_model`.

- [ ] **Step 3: Implement**

Add to `role_classifier.py` (import):

```python
from sklearn.inspection import permutation_importance
```

```python
def fit_final_model(df: pd.DataFrame, random_state: int = 0) -> dict:
    """Refit the encoder + model on ALL rows; return a picklable artifact dict."""
    ohe = build_encoder(df[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    X = encode_features(ohe, df[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    y = df[LABEL_COL].to_numpy()
    sw = compute_sample_weight("balanced", y)
    model = _new_model(random_state)
    model.fit(X, y, sample_weight=sw)
    return {
        "model": model, "ohe": ohe, "feature_cols": FEATURE_COLS,
        "numeric_cols": NUMERIC_COLS, "categorical_cols": CATEGORICAL_COLS,
        "labels": sorted(pd.unique(y).tolist()), "sklearn_version": sklearn.__version__,
    }


def _encoded_feature_names(ohe) -> list[str]:
    cat_names = ohe.get_feature_names_out(CATEGORICAL_COLS).tolist()
    return list(NUMERIC_COLS) + cat_names


def feature_importances(df: pd.DataFrame, n_splits: int = 5, random_state: int = 0,
                        n_repeats: int = 5) -> list[tuple[str, float]]:
    """Permutation importances computed on one held-out GroupKFold fold."""
    df, _ = dedupe_text_role(df)
    y = df[LABEL_COL].to_numpy()
    groups = df[GROUP_COL].to_numpy()
    gkf = GroupKFold(n_splits=n_splits)
    tr_idx, te_idx = next(gkf.split(df, y, groups))
    tr, te = df.iloc[tr_idx], df.iloc[te_idx]
    ohe = build_encoder(tr[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    Xtr = encode_features(ohe, tr[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    Xte = encode_features(ohe, te[FEATURE_COLS], NUMERIC_COLS, CATEGORICAL_COLS)
    model = _new_model(random_state)
    model.fit(Xtr, tr[LABEL_COL].to_numpy(),
              sample_weight=compute_sample_weight("balanced", tr[LABEL_COL].to_numpy()))
    r = permutation_importance(model, Xte, te[LABEL_COL].to_numpy(),
                               n_repeats=n_repeats, random_state=random_state,
                               scoring="f1_macro")
    names = _encoded_feature_names(ohe)
    pairs = sorted(zip(names, r.importances_mean.tolist()), key=lambda t: t[1], reverse=True)
    return pairs
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `pytest tests/test_role_classifier.py -k "final_model or feature_importances" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/training/role_classifier.py tests/test_role_classifier.py
git commit -m "feat: final-model persistence + permutation feature importances"
```

---

### Task 12: CLI script — train and write report + artifacts

**Files:**
- Create: `scripts/train_role_classifier.py`
- Output: `.planning/extraction/training/role_model.pkl`, `role_model_report.md`, `role_model_report.json`, `role_model_confusion.csv`
- Test: `tests/test_role_classifier.py` (smoke test of the report-writing helper)

- [ ] **Step 1: Write the failing test**

```python
from docomestria.training.role_classifier import render_report_md


def test_render_report_md_contains_headline_and_table():
    result = {
        "macro_f1": 0.83, "baseline_macro_f1": 0.71, "baseline_fallback_share": 0.12,
        "per_class": {"key": {"precision": 0.9, "recall": 0.8, "f1-score": 0.85, "support": 100}},
        "confusion": [[10]], "labels": ["key"], "oof_pred": ["key"],
        "n_rows": 1, "n_dropped_dups": 3, "sklearn_version": "1.5.0",
    }
    imps = [("docling_label_section_header", 0.21), ("ends_colon", 0.05)]
    md = render_report_md(result, imps)
    assert "Macro-F1" in md and "0.83" in md
    assert "vs Docling baseline" in md and "0.71" in md
    assert "docling_label_section_header" in md
    assert "key" in md   # per-class row
```

- [ ] **Step 2: Run test, verify it fails**

Run: `pytest tests/test_role_classifier.py -k render_report_md -v`
Expected: FAIL — `ImportError: render_report_md`.

- [ ] **Step 3: Implement `render_report_md` in the module**

Add to `role_classifier.py`:

```python
def render_report_md(result: dict, importances: list[tuple[str, float]]) -> str:
    lines = ["# Role Classifier — Report (Job A)", ""]
    delta = result["macro_f1"] - result["baseline_macro_f1"]
    lines += [
        f"- **Macro-F1 (pooled OOF):** {result['macro_f1']:.4f}",
        f"- **vs Docling baseline:** {result['baseline_macro_f1']:.4f} "
        f"(delta {delta:+.4f}, fallback share {result['baseline_fallback_share']:.3f})",
        f"- Rows: {result['n_rows']} (dropped {result['n_dropped_dups']} dup text/role) "
        f"| sklearn {result['sklearn_version']}",
        "", "## Per-class", "", "| role | precision | recall | f1 | support |",
        "|---|---|---|---|---|",
    ]
    for lab in result["labels"]:
        m = result["per_class"][lab]
        lines.append(f"| {lab} | {m['precision']:.3f} | {m['recall']:.3f} "
                     f"| {m['f1-score']:.3f} | {int(m['support'])} |")
    lines += ["", "## Confusion (rows=true, cols=pred)", "",
              "| | " + " | ".join(result["labels"]) + " |",
              "|" + "---|" * (len(result["labels"]) + 1)]
    for lab, row in zip(result["labels"], result["confusion"]):
        lines.append(f"| **{lab}** | " + " | ".join(str(v) for v in row) + " |")
    lines += ["", "## Top feature importances", ""]
    for name, imp in importances[:25]:
        lines.append(f"- {name}: {imp:.4f}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test, verify it passes**

Run: `pytest tests/test_role_classifier.py -k render_report_md -v`
Expected: PASS.

- [ ] **Step 5: Write the CLI script**

Create `scripts/train_role_classifier.py`:

```python
#!/usr/bin/env python3
"""Train the Job-A role classifier from role_table.csv and write model + report.

Usage:  python3 scripts/train_role_classifier.py
Deterministic: fixed random_state, unshuffled GroupKFold.
"""
from __future__ import annotations

import csv
import json
import pickle
from pathlib import Path

from docomestria.training.role_classifier import (
    load_dataset, evaluate_oof, feature_importances, fit_final_model, render_report_md,
)

ROOT = Path(__file__).resolve().parents[1]
TRAIN_DIR = ROOT / ".planning" / "extraction" / "training"
CSV_PATH = TRAIN_DIR / "role_table.csv"
N_SPLITS = 5
RANDOM_STATE = 0


def main() -> int:
    df = load_dataset(CSV_PATH)
    result = evaluate_oof(df, n_splits=N_SPLITS, random_state=RANDOM_STATE)
    imps = feature_importances(df, n_splits=N_SPLITS, random_state=RANDOM_STATE)

    # report.md
    (TRAIN_DIR / "role_model_report.md").write_text(
        render_report_md(result, imps), encoding="utf-8")
    # report.json (drop the bulky oof_pred from the JSON headline)
    json_payload = {k: v for k, v in result.items() if k != "oof_pred"}
    json_payload["top_importances"] = imps[:40]
    (TRAIN_DIR / "role_model_report.json").write_text(
        json.dumps(json_payload, indent=2, sort_keys=True), encoding="utf-8")
    # confusion.csv
    with open(TRAIN_DIR / "role_model_confusion.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["true\\pred"] + result["labels"])
        for lab, row in zip(result["labels"], result["confusion"]):
            w.writerow([lab] + row)
    # final model
    artifact = fit_final_model(df, random_state=RANDOM_STATE)
    (TRAIN_DIR / "role_model.pkl").write_bytes(pickle.dumps(artifact))

    print(f"macro-F1={result['macro_f1']:.4f}  "
          f"baseline={result['baseline_macro_f1']:.4f}  "
          f"delta={result['macro_f1'] - result['baseline_macro_f1']:+.4f}  "
          f"rows={result['n_rows']} (dropped {result['n_dropped_dups']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run the script end-to-end on the real table**

Run: `python3 scripts/train_role_classifier.py`
Expected: prints `macro-F1=… baseline=… delta=… rows=…`; writes 4 files into `.planning/extraction/training/`. Inspect:
```bash
sed -n '1,30p' .planning/extraction/training/role_model_report.md
```
Expected: headline macro-F1, vs-baseline delta, per-class table (7 roles), confusion matrix, top importances (expect `docling_label_*` near the top).

- [ ] **Step 7: Commit (code + artifacts)**

```bash
git add scripts/train_role_classifier.py src/docomestria/training/role_classifier.py tests/test_role_classifier.py
git add .planning/extraction/training/role_model_report.md .planning/extraction/training/role_model_report.json .planning/extraction/training/role_model_confusion.csv .planning/extraction/training/role_model.pkl
git commit -m "feat: train_role_classifier CLI — model + report + confusion artifacts"
```

---

### Task 13: Determinism guard for the training script

**Files:**
- Test: `tests/test_role_classifier.py`

- [ ] **Step 1: Write the test**

```python
def test_full_pipeline_determinism_on_synthetic():
    df = _synthetic_dataset()
    a = evaluate_oof(df, n_splits=3, random_state=0)
    b = evaluate_oof(df, n_splits=3, random_state=0)
    assert a["macro_f1"] == b["macro_f1"]
    assert a["baseline_macro_f1"] == b["baseline_macro_f1"]
    assert a["confusion"] == b["confusion"]
    assert a["oof_pred"] == b["oof_pred"]
```

- [ ] **Step 2: Run it, verify it passes**

Run: `pytest tests/test_role_classifier.py::test_full_pipeline_determinism_on_synthetic -v`
Expected: PASS (HGB `random_state=0` + unshuffled GroupKFold ⇒ identical results).

- [ ] **Step 3: Run the whole suite**

Run: `pytest -q`
Expected: PASS — both `tests/test_training_table.py` and `tests/test_role_classifier.py` green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_role_classifier.py
git commit -m "test: determinism guard for role-classifier OOF pipeline"
```

---

## Self-Review (spec coverage)

- §4 enrichment (docling label/heading/layer + signature rect) → Tasks 1-3, 5. ✓
- §4 silent-zero header fix → Task 4. ✓
- §4 "pure atoms join, no engine re-run" → Task 1 (no PDF open; `_is_signature` import-safe). ✓
- §5 HGB native NaN → Task 9 (numeric NaN preserved) / Task 10. ✓
- §5 encoding contract → Task 9 (OneHotEncoder `handle_unknown="ignore"` — refinement over spec's ordinal/-1, which would break HGB; same goal). ✓
- §5 baseline + noise fallback → Task 8. ✓
- §5 GroupKFold-by-pdf + (text,role) dedup → Tasks 7, 10. ✓
- §5 balanced `sample_weight` (not `class_weight`) → Task 10. ✓
- §5/§8 determinism (random_state, sklearn version, unshuffled folds) → Tasks 10, 13. ✓
- §6 pooled-OOF per-class P/R/F1 + macro-F1 + confusion + baseline delta + importances → Tasks 10, 11, 12. ✓
- §6 artifacts under `.planning/extraction/training/` → Task 12. ✓
- §8 re-runnable one-command chain → `build_training_table.py` (Task 5) + `train_role_classifier.py` (Task 12). ✓

**Note on two deliberate refinements (flagged to the user, both preserve spec intent):**
1. Categorical encoding uses `OneHotEncoder(handle_unknown="ignore")` rather than the spec's `OrdinalEncoder(unknown_value=-1)` — `-1` violates HGB's categorical contract (`0..n-1`/NaN). One-hot is robust to unseen categories and needs no `categorical_features` wiring.
2. `docling_heading_level` is treated as numeric (not categorical) — it's ordinal depth.
