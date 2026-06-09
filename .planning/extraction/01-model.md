# The mathematical model

This document specifies the data model, feature functions, scoring
templates, refinement step, pair score, ILP formulation, a worked
example, and the weight-calibration plan. The framing (CRF + ILP) is
covered in [`00-approach.md`](./00-approach.md).

## A.3 The data model — nodes, features, edges

The atomic unit is a **LiteParse span**. A page becomes a graph whose
nodes are spans and whose edges are pairwise relationships between
spans. Both nodes and edges carry feature vectors.

### Per-node feature vector

For each span we compute the following features.

**Geometric**

| Feature | Type | Description |
|---|---|---|
| `x` | float (pt) | left edge of bbox |
| `y` | float (pt) | top edge of bbox |
| `w` | float (pt) | width |
| `h` | float (pt) | height |
| `rel_x` | float ∈ [0, 1] | `x / page_width` |
| `rel_y` | float ∈ [0, 1] | `y / page_height` |
| `rel_size` | float | `font_size / page_median_font_size` |

**Typographic**

| Feature | Type | Description |
|---|---|---|
| `is_bold` | bool | derived from font name |
| `is_italic` | bool | derived from font name |
| `size_pt` | float | raw font size in points |
| `font_rank` | int (0..) | 0 = most common font on page |

**Content**

| Feature | Type | Description |
|---|---|---|
| `case_upper` | float ∈ [0, 1] | fraction of UPPER letters |
| `case_lower` | float ∈ [0, 1] | fraction of lower letters |
| `case_title` | float ∈ [0, 1] | fraction of Title-cased tokens |
| `digit_ratio` | float ∈ [0, 1] | `n_digits / n_chars` |
| `len_chars` | int | character count |
| `starts_paren` | bool | text begins with `(` |
| `ends_colon` | bool | text ends with `:` |
| `has_currency` | bool | matches `€`, `EUR`, `euros`, … |
| `has_date` | bool | matches a date regex |
| `has_percent` | bool | matches `%` |
| `has_iban` | bool | matches IBAN regex |
| `has_nif` | bool | matches Spanish NIF regex |

**Context**

| Feature | Type | Description |
|---|---|---|
| `in_rect_id` | int \| null | id of the smallest enclosing `pdfplumber` rect |
| `rect_depth` | int | 0 = outer, 1 = nested, 2 = leaf |
| `docling_label` | str \| null | `text`, `section_header`, `field_key`, `field_value`, … |
| `docling_level` | int \| null | heading level (1 = h1, 2 = h2, 3 = h3) |
| `docling_layer` | str | `body` \| `furniture` |
| `docling_col_span` | int | from `TableCell.col_span` |
| `docling_row_span` | int | from `TableCell.row_span` |
| `docling_column_header` | bool | from `TableCell.column_header` |
| `docling_row_header` | bool | from `TableCell.row_header` |

### Per-edge weight functions

For every pair of spans `(A, B)` (`A` left of or above `B`) we compute
the following edge weights.

```python
same_row(A, B)        = exp(-abs(A.y_center - B.y_center) / 4.0)
adjacent_x(A, B)      = exp(-gap / 40.0) if B is right of A else 0
same_column(A, B)     = exp(-abs(A.x - B.x) / 4.0)
case_contrast(A, B)   = 1 if A.case == 'lower' and B.case in {'UPPER', 'none'} else 0
shared_container(A,B) = 1 if A.in_rect_id == B.in_rect_id else 0
shared_section(A, B)  = 1 if same section else -5  # the penalty is intentional
paragraph_break(A, B) = -3 if a long body-text span lies between them else 0
```

These are the only edge features used in §A.6. They are chosen so that
the score is a soft monotonic function of geometric/typographic
proximity, with hard penalties for crossing logical boundaries
(sections, paragraphs).

## A.4 Role classification as weighted templates

Each span is assigned exactly one **role** by `argmax` over a small set
of weighted templates. The roles are
`{LABEL, VALUE_NUMERIC, VALUE_TEXT, HEADER, SUB_HEADER, CLARIFIER,
EMPTY}`.

The following weights are **starting values** for manual calibration.
See §A.9 for how to refine them.

```text
LABEL:
  is_bold                +2.0
  case_lower             +1.5
  digit_ratio            -2.0
  ends_colon             +1.0
  rect_depth             +0.5
  docling_field_key      +5.0

VALUE_NUMERIC:
  digit_ratio            +3.0
  case_none              +1.5
  is_bold                -1.0
  starts_paren           -2.0
  docling_field_value    +5.0

VALUE_TEXT:
  case_upper             +2.0
  is_bold                -0.5
  digit_ratio            -1.0

HEADER:
  is_bold                +1.5
  case_upper             +2.0
  rel_size               +2.0
  len_chars_short        +0.5
  docling_section_header +5.0

SUB_HEADER:
  is_bold                +1.5
  case_lower             +1.0
  inside_parent_rect     +1.0

CLARIFIER:
  starts_paren           +3.0
  case_lower             +1.0
  follows_label_y        +1.5

EMPTY:
  n_spans_zero           +5.0
```

**Assignment rule.**

    role(span) = argmax_r [ score_r(span) ]

**Confidence.**

    confidence(span) = (top_score - second_top) / top_score

Confidence below a threshold (`< 0.15`) triggers downstream review
flags and inhibits ILP commitment to that span as a label or value.

## A.5 Column coherence as message-passing refinement

After local role assignment, spans are grouped by **x-band** (a column
in the visual grid). Within each band the dominant role propagates as
follows.

- For each x-band, compute the role distribution of its cells.
- If **≥80 %** of cells in the band share a single role `r*`, mark `r*`
  as the band's dominant role.
- The dominant role's score on the remaining cells of the band is
  boosted by **+1.5** for that role.
- Iterate **once** — a single pass is empirically sufficient.

This is a simple, bounded message-passing step that resolves the
column-coherence failure modes documented in
[`04-cases.md` case 8](./04-cases.md#case-8-per-cell-profile--column-coherence).

## A.6 Pair scoring

For each candidate `(L, V)` pair the joint score is

```python
score(L, V) = (
    2.0 * same_row(L, V)
  + 1.5 * adjacent_x(L, V)
  + 1.0 * case_contrast(L, V)
  + 2.0 * shared_container(L, V)
  + 3.0 * column_role_compatible(L, V)
  + 4.0 * docling_field_pair(L, V)
  + 1.5 * labels_value_in_same_band(L, V)
  - 5.0 * different_section(L, V)
  - 3.0 * paragraph_break_between(L, V)
)
```

where

- `column_role_compatible(L, V) = 1` if `L` sits in a LABEL-coherent
  column and `V` sits in a VALUE-coherent column (see §A.5);
- `docling_field_pair(L, V) = 1` if Docling labels `L` as `field_key`
  and `V` as `field_value` in the same `key_value_region`;
- `labels_value_in_same_band(L, V) = 1` if both spans fall within the
  same y-band of a multi-column row.

## A.7 ILP joint resolution

Local pair scores are not enough — a span may be a plausible value for
several labels. We resolve the global assignment with an integer linear
program à la Roth & Yih (2004).

**Variables.**

    x[i, j] ∈ {0, 1}    — 1 iff we emit the pair (span_i, span_j)

**Objective.**

    maximize  Σ_{i, j}  score(i, j) · x[i, j]

**Constraints.**

```text
Σ_j  x[i, j]  ≤ 1     ∀i     # span i appears in at most one pair as a label
Σ_i  x[i, j]  ≤ 1     ∀j     # span j appears in at most one pair as a value
no bbox overlap between any two emitted pairs (i, j) and (k, l)
x[i, j] = 0  if role(span_i) ≠ LABEL
            or role(span_j) ∉ {VALUE_NUMERIC, VALUE_TEXT, CLARIFIER}
```

**Solver.** `pulp` with the CBC backend (or `scipy.optimize.linprog`
with deterministic rounding for small instances). The page-level
problem has tens to low hundreds of variables and solves in
milliseconds.

This formulation is exactly the joint-inference-via-ILP scheme of Roth
& Yih (2004); see [`00-approach.md`](./00-approach.md#foundational-references).

## A.8 Worked example — BBVA_0608 page 3, row 9

The row "Interés Nominal Anual" carries two values in a 3-column band:
`11,2000 %` under the header "Sin nómina" and `10,2000 %` under "Con
nómina". The expected output is **two** pairs (one per column).

### Inputs

| Span | Text | x | y | size | bold | case |
|---|---|---|---|---|---|---|
| `L`  | `Interés Nominal Anual` | 180 | 415 | 10 | true  | lower |
| `V1` | `11,2000 %`             | 355 | 415 | 10 | false | none  |
| `V2` | `10,2000 %`             | 455 | 415 | 10 | false | none  |

Column coherence (from §A.5):
- column at x ≈ 180 is LABEL-coherent;
- columns at x ≈ 355 and x ≈ 455 are both VALUE_NUMERIC-coherent.

### Role scores

```text
L:  LABEL          score = +2.0 (bold) + 1.5 (lower) + 1.0 (ends_colon=no, drop)
                       + 0.5 (rect_depth)      = +4.0     (top)
    VALUE_NUMERIC      = -1.0 (bold)
                       - 2.0 (digit_ratio=0)   = -3.0
    → role(L) = LABEL, confidence ≈ 1.0

V1: VALUE_NUMERIC  score = +3.0 (digit_ratio≈0.7)
                       + 1.5 (case_none)       = +4.5     (top)
    LABEL              = -2.0 (digit_ratio)    = -2.0
    → role(V1) = VALUE_NUMERIC, confidence ≈ 1.0

V2: identical to V1   → role(V2) = VALUE_NUMERIC
```

### Pair scores

For `(L, V1)`:

```text
same_row(L, V1)     = exp(0 / 4)            = 1.0
adjacent_x(L, V1)   = exp(-(355-180-w_L)/40)  ≈ 0.25
case_contrast       = 1   (lower → none)
shared_container    = 1   (same row rect)
column_role_compat  = 1   (LABEL col → VALUE col)
docling_field_pair  = 0   (no Docling field tag here)
labels_value_band   = 1   (same band B of page 3)
different_section   = 0   (same section)
paragraph_break     = 0

score(L, V1) = 2.0·1.0 + 1.5·0.25 + 1.0·1 + 2.0·1 + 3.0·1 + 4.0·0
             + 1.5·1 - 5.0·0 - 3.0·0
             = 2.0 + 0.375 + 1.0 + 2.0 + 3.0 + 1.5
             = 9.875
```

For `(L, V2)`: same except `adjacent_x` is smaller (further away).

```text
adjacent_x(L, V2)   = exp(-(455-180-w_L)/40)  ≈ 0.10

score(L, V2) = 2.0 + 0.150 + 1.0 + 2.0 + 3.0 + 1.5
             = 9.650
```

### ILP outcome

The constraints in §A.7 allow **one label to many values when each
value sits in a distinct column band**. Both `(L, V1)` and `(L, V2)`
are emitted, each tagged with its `column_index` (0 for "Sin nómina",
1 for "Con nómina"). No bbox overlap occurs because V1 and V2 are
geometrically disjoint.

Final output:

```json
[
  {"label": "Interés Nominal Anual", "value": "11,2000 %", "column_header": "Sin nómina", "score": 9.875},
  {"label": "Interés Nominal Anual", "value": "10,2000 %", "column_header": "Con nómina", "score": 9.650}
]
```

## A.9 Calibration of weights

Three calibration modes are available, in order of increasing
sophistication.

### 1. Manual

Start with the weights in §A.4 and §A.6. Walk a small set (≈10
examples) through the system and adjust by eye when the wrong role or
the wrong pair wins. Fast, but does not generalise.

### 2. Grid search

With ~30 labelled KV pairs as ground truth, run a coarse grid over
weight combinations and pick the configuration that maximises F1. This
is the recommended first step once any ground truth exists.

### 3. Logistic regression

Train logistic-regression coefficients on the per-span and per-pair
feature vectors of the labelled data. The result remains a log-linear
model — weights are interpretable — but they are now learned from
data. This is the bridge between manual heuristics and full machine
learning.

**Rule of thumb.** Avoid full deep learning until **≥200 labelled
pairs** are available. Below that volume, the logistic-regression-on-
heuristic-features path consistently outperforms small neural models
and is auditable.

## A.10 Future hybrid

LayoutLM-style transformer embeddings can be appended to the per-span
feature vector as extra dimensions without changing the role-template
formulation, the column coherence step, the pair score, or the ILP
constraints. See [`00-approach.md` §"Future hybrid"](./00-approach.md#future-hybrid-layoutlm-embeddings-as-features).
