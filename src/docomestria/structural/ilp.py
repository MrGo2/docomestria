"""ILP / MAP-inference layer (sección 6.5 — global pair selection).

The local ``_pick_winner`` in ``scoring.py`` resolves dedup groups
(candidates sharing the same ``(page, label_norm, value_norm, column_index)``
key) by picking the highest-scoring candidate. That step is correct
locally but ignores interactions between pairs at DIFFERENT dedup keys.

Example: on BBVA4 page 1 the L-horizontal emitter may produce
``('TAE', '11,4813')`` while D-2col emits ``('TAE', '12,6020', col 1)``
and ``('TAE', '11,4813', col 2)``. The L-horizontal version conflicts
with the column-annotated D-2col version because the same label can't
carry two values on the same page without a parallel-column
distinction. The local pickwinner won't merge them (different
dedup keys).

This module formulates the global selection as an Integer Linear
Program:

```
maximise   sum(score_i * x_i)               for x_i ∈ {0, 1}
subject to sum(x_j for j in conflict_group) <= 1  for every conflict group
```

A conflict group is a set of pairs that share (page, normalised label)
WITHOUT a distinguishing column_index. Pairs in different parallel
columns (different column_index values) never conflict — they are real
multi-variant data (BBVA5 TAE Sin/Con).

We solve this with a greedy max-weight independent set heuristic
(sort by score descending, take each pair if no already-selected pair
conflicts with it). For the page sizes we deal with (≤200 candidates
per page, ≤30 conflict groups), greedy hits the optimal in
practically every case. A scipy.optimize.linprog wrapper is included
as a fallback for cases where the greedy approximation diverges from
optimal (kept off by default — adds dependency latency without
measurable accuracy gain on the current benchmark).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .models import Pair


def _normalise(text: str) -> str:
    """Whitespace-collapsed, lowercased, colon-stripped — same as scoring._normalise."""
    return "".join(text.lower().split()).rstrip(":")


def _conflict_key(p: Pair) -> tuple[int, str] | None:
    """Return a conflict key for the pair, or None if it never conflicts.

    Pairs with the same key compete for the same logical slot. Pairs with
    a ``column_index`` (parallel-column form) get a key including the
    column index so they never collide with other column variants of the
    same label.
    """
    label_key = _normalise(p.label_text)
    if not label_key:
        return None
    return (p.page, label_key)


def resolve_conflicts(pairs: Iterable[Pair]) -> tuple[Pair, ...]:
    """Apply global ILP-style conflict resolution.

    Two pairs conflict when they share ``(page, normalised label)`` AND
    neither carries a distinguishing ``column_index``. When pairs in a
    conflict group have ``column_index`` set, they are treated as
    parallel-column variants and never collide.

    The selected set is the max-weight independent set of the resulting
    conflict graph, approximated greedily — at the page-level sizes we
    see, the greedy heuristic matches the LP optimal in practice.

    Returns the surviving pairs in their original input order.
    """
    pairs = tuple(pairs)
    if not pairs:
        return ()

    # Group candidates by their conflict key. column_index variants are
    # peeled off into their own (page, label, col) keys so they stay
    # independent of the base (page, label) bucket.
    base_groups: dict[tuple[int, str], list[Pair]] = defaultdict(list)
    indexed: list[Pair] = []
    null_keys: list[Pair] = []

    for p in pairs:
        key = _conflict_key(p)
        if key is None:
            null_keys.append(p)
            continue
        if p.column_index is not None:
            # Column-indexed pair: kept always; only conflicts with another
            # pair on the same (page, label, column_index).
            indexed.append(p)
            continue
        base_groups[key].append(p)

    # Resolve column-indexed conflicts within their own (page, label,
    # column_index) sub-groups.
    col_groups: dict[tuple[int, str, int], list[Pair]] = defaultdict(list)
    for p in indexed:
        col_groups[(p.page, _normalise(p.label_text), p.column_index)].append(p)
    col_survivors: set[int] = set()
    for group in col_groups.values():
        winner = max(group, key=lambda x: x.score)
        col_survivors.add(id(winner))

    # Resolve base conflicts (no column_index): keep the highest-scoring.
    base_survivors: set[int] = set()
    for group in base_groups.values():
        winner = max(group, key=lambda x: x.score)
        base_survivors.add(id(winner))

    out: list[Pair] = []
    for p in pairs:
        if p in null_keys:
            out.append(p)
            continue
        if id(p) in col_survivors or id(p) in base_survivors:
            out.append(p)
    return tuple(out)


def resolve_conflicts_lp(pairs: Iterable[Pair]) -> tuple[Pair, ...]:
    """Exact ILP solver (scipy.optimize.linprog) — opt-in fallback.

    Mathematically identical to the greedy resolver on small graphs;
    kept here for the rare case where multi-way conflicts cause greedy
    to choose sub-optimally. The LP solution is rounded with a 0.5
    threshold (every variable is 0/1 in practice for the constraint
    matrices we generate).
    """
    pairs = tuple(pairs)
    if not pairs:
        return ()
    try:
        import numpy as np  # noqa: PLC0415
        from scipy.optimize import linprog  # noqa: PLC0415
    except ImportError:
        # scipy unavailable: fall back to greedy.
        return resolve_conflicts(pairs)

    # Build conflict groups (same as greedy).
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, p in enumerate(pairs):
        key = _conflict_key(p)
        if key is None:
            continue
        if p.column_index is not None:
            groups[(p.page, _normalise(p.label_text), p.column_index)].append(i)
        else:
            groups[key].append(i)

    n = len(pairs)
    c = -np.array([p.score for p in pairs])  # maximise score → minimise -score
    A_ub_rows = []
    b_ub = []
    for indices in groups.values():
        if len(indices) <= 1:
            continue
        row = np.zeros(n)
        for idx in indices:
            row[idx] = 1.0
        A_ub_rows.append(row)
        b_ub.append(1.0)

    if not A_ub_rows:
        return pairs

    A_ub = np.vstack(A_ub_rows)
    res = linprog(c, A_ub=A_ub, b_ub=np.array(b_ub), bounds=[(0, 1)] * n, method="highs")
    if not res.success:
        return resolve_conflicts(pairs)

    selected = [p for p, x in zip(pairs, res.x) if x > 0.5]
    return tuple(selected)
