# Role-Classification Training Table — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/build_training_table.py` that converts the 66 golden page-files into one flat CSV — one row per atomic text item, with a 3-engine feature vector and a golden role label — ready to train role-classification weights next session.

**Architecture:** A pure-Python, deterministic builder. Core logic lives in an importable, testable library module `src/docomestria/golden/training_table.py`; the CLI in `scripts/build_training_table.py` is a thin glob → build → write wrapper. Features are read mostly from each golden leaf's `evidence` "signal" block (which already carries liteparse font/bold/case + per-engine bboxes); key items that only have a `label_bbox` are re-derived by matching against `atoms.spans` directly (no PDF, no `EngineData`). Content flags are computed per item text via a shared `src/docomestria/text_features.py` (refactored out of `extract_atoms.py` so atoms and the training table compute identically). Unannotated atom spans become `noise` rows.

**Tech Stack:** Python 3, stdlib `csv` + `json` + `re` + `dataclasses` + `statistics`, reuse of `docomestria.golden.engine_data._norm`/`_contains`. No numpy/pandas/sklearn. pandas is NOT required (histogram via `collections.Counter`).

**Spec:** `docs/superpowers/specs/2026-06-08-role-classification-training-table-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `src/docomestria/text_features.py` | **New.** `content_flags(text)` + `case_class(text)` + their regexes. Single source of truth. |
| `scripts/extract_atoms.py` | **Modify.** Import the two helpers from `text_features` instead of defining them locally. |
| `src/docomestria/golden/training_table.py` | **New.** `FIELDS`, `Item` dataclass, `signal_features`, `rederive_signal`, `walk_structure`, `noise_items`, `build_page_rows`, `write_csv`. |
| `scripts/build_training_table.py` | **New.** CLI: glob goldens, load atoms, per-page `build_page_rows`, concat, sort, `write_csv`, print histogram. |
| `tests/test_text_features.py` | **New.** Unit tests for the two helpers. |
| `tests/test_training_table.py` | **New.** Unit tests for walk / signal / rederive / noise / page assembly / determinism. |

---

## Conventions (read once)

- Golden dir: `.planning/extraction/golden/` ; files `<stem>-p<NN>.json`.
- Atoms dir: `.planning/extraction/atoms/` ; files `<stem>-p<NN>.atoms.json`.
- `EngineData` constructor is at `src/docomestria/golden/engine_data.py:57`; `_norm` at `:25`; `_contains` is module-level in the same file. We import only `_norm`, `_contains`.
- An atoms span: `{"text", "bbox":{x,y,w,h}, "font_name", "font_size", "is_bold", "case_class", "content":{...}}`.
- A golden leaf "signal" dict (inside `evidence`) has keys: `text, row_y_hint, x_hint, pdfplumber|null, liteparse|null, docling|null, rect|null, colon_signal|null, value_extent|null, cell_bbox, engine_agreement`. `liteparse` (when present) = `{span_id, bbox, case_class, is_bold, font_size}`. `docling` (when present) = `{cell_ref, bbox, column_header, row_header}`.
- Run tests with: `pytest <path> -v` from repo root (package is installed editable; no PYTHONPATH needed). If `pytest` is not on PATH, use `python3 -m pytest <path> -v`.

---

## Task 1: Refactor content/case helpers into an importable module

**Files:**
- Create: `src/docomestria/text_features.py`
- Modify: `scripts/extract_atoms.py` (lines 41–82 region: the regexes + `_case_class` + `_content_flags`)
- Test: `tests/test_text_features.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_features.py`:

```python
from docomestria.text_features import content_flags, case_class


def test_case_class_values():
    assert case_class("TOTAL DEUDA") == "UPPER"
    assert case_class("importe pendiente") == "lower"
    assert case_class("DNI Titular") == "Title"  # mixed up/lo ratios, words start-upper
    assert case_class("IBAN es20") == "mixed"  # up/lo both <0.80, not title-cased
    assert case_class("123,45") == "none"


def test_content_flags_keys_and_values():
    f = content_flags("1.234,56 €")
    assert set(f) == {
        "digit_ratio", "has_currency", "has_date", "has_percent",
        "has_iban", "has_nif", "starts_paren", "ends_colon",
        "n_numeric_tokens", "len_chars",
    }
    assert f["has_currency"] is True
    assert f["len_chars"] == len("1.234,56 €")
    assert content_flags("Nº Modelo:")["ends_colon"] is True
    assert content_flags("(ver nota)")["starts_paren"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_text_features.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docomestria.text_features'`

- [ ] **Step 3: Create the module**

Create `src/docomestria/text_features.py` by moving the exact logic from `scripts/extract_atoms.py:41-82` (rename the two functions to public names, drop the leading underscore):

```python
"""Text feature helpers shared by atoms extraction and the training table.

Single source of truth: extract_atoms.py imports from here so the atoms files
and the training table compute identical content flags.
"""
import re

_NUM_TOKEN = re.compile(r"\d[\d.,]*")
_CURRENCY = re.compile(r"[€$£]|\bEUR\b|\bUSD\b")
_DATE = re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b")
_PERCENT = re.compile(r"\d\s*%")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[\sA-Z0-9]{10,}\b")
_NIF = re.compile(r"\b\d{8}[A-Z]\b|\b[A-Z]\d{7}[A-Z0-9]\b")


def case_class(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "none"
    up = sum(1 for c in letters if c.isupper())
    lo = sum(1 for c in letters if c.islower())
    if up / len(letters) >= 0.80:
        return "UPPER"
    if lo / len(letters) >= 0.80:
        return "lower"
    words = [w for w in text.split() if any(ch.isalpha() for ch in w)]
    if words:
        starts_upper = sum(
            1 for w in words
            if next((c for c in w if c.isalpha()), "").isupper()
        )
        if starts_upper / len(words) >= 0.70:
            return "Title"
    return "mixed"


def content_flags(text: str) -> dict:
    return {
        "digit_ratio": sum(c.isdigit() for c in text) / max(1, len(text)),
        "has_currency": bool(_CURRENCY.search(text)),
        "has_date": bool(_DATE.search(text)),
        "has_percent": bool(_PERCENT.search(text)),
        "has_iban": bool(_IBAN.search(text)),
        "has_nif": bool(_NIF.search(text)),
        "starts_paren": text.startswith("("),
        "ends_colon": text.rstrip().endswith(":"),
        "n_numeric_tokens": len(_NUM_TOKEN.findall(text)),
        "len_chars": len(text),
    }
```

> CRITICAL — MOVE, DON'T RETYPE: the regex block above is **illustrative only**. The
> existing atoms were produced by the exact regexes at `scripts/extract_atoms.py:41-46` and
> the functions at `:49-82`. **Physically cut those exact lines** and paste them into
> `text_features.py` (renaming `_case_class`→`case_class`, `_content_flags`→`content_flags`).
> Do not hand-retype the regexes — any drift in the `/ - € ¥ % IBAN NIF` patterns silently
> changes feature semantics. After moving, verify:
> `python3 -c "import ast,sys; ast.parse(open('src/docomestria/text_features.py').read())"`
> and confirm the 6 regex lines are byte-identical to the originals (e.g. `git diff` of the
> deleted lines vs the added ones).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_text_features.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Point extract_atoms.py at the shared module**

In `scripts/extract_atoms.py`: delete the local `_NUM_TOKEN/_CURRENCY/_DATE/_PERCENT/_IBAN/_NIF` regexes and the `_case_class` / `_content_flags` defs (lines ~41–82). Add an import near the top of the file, after the existing imports:

```python
from docomestria.text_features import case_class as _case_class, content_flags as _content_flags
```

(Aliasing to the old private names means the rest of `extract_atoms.py` is untouched.)

- [ ] **Step 6: Verify extract_atoms still imports cleanly**

Run: `python3 -c "import scripts.extract_atoms"` from repo root (or `python3 scripts/extract_atoms.py --help` if it has argparse).
Expected: no ImportError / NameError. (Do NOT re-run a full atoms extraction — logic is unchanged.)

- [ ] **Step 7: Commit**

```bash
git add src/docomestria/text_features.py scripts/extract_atoms.py tests/test_text_features.py
git commit -m "refactor: extract content/case helpers to importable text_features module"
```

---

## Task 2: Row schema + deterministic CSV writer

**Files:**
- Create: `src/docomestria/golden/training_table.py`
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_training_table.py`:

```python
from pathlib import Path
from docomestria.golden.training_table import FIELDS, write_csv


def test_fields_are_unique_and_start_with_provenance():
    assert len(FIELDS) == len(set(FIELDS))
    assert FIELDS[:5] == ["pdf", "page", "text", "node_path", "source_node_type"]
    assert "role" in FIELDS


def test_write_csv_is_byte_deterministic(tmp_path):
    rows = [
        {f: "" for f in FIELDS},
        {f: "" for f in FIELDS},
    ]
    rows[0].update({"pdf": "B", "page": 2, "role": "value",
                    "is_bold": True, "x": 0.123456})
    rows[1].update({"pdf": "A", "page": 1, "role": "key",
                    "is_bold": False, "x": 0.5})
    out = tmp_path / "t.csv"
    write_csv(rows, out)
    text = out.read_text(encoding="utf-8")
    lines = text.splitlines()
    # header is FIELDS joined; bool -> 0/1; float rounded to 4 dp; \n newline
    assert lines[0] == ",".join(FIELDS)
    assert ",0.1235," in text          # x rounded to 4 dp
    # bools encoded as 0/1 somewhere in the data rows
    assert any(cell in ("0", "1") for cell in lines[1].split(","))
    # rows are written in the order given (sorting happens in the CLI, not here)
    assert lines[1].startswith("B,2,")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_training_table.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docomestria.golden.training_table'`

- [ ] **Step 3: Create the module skeleton with FIELDS + write_csv**

Create `src/docomestria/golden/training_table.py`:

```python
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
```

> NOTE: `_fmt` enforces the missing-sentinel / bool / float-precision policy; `csv.writer(lineterminator="\n", QUOTE_MINIMAL)` enforces the newline dialect and quotes only cells that need it. Same rows in → byte-identical CSV out. Because the writer handles commas/newlines, Task 7 does NOT strip commas from `text`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_training_table.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "feat: training-table row schema + deterministic CSV writer"
```

---

## Task 3: Extract features from a golden "signal" dict

**Files:**
- Modify: `src/docomestria/golden/training_table.py`
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_training_table.py`:

```python
from docomestria.golden.training_table import signal_features


_SIGNAL = {
    "text": "Nombre",
    "pdfplumber": {"bbox": {"x": 1, "y": 2, "w": 3, "h": 4}},
    "liteparse": {"span_id": 7, "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
                  "case_class": "Title", "is_bold": True, "font_size": 10.0},
    "docling": {"cell_ref": "#/texts/36", "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
                "column_header": None, "row_header": None},
    "rect": None,
    "colon_signal": None,
    "engine_agreement": 3,
}


def test_signal_features_reads_liteparse_and_presence():
    f = signal_features(_SIGNAL)
    assert f["font_size"] == 10.0
    assert f["is_bold"] is True
    assert f["case_title"] == 1 and f["case_upper"] == 0
    assert f["liteparse_present"] == 1
    assert f["pdfplumber_present"] == 1
    assert f["docling_present"] == 1
    assert f["inside_rect"] == 0
    assert f["colon_present"] == 0
    assert f["engine_agreement"] == 3
    assert f["span_id"] == 7


def test_signal_features_none_is_all_absent():
    f = signal_features(None)
    assert f["liteparse_present"] == 0
    assert f["font_size"] == ""
    assert f["span_id"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_training_table.py -k signal_features -v`
Expected: FAIL — `ImportError: cannot import name 'signal_features'`

- [ ] **Step 3: Implement `signal_features`**

Add to `src/docomestria/golden/training_table.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_training_table.py -k signal_features -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "feat: signal_features — typography/context from golden evidence"
```

---

## Task 4: Re-derive a signal from atoms (key items with only a bbox)

**Files:**
- Modify: `src/docomestria/golden/training_table.py`
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_training_table.py`:

```python
from docomestria.golden.training_table import rederive_signal


_SPANS = [
    {"text": "Nº Modelo", "bbox": {"x": 477.0, "y": 24.0, "w": 47.0, "h": 9.0},
     "font_size": 10.0, "is_bold": False, "case_class": "Title"},
    {"text": "Nombre", "bbox": {"x": 100.0, "y": 24.0, "w": 30.0, "h": 9.0},
     "font_size": 10.0, "is_bold": True, "case_class": "Title"},
    {"text": "Nombre", "bbox": {"x": 400.0, "y": 24.0, "w": 30.0, "h": 9.0},
     "font_size": 9.0, "is_bold": False, "case_class": "Title"},
]


def test_rederive_resolves_by_text_and_bbox_overlap():
    sig, status = rederive_signal("Nº Modelo",
                                  {"x": 478.0, "y": 24.0, "w": 47.0, "h": 9.0},
                                  _SPANS)
    assert status == "resolved"
    assert sig["liteparse"]["span_id"] == 0
    assert sig["liteparse"]["font_size"] == 10.0


def test_rederive_ambiguous_when_two_spans_overlap_same_text():
    # both "Nombre" spans match text; neither overlaps the query bbox -> unresolved
    sig, status = rederive_signal("Nombre",
                                  {"x": 250.0, "y": 24.0, "w": 30.0, "h": 9.0},
                                  _SPANS)
    assert status == "unresolved"
    assert sig is None


def test_rederive_picks_the_overlapping_one_when_unambiguous():
    sig, status = rederive_signal("Nombre",
                                  {"x": 101.0, "y": 24.0, "w": 30.0, "h": 9.0},
                                  _SPANS)
    assert status == "resolved"
    assert sig["liteparse"]["span_id"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_training_table.py -k rederive -v`
Expected: FAIL — `ImportError: cannot import name 'rederive_signal'`

- [ ] **Step 3: Implement `rederive_signal`**

Add to `src/docomestria/golden/training_table.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_training_table.py -k rederive -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "feat: rederive_signal — atoms span match for label-only key items"
```

---

## Task 5: Walk the structure tree into raw Items (the adapter matrix)

**Files:**
- Modify: `src/docomestria/golden/training_table.py`
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_training_table.py`:

```python
from docomestria.golden.training_table import Item, walk_structure


def _items_by_role(items):
    out = {}
    for it in items:
        out.setdefault(it.role, []).append(it.text)
    return out


def test_walk_kv_group_emits_key_and_value_rows():
    structure = [{
        "type": "kv_group", "id": "titular",
        "pairs": [{
            "label": "Nombre", "value": "ADRIAN",
            "label_bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
            "bbox": {"x": 5, "y": 2, "w": 3, "h": 4},
            "evidence": {
                "label": {"liteparse": {"span_id": 7, "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
                          "case_class": "Title", "is_bold": True, "font_size": 10.0},
                          "engine_agreement": 3},
                "value": {"liteparse": {"span_id": 8, "bbox": {"x": 5, "y": 2, "w": 3, "h": 4},
                          "case_class": "UPPER", "is_bold": False, "font_size": 10.0},
                          "engine_agreement": 3},
            },
        }],
    }]
    items = walk_structure(structure, spans=[])
    roles = _items_by_role(items)
    assert roles["key"] == ["Nombre"]
    assert roles["value"] == ["ADRIAN"]
    # different span_ids -> not compound
    assert all(it.compound_span == 0 for it in items)


def test_walk_fused_span_sets_compound_on_both_rows():
    # key and value resolve to the SAME liteparse span_id -> compound_span=1
    structure = [{
        "type": "kv_group", "id": "g",
        "pairs": [{
            "label": "Nº Modelo", "value": "F_AS-5",
            "label_bbox": {"x": 1, "y": 2, "w": 9, "h": 4},
            "bbox": {"x": 1, "y": 2, "w": 9, "h": 4},
            "evidence": {
                "label": {"liteparse": {"span_id": 4, "bbox": {"x": 1, "y": 2, "w": 9, "h": 4},
                          "case_class": "Title", "is_bold": False, "font_size": 10.0}},
                "value": {"liteparse": {"span_id": 4, "bbox": {"x": 1, "y": 2, "w": 9, "h": 4},
                          "case_class": "Title", "is_bold": False, "font_size": 10.0}},
            },
        }],
    }]
    items = walk_structure(structure, spans=[])
    assert all(it.compound_span == 1 for it in items)
    # content features still differ per row (computed later from each item's text)
    from docomestria.text_features import content_flags
    assert content_flags("Nº Modelo")["digit_ratio"] == 0.0
    assert content_flags("F_AS-5")["digit_ratio"] > 0.0


def test_walk_table_maps_header_keycol_valuecol():
    structure = [{
        "type": "table", "id": "t1", "title": "Datos",
        "columns": [{"id": "label", "label": "Concepto"},
                    {"id": "value", "label": "Importe"}],
        "rows": [{
            "label": {"text": "Precio", "evidence": {"liteparse": None}, "bbox": {"x": 1, "y": 9, "w": 2, "h": 2}},
            "value": {"text": "14.990,00", "evidence": {"liteparse": None}, "bbox": {"x": 4, "y": 9, "w": 2, "h": 2}},
        }],
    }]
    items = walk_structure(structure, spans=[])
    roles = _items_by_role(items)
    assert "Precio" in roles["key"]
    assert "14.990,00" in roles["value"]
    # column header labels become table_header
    assert "Concepto" in roles["table_header"] and "Importe" in roles["table_header"]


def test_walk_noise_node():
    structure = [{"type": "noise", "id": "n1", "text": "pág 1/24",
                  "bbox": {"x": 1, "y": 1, "w": 2, "h": 2},
                  "evidence": {"text_signal": {"liteparse": None, "engine_agreement": 1}}}]
    items = walk_structure(structure, spans=[])
    assert items[0].role == "noise" and items[0].text == "pág 1/24"


def test_walk_unknown_node_raises():
    import pytest
    with pytest.raises(ValueError):
        walk_structure([{"type": "frobnicate"}], spans=[])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_training_table.py -k walk -v`
Expected: FAIL — `ImportError: cannot import name 'Item'`

- [ ] **Step 3: Implement `Item`, `_as_signal`, and `walk_structure`**

Add to `src/docomestria/golden/training_table.py`:

```python
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
            # Repeated record blocks (e.g. BBVA titulares): items[] -> named
            # groups -> named fields. A filled field is {text, evidence, bbox}
            # (a VALUE on the page); an empty field is [None, y_hint]. The field
            # *name* is a schema label with no on-page geometry, so emit only the
            # filled values.
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_training_table.py -k walk -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "feat: walk_structure adapter matrix (all node types -> Items, fail on unknown)"
```

---

## Task 6: Unmatched atoms → noise Items

**Files:**
- Modify: `src/docomestria/golden/training_table.py`
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_training_table.py`:

```python
from docomestria.golden.training_table import noise_items


def test_unmatched_atoms_become_noise():
    spans = [
        {"text": "Nombre", "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
         "font_size": 10.0, "is_bold": True, "case_class": "Title"},
        {"text": "JUNK WATERMARK", "bbox": {"x": 9, "y": 9, "w": 5, "h": 4},
         "font_size": 7.0, "is_bold": False, "case_class": "UPPER"},
    ]
    # span 0 consumed by an annotated item; span 1 is unmatched background
    consumed = {0}
    annotated = [("Nombre", {"x": 1, "y": 2, "w": 3, "h": 4})]
    noise = noise_items(spans, consumed, annotated)
    assert len(noise) == 1
    assert noise[0].role == "noise"
    assert noise[0].text == "JUNK WATERMARK"
    assert noise[0].signal["liteparse"]["span_id"] == 1


def test_atom_matched_by_text_bbox_not_double_counted():
    spans = [{"text": "Nombre", "bbox": {"x": 1, "y": 2, "w": 3, "h": 4},
              "font_size": 10.0, "is_bold": True, "case_class": "Title"}]
    # not in consumed set, but text+bbox match an annotated item -> NOT noise
    annotated = [("Nombre", {"x": 1, "y": 2, "w": 3, "h": 4})]
    assert noise_items(spans, set(), annotated) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_training_table.py -k unmatched -v` and `-k double_counted`
Expected: FAIL — `ImportError: cannot import name 'noise_items'`

- [ ] **Step 3: Implement `noise_items`**

Add to `src/docomestria/golden/training_table.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_training_table.py -k "unmatched or double_counted" -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "feat: noise_items — unannotated atoms become noise rows (double-guarded)"
```

---

## Task 7: Assemble one page into final rows (page-level + neighbour features)

**Files:**
- Modify: `src/docomestria/golden/training_table.py`
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_training_table.py`:

```python
from docomestria.golden.training_table import build_page_rows


def _golden_with_two_kv():
    return {
        "pdf": "DOC", "page": 1, "page_size_pt": [600.0, 800.0],
        "structure": [{
            "type": "kv_group", "id": "g",
            "pairs": [{
                "label": "Nº Modelo", "value": "F_AS-5",
                "label_bbox": {"x": 60.0, "y": 24.0, "w": 60.0, "h": 10.0},
                "bbox": {"x": 300.0, "y": 24.0, "w": 40.0, "h": 10.0},
                "evidence": {
                    "label": {"liteparse": {"span_id": 0, "bbox": {"x": 60.0, "y": 24.0, "w": 60.0, "h": 10.0},
                              "case_class": "Title", "is_bold": False, "font_size": 10.0},
                              "engine_agreement": 2},
                    "value": {"liteparse": {"span_id": 1, "bbox": {"x": 300.0, "y": 24.0, "w": 40.0, "h": 10.0},
                              "case_class": "Title", "is_bold": False, "font_size": 10.0},
                              "engine_agreement": 2},
                },
            }],
        }],
    }


def _atoms_two_spans():
    return {"atoms": {"spans": [
        {"text": "Nº Modelo", "bbox": {"x": 60.0, "y": 24.0, "w": 60.0, "h": 10.0},
         "font_size": 10.0, "is_bold": False, "case_class": "Title"},
        {"text": "F_AS-5", "bbox": {"x": 300.0, "y": 24.0, "w": 40.0, "h": 10.0},
         "font_size": 10.0, "is_bold": False, "case_class": "Title"},
    ], "rects": []}}


def test_build_page_rows_geometry_and_label_and_content():
    rows, diag = build_page_rows(_golden_with_two_kv(), _atoms_two_spans())
    assert len(rows) == 2  # both atoms consumed -> no extra noise
    by_role = {r["role"]: r for r in rows}
    key = by_role["key"]
    # geometry normalised by page size [600,800]
    assert abs(key["x"] - 60.0 / 600.0) < 1e-9
    assert abs(key["w"] - 60.0 / 600.0) < 1e-9
    # content computed from the item's own text
    assert by_role["value"]["digit_ratio"] > 0  # "F_AS-5" has a digit
    assert key["digit_ratio"] == 0.0            # "Nº Modelo" has none
    # font_size_ratio: both items have font 10 -> median 10 -> ratio 1.0
    assert abs(key["font_size_ratio"] - 1.0) < 1e-9
    assert diag["unresolved_keys"] == 0


def test_build_page_rows_emits_noise_for_extra_atom():
    g = _golden_with_two_kv()
    atoms = _atoms_two_spans()
    atoms["atoms"]["spans"].append(
        {"text": "WATERMARK", "bbox": {"x": 10.0, "y": 700.0, "w": 80.0, "h": 8.0},
         "font_size": 6.0, "is_bold": False, "case_class": "UPPER"})
    rows, diag = build_page_rows(g, atoms)
    assert any(r["role"] == "noise" and r["text"] == "WATERMARK" for r in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_training_table.py -k build_page_rows -v`
Expected: FAIL — `ImportError: cannot import name 'build_page_rows'`

- [ ] **Step 3: Implement `build_page_rows`**

Add to `src/docomestria/golden/training_table.py`:

```python
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
```

> NOTE on `text`: provenance `text` is kept raw (only surrounding whitespace stripped).
> Commas and embedded newlines are preserved and safely quoted by `csv.writer` (Task 2), so
> Spanish amounts like `14.990,00` survive intact. Content features (`digit_ratio`,
> `n_numeric_tokens`, `has_currency`) are computed from the original `it.text`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_training_table.py -k build_page_rows -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the whole unit suite**

Run: `pytest tests/test_training_table.py tests/test_text_features.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add src/docomestria/golden/training_table.py tests/test_training_table.py
git commit -m "feat: build_page_rows — page assembly, geometry norm, neighbour features"
```

---

## Task 8: CLI — glob corpus, build, sort, write CSV, print histogram

**Files:**
- Create: `scripts/build_training_table.py`

- [ ] **Step 1: Write the CLI**

Create `scripts/build_training_table.py`:

```python
#!/usr/bin/env python3
"""Build the role-classification training table from all golden page-files.

Usage:  python3 scripts/build_training_table.py
Output: .planning/extraction/training/role_table.csv  (+ printed histogram)
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from docomestria.golden.training_table import FIELDS, build_page_rows, write_csv  # noqa: E402

GOLDEN_DIR = ROOT / ".planning" / "extraction" / "golden"
ATOMS_DIR = ROOT / ".planning" / "extraction" / "atoms"
OUT_DIR = ROOT / ".planning" / "extraction" / "training"
OUT = OUT_DIR / "role_table.csv"
MIN_EXPECTED_PAGES = 50  # corpus is 66 page-files; fail loud if the glob is near-empty


def _has_structure(golden: dict) -> bool:
    """True for structure-format goldens (a non-empty `structure` tree).

    Legacy goldens carry only top-level `sections`/`kv_pairs` (no per-engine
    evidence) and must be skipped — walking them would emit nothing and turn
    every atom on the page into noise.
    """
    return isinstance(golden.get("structure"), list) and len(golden["structure"]) > 0


def main() -> int:
    golden_files = sorted(GOLDEN_DIR.glob("*.json"))
    if len(golden_files) < MIN_EXPECTED_PAGES:
        print(f"ERROR: only {len(golden_files)} goldens under {GOLDEN_DIR} "
              f"(expected >= {MIN_EXPECTED_PAGES}). Aborting.", file=sys.stderr)
        return 1

    all_rows = []
    totals = {"unresolved_keys": 0, "noise_atoms": 0, "pages": 0}
    legacy_skipped: list[str] = []
    missing_atoms: list[str] = []
    for gp in golden_files:
        golden = json.loads(gp.read_text(encoding="utf-8"))
        if not _has_structure(golden):
            legacy_skipped.append(gp.name)
            continue
        atoms_path = ATOMS_DIR / f"{gp.stem}.atoms.json"
        if not atoms_path.exists():
            missing_atoms.append(gp.name)   # a STRUCTURE golden with no atoms = error
            continue
        atoms = json.loads(atoms_path.read_text(encoding="utf-8"))
        rows, diag = build_page_rows(golden, atoms)
        all_rows.extend(rows)
        totals["unresolved_keys"] += diag["unresolved_keys"]
        totals["noise_atoms"] += diag["noise_atoms"]
        totals["pages"] += 1

    # deterministic global order
    all_rows.sort(key=lambda r: (
        str(r["pdf"]), int(r["page"]) if str(r["page"]).isdigit() else 0,
        r["node_path"], str(r["row_idx"]), str(r["col_id"]),
        r["y"] if r["y"] != "" else 9.9, r["x"] if r["x"] != "" else 9.9,
    ))

    # A structure-format golden with no atoms is a hard error — abort before
    # writing so we never emit a partial table.
    if missing_atoms:
        print(f"ERROR: {len(missing_atoms)} structure goldens have no atoms file:",
              file=sys.stderr)
        for n in missing_atoms:
            print(f"  - {n}", file=sys.stderr)
        return 1
    if totals["pages"] == 0:
        print("ERROR: no structure-format goldens processed; nothing to write.",
              file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(all_rows, OUT)

    hist = Counter(r["role"] for r in all_rows)
    print(f"\nWrote {len(all_rows)} rows from {totals['pages']} pages -> {OUT}")
    print("Class histogram:")
    for role in ["section_header", "key", "value", "table_header",
                 "prose", "signature", "noise"]:
        print(f"  {role:<16} {hist.get(role, 0)}")
    other = set(hist) - {"section_header", "key", "value", "table_header",
                         "prose", "signature", "noise"}
    for role in sorted(other):
        print(f"  {role:<16} {hist[role]}  (UNEXPECTED)")
    print(f"\nunresolved_keys={totals['unresolved_keys']}  "
          f"noise_atoms={totals['noise_atoms']}")
    if legacy_skipped:
        print(f"\nSKIPPED {len(legacy_skipped)} legacy goldens (no `structure` tree — "
              f"re-scaffold to include them):")
        for n in legacy_skipped:
            print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it over the real corpus**

Run: `python3 scripts/build_training_table.py`
Expected: prints `Wrote N rows from ~46 pages` (the ~20 legacy goldens are listed under "SKIPPED … legacy goldens"), a histogram with non-zero counts for `key`, `value`, `noise` (at minimum), and `unresolved_keys` low (single/low-double digits, not hundreds). No `(UNEXPECTED)` roles. Exit code 0. No traceback. (If it exits 1 with "structure goldens have no atoms", generate the missing atoms first or investigate — that is a real error, not legacy.)

- [ ] **Step 3: Sanity-check the output exists and is non-trivial**

Run: `wc -l .planning/extraction/training/role_table.csv && head -3 .planning/extraction/training/role_table.csv`
Expected: line count = N+1 (header + rows), header equals the `FIELDS` order, two readable data rows.

- [ ] **Step 4: Commit**

```bash
git add scripts/build_training_table.py .planning/extraction/training/role_table.csv
git commit -m "feat: build_training_table CLI + generated role_table.csv"
```

---

## Task 9: Determinism guard

**Files:**
- Test: `tests/test_training_table.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_training_table.py`:

```python
def test_build_page_rows_is_deterministic():
    g, a = _golden_with_two_kv(), _atoms_two_spans()
    r1, _ = build_page_rows(g, a)
    r2, _ = build_page_rows(g, a)
    assert r1 == r2  # same input -> identical rows, identical order
```

- [ ] **Step 2: Run test to verify it passes (it should already)**

Run: `pytest tests/test_training_table.py -k deterministic -v`
Expected: PASS. (If it fails, a feature uses a set/dict iteration order or float nondeterminism — fix before proceeding.)

- [ ] **Step 3: Verify CSV byte-stability end to end**

Run:
```bash
python3 scripts/build_training_table.py
cp .planning/extraction/training/role_table.csv /tmp/rt1.csv
python3 scripts/build_training_table.py
diff -q /tmp/rt1.csv .planning/extraction/training/role_table.csv && echo "BYTE-IDENTICAL"
```
Expected: prints `BYTE-IDENTICAL`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_training_table.py
git commit -m "test: determinism guard for training-table builder"
```

---

## Final Verification (Definition of Done)

- [ ] `pytest tests/test_training_table.py tests/test_text_features.py -v` — all green.
- [ ] `python3 scripts/build_training_table.py` runs clean over ~46 structure pages (exit 0), prints histogram + `unresolved_keys`/`noise_atoms` counts + the list of ~20 skipped legacy goldens, no `(UNEXPECTED)` roles.
- [ ] CSV is byte-identical across two runs (`BYTE-IDENTICAL`).
- [ ] Spot-check 3 rows against the viewer: start `PYTHONPATH=src python3 scripts/view_goldens.py --port 8772`, pick a page, find 3 rows in the CSV by `text`, confirm their `role` and `is_bold`/`font_size` match what the page shows.
- [ ] Row count ≈ (annotated items + unmatched atoms) across the corpus — sanity, not exact.
```
