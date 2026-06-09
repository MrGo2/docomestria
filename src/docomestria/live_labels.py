"""Transfer golden annotation roles onto live feature rows by normalized-text +
bbox-overlap (the PRIMARY disambiguator; span_id is not unique). Unmatched live
rows become `noise`, reproducing the golden noise_items policy. Also extracts the
annotated items from a golden page JSON via walk_structure.

Note on spans: golden.training_table.build_page_rows reads the atoms spans from a
SEPARATE atoms document (atoms["atoms"]["spans"]), not from the golden page JSON.
walk_structure currently does not read spans in its body, but to stay faithful to
its signature and to let the caller (Task 6) thread the real atoms doc,
golden_annotated_items accepts an optional `spans`. When omitted it falls back to
golden["atoms"]["spans"] so a self-contained golden page still works.
"""

from __future__ import annotations

from .golden.engine_data import _contains, _norm
from .golden.training_table import _overlap_frac, walk_structure

ANNOTATED_ROLES = frozenset(
    {"key", "value", "section_header", "table_header", "signature", "prose"}
)
_MIN_OVERLAP = 0.30


def golden_annotated_items(golden: dict, spans: list | None = None) -> list[dict]:
    """Annotated (non-noise) items for one golden page, geometry normalised 0-1.

    Returns dicts: {text, role, bbox:{x,y,w,h}|None, page}.
    Keeps bbox=None items (e.g. table_header) so they count in the coverage
    denominator; transfer falls back to text-only matching for them. Skips items
    whose text is not a str (e.g. {"ref": "nota_1"}) — the golden builder drops
    these, and _norm would crash on them.

    `spans` is the atoms spans list (atoms["atoms"]["spans"]). When None it falls
    back to golden["atoms"]["spans"], so a self-contained page works in tests; the
    Task 6 caller passes the real atoms doc spans explicitly.
    """
    pw, ph = golden.get("page_size_pt", (1.0, 1.0))
    pw = pw or 1.0
    ph = ph or 1.0
    if spans is None:
        spans = (golden.get("atoms", {}) or {}).get("spans", [])
    out: list[dict] = []
    for it in walk_structure(golden.get("structure", []), spans):
        if it.role not in ANNOTATED_ROLES:
            continue
        if not isinstance(it.text, str):
            continue
        bb = it.bbox
        norm_bb = (
            {"x": bb["x"] / pw, "y": bb["y"] / ph, "w": bb["w"] / pw, "h": bb["h"] / ph}
            if bb
            else None
        )
        out.append({"text": it.text, "role": it.role, "bbox": norm_bb, "page": golden.get("page")})
    return out


def transfer_labels(rows: list[dict], golden_items: list[dict]) -> tuple[list[dict], dict]:
    """Assign each row a golden role or `noise`. Match policy:
    - golden item WITH bbox -> normalized-text equal AND overlap >= 0.30 (primary).
    - golden item WITHOUT bbox (e.g. table_header) -> normalized-text equal only.

    Returns (labeled_rows, coverage_report). Input rows are not mutated (shallow
    copy; live rows are flat scalar dicts).
    """
    used: set[int] = set()
    labeled: list[dict] = []
    matched_per_role: dict[str, int] = {}
    g_norms = [_norm(g["text"]) for g in golden_items]

    for row in rows:
        new = dict(row)
        r_norm = _norm(row.get("text", ""))
        r_bb = {"x": row["x"], "y": row["y"], "w": row["w"], "h": row["h"]}
        best_idx, best_ov = -1, -1.0
        for gi, g in enumerate(golden_items):
            if gi in used or not _contains(r_norm, g_norms[gi]):
                continue
            if g["bbox"] is None:
                # all bbox=None candidates are geometrically indistinguishable
                # (ov=0.0); first text match wins
                ov = 0.0
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

    total_by_role: dict[str, int] = {}
    for g in golden_items:
        total_by_role[g["role"]] = total_by_role.get(g["role"], 0) + 1
    per_role = {}
    for role, total in total_by_role.items():
        m = matched_per_role.get(role, 0)
        per_role[role] = {
            "matched": m,
            "total": total,
            "pct": (100.0 * m / total) if total else 0.0,
        }
    total = sum(total_by_role.values())
    matched = sum(matched_per_role.values())
    cov = {
        "matched": matched,
        "total": total,
        "overall_pct": (100.0 * matched / total) if total else 0.0,
        "per_role": per_role,
    }
    return labeled, cov
