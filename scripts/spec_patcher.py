"""spec_patcher — deterministic patcher that applies findings.json to a spec.py.

Reads findings.json (from golden-reviewer) and applies mechanical patches to a
docomestria golden spec module. Pure stdlib (ast, json, re, argparse).

Operations supported in findings[].proposed_fix.op:
    update_y_hint           — change y_hint of a target kv pair / leaf / row
    update_x_hint           — set x_hint on the value side of a target
    fix_value_bbox          — translated to update_x_hint (using params.new_value_bbox.x)
    fix_label_and_value_bbox— translated to update_x_hint (+update_y_hint if .y changes)
    add_kv                  — insert new kv pair into a target section/kv_group
    fix_value               — change value text of a target pair
    delete                  — remove a target node
    move                    — move target node from one parent to another (by id)
    mark_noise              — append a noise node at the end of STRUCTURE

Target resolution (proposed_fix.target):
    "<spec_node_id>"                       — node with this id (kv_group / section / kv_leaf)
    "kv label='X' row_y=Y"                 — pair with label X at row_y Y (anywhere in STRUCTURE)
    "kv label='X'"                         — first pair with label X
    "row label='X' row_y=Y"                — table row whose label col text is X at y=Y

Strategy:
    Most specs use helper functions like `_block_pairs(...)` so the kv pairs do
    not appear as literal dicts at the call site. We solve this by injecting a
    small `_apply_overrides(pairs, overrides)` helper and wrapping helper calls
    with it. Overrides are applied at runtime (build time) to set y_hint / x_hint
    on specific labels.

    For specs where pairs are literal dicts in STRUCTURE, we edit the dict
    literal directly using line-based regex (preserves comments / formatting).

CLI:
    python3 scripts/spec_patcher.py --spec scripts/specs/foo_p02.py \\
        --findings .planning/extraction/reviews/foo-p02.findings.json \\
        [--out scripts/specs/foo_p02.py] [--dry-run]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path


# ----- finding normalisation -------------------------------------------------

def _translate_finding(f: dict) -> dict:
    """Translate fix_value_bbox / fix_label_and_value_bbox to x_hint patches.

    The reviewer often returns bbox-recompute patches that the patcher cannot
    apply literally (bboxes are computed by the builder). Translate them to
    x_hint hints which the (now extended) cell_linker uses to pick the right
    column at build time.
    """
    op = f.get("proposed_fix", {}).get("op")
    params = f.get("proposed_fix", {}).get("params", {})
    if op == "fix_value_bbox":
        nb = params.get("new_value_bbox") or {}
        if "x" in nb:
            f["proposed_fix"]["op"] = "update_x_hint"
            # NOTE: we don't propagate bbox.y → y_hint here because the bbox
            # baseline is typically the original row_y ± a few pt; the existing
            # y_hint is what locates the row and is already correct. Use the
            # explicit `update_y_hint` op if a real y change is needed.
            f["proposed_fix"]["params"] = {"x_hint": float(nb["x"])}
    elif op == "fix_label_and_value_bbox":
        nv = params.get("new_value_bbox") or {}
        nl = params.get("new_label_bbox") or {}
        new_params = {}
        if "x" in nv:
            new_params["x_hint"] = float(nv["x"])
        if "x" in nl:
            new_params["label_x_hint"] = float(nl["x"])
        f["proposed_fix"]["op"] = "update_x_hint"
        f["proposed_fix"]["params"] = new_params
    return f


# ----- target parsing --------------------------------------------------------

_RE_KV_TARGET = re.compile(r"kv\s+label=['\"]([^'\"]+)['\"](?:\s+row_y=(\d+))?")
_RE_ROW_TARGET = re.compile(r"row\s+label=['\"]([^'\"]+)['\"](?:\s+row_y=(\d+))?")


def _parse_target(target: str) -> dict:
    """Parse a target string into a structured locator."""
    t = target.strip()
    m = _RE_KV_TARGET.match(t)
    if m:
        return {"kind": "kv_pair", "label": m.group(1),
                "row_y": int(m.group(2)) if m.group(2) else None}
    m = _RE_ROW_TARGET.match(t)
    if m:
        return {"kind": "table_row", "label": m.group(1),
                "row_y": int(m.group(2)) if m.group(2) else None}
    # Default: assume it's a node id
    return {"kind": "id", "id": t}


# ----- spec source rewriting -------------------------------------------------

_OVERRIDES_VAR = "_PATCH_OVERRIDES"

_HELPER_SRC = '''
def _apply_overrides(pairs, overrides):
    """Patcher-injected helper: mutates pair dicts in place based on label match.

    overrides: dict mapping label -> dict of fields to set/override.
    """
    if not overrides:
        return pairs
    out = []
    for p in pairs:
        lbl = p.get("label")
        if lbl in overrides:
            merged = dict(p)
            merged.update(overrides[lbl])
            out.append(merged)
        else:
            out.append(p)
    return out
'''.lstrip()


def _ensure_helper_injected(src: str) -> str:
    """Ensure _apply_overrides is defined in the spec source. Idempotent.

    Insertion point: after module docstring, imports, and the standard
    PDF/PAGE/META assignment block; before STRUCTURE and any helper defs.
    """
    if "_apply_overrides" in src:
        return src
    tree = ast.parse(src)
    insert_lineno = 1
    for node in tree.body:
        # Module docstring
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            insert_lineno = node.end_lineno + 1
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            insert_lineno = node.end_lineno + 1
            continue
        if isinstance(node, ast.Assign):
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id in ("PDF", "PAGE", "META"):
                insert_lineno = node.end_lineno + 1
                continue
        # Stop at first def / unrecognised node — helper goes right before it.
        break
    lines = src.split("\n")
    new_lines = lines[:insert_lineno] + ["", _HELPER_SRC] + lines[insert_lineno:]
    return "\n".join(new_lines)


# ----- AST-based locator -----------------------------------------------------

class SpecModel:
    """Wraps a spec source: AST + flat index of nodes (by id, by kv label)."""

    def __init__(self, src: str, path: Path):
        self.src = src
        self.path = path
        self.tree = ast.parse(src)
        self.structure_node = self._find_structure()
        self._build_index()

    def _find_structure(self) -> ast.Assign:
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                tgt = node.targets[0]
                if isinstance(tgt, ast.Name) and tgt.id == "STRUCTURE":
                    return node
        raise ValueError("No STRUCTURE = [...] assignment found in spec")

    def _build_index(self):
        # Map kv_group node (by id) → AST node holding the 'pairs' value
        self.kv_group_pairs_value: dict[str, ast.AST] = {}
        # Map kv_leaf node (by id) → ast.Dict containing the kv_leaf literal
        self.kv_leaf_dicts: dict[str, ast.Dict] = {}
        # Map section node (by id) → ast.Dict of section + children list
        self.section_dicts: dict[str, ast.Dict] = {}

        def walk(node: ast.AST):
            if isinstance(node, ast.Dict):
                node_type = _get_str_key(node, "type")
                node_id = _get_str_key(node, "id")
                if node_type == "section" and node_id:
                    self.section_dicts[node_id] = node
                elif node_type == "kv_leaf" and node_id:
                    self.kv_leaf_dicts[node_id] = node
                elif node_type == "kv_group" and node_id:
                    pairs_value = _get_value_for_key(node, "pairs")
                    if pairs_value is not None:
                        self.kv_group_pairs_value[node_id] = pairs_value
            for child in ast.iter_child_nodes(node):
                walk(child)

        walk(self.structure_node)


def _get_str_key(d: ast.Dict, key: str) -> str | None:
    for k, v in zip(d.keys, d.values):
        if isinstance(k, ast.Constant) and k.value == key:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                return v.value
    return None


def _get_value_for_key(d: ast.Dict, key: str) -> ast.AST | None:
    for k, v in zip(d.keys, d.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return v
    return None


# ----- runtime spec execution to locate kv pairs at runtime ------------------

def _exec_spec(src: str, spec_path: Path) -> dict:
    """Execute the spec source and return its module namespace."""
    ns: dict = {"__file__": str(spec_path), "__name__": "spec_to_patch"}
    code = compile(src, str(spec_path), "exec")
    exec(code, ns)
    return ns


def _runtime_kv_groups_for_label(structure, label: str, row_y: int | None):
    """Yield (kv_group_id, pair_dict) for runtime structure matching label/row_y."""
    def walk(nodes):
        for n in nodes or []:
            if not isinstance(n, dict):
                continue
            t = n.get("type")
            if t == "kv_group":
                for p in n.get("pairs", []) or []:
                    if p.get("label") == label:
                        if row_y is None or abs(int(p.get("y_hint") or 0) - row_y) <= 5:
                            yield n.get("id"), p
            yield from walk(n.get("children", []))
    yield from walk(structure)


# ----- patch application -----------------------------------------------------

class PatchApplier:
    def __init__(self, spec_path: Path):
        self.spec_path = spec_path
        self.src = spec_path.read_text(encoding="utf-8")
        # Track per-kv_group overrides: {kv_group_id: {label: {field: value}}}
        self.kv_group_overrides: dict[str, dict[str, dict]] = {}
        self.applied: list[str] = []
        self.skipped: list[str] = []

    def apply(self, finding: dict) -> bool:
        fid = finding.get("id", "?")
        fix = finding.get("proposed_fix") or {}
        op = fix.get("op")
        target = fix.get("target") or ""
        params = fix.get("params") or {}
        loc = _parse_target(target)

        if op in ("update_x_hint", "update_y_hint"):
            return self._apply_hint_update(fid, op, loc, params)
        if op == "fix_value":
            return self._apply_fix_value(fid, loc, params)
        if op == "delete":
            return self._apply_delete(fid, loc)
        if op == "mark_noise":
            return self._apply_mark_noise(fid, params)
        if op == "add_kv":
            return self._apply_add_kv(fid, loc, params)
        if op == "move":
            return self._apply_move(fid, loc, params)
        self.skipped.append(f"[{fid}] unsupported op: {op}")
        return False

    # --- handler: hint updates (most common, via _apply_overrides injection) -
    def _apply_hint_update(self, fid: str, op: str, loc: dict, params: dict) -> bool:
        if loc["kind"] != "kv_pair":
            self.skipped.append(f"[{fid}] {op} requires kv-pair target, got {loc['kind']}")
            return False
        label = loc["label"]
        row_y = loc.get("row_y")
        # Locate the kv_group at runtime by walking executed STRUCTURE
        try:
            ns = _exec_spec(self.src, self.spec_path)
        except Exception as e:
            self.skipped.append(f"[{fid}] spec failed to execute: {e}")
            return False
        matches = list(_runtime_kv_groups_for_label(ns.get("STRUCTURE", []),
                                                    label, row_y))
        if not matches:
            self.skipped.append(f"[{fid}] no kv pair matches label={label!r} row_y={row_y}")
            return False
        if len(matches) > 1 and row_y is None:
            self.skipped.append(
                f"[{fid}] ambiguous: {len(matches)} pairs match label={label!r}, need row_y")
            return False
        kv_group_id, pair = matches[0]
        # Collect overrides
        override: dict = {}
        if "x_hint" in params:
            override["x_hint"] = float(params["x_hint"])
        if "label_x_hint" in params:
            override["label_x_hint"] = float(params["label_x_hint"])
        if "y_hint" in params and op == "update_y_hint":
            override["y_hint"] = int(params["y_hint"])
        elif "y_hint" in params:
            # update_x_hint may also carry y_hint when bbox moved on the y axis
            override["y_hint"] = int(params["y_hint"])
        if not override:
            self.skipped.append(f"[{fid}] no recognised hint params: {params}")
            return False
        self.kv_group_overrides.setdefault(kv_group_id, {}).setdefault(label, {}).update(override)
        change_desc = "+".join(f"{k}={v}" for k, v in override.items())
        self.applied.append(f"[{fid}] {op}: pairs[{label}] {change_desc}")
        return True

    # --- handler: fix_value (rewrite pair value or kv_leaf value literal) ---
    def _apply_fix_value(self, fid: str, loc: dict, params: dict) -> bool:
        new_value = params.get("value") or params.get("new_value")
        if new_value is None:
            self.skipped.append(f"[{fid}] fix_value missing 'value' param")
            return False
        if loc["kind"] != "kv_pair":
            self.skipped.append(f"[{fid}] fix_value supports kv-pair target only")
            return False
        label = loc["label"]
        row_y = loc.get("row_y")
        try:
            ns = _exec_spec(self.src, self.spec_path)
        except Exception as e:
            self.skipped.append(f"[{fid}] spec failed to execute: {e}")
            return False
        matches = list(_runtime_kv_groups_for_label(ns.get("STRUCTURE", []),
                                                    label, row_y))
        if not matches:
            self.skipped.append(f"[{fid}] no kv pair matches label={label!r}")
            return False
        kv_group_id, _ = matches[0]
        self.kv_group_overrides.setdefault(kv_group_id, {}).setdefault(label, {})[
            "value"] = str(new_value)
        self.applied.append(f"[{fid}] fix_value: pairs[{label}] value={new_value!r}")
        return True

    def _apply_delete(self, fid: str, loc: dict) -> bool:
        # Mark for deletion via override sentinel (None value + _delete flag)
        if loc["kind"] != "kv_pair":
            self.skipped.append(f"[{fid}] delete supports kv-pair target only")
            return False
        label = loc["label"]
        row_y = loc.get("row_y")
        try:
            ns = _exec_spec(self.src, self.spec_path)
        except Exception as e:
            self.skipped.append(f"[{fid}] spec failed to execute: {e}")
            return False
        matches = list(_runtime_kv_groups_for_label(ns.get("STRUCTURE", []),
                                                    label, row_y))
        if not matches:
            self.skipped.append(f"[{fid}] no kv pair matches label={label!r}")
            return False
        kv_group_id, _ = matches[0]
        self.kv_group_overrides.setdefault(kv_group_id, {}).setdefault(label, {})[
            "_delete"] = True
        self.applied.append(f"[{fid}] delete: pairs[{label}]")
        return True

    def _apply_mark_noise(self, fid: str, params: dict) -> bool:
        text = params.get("text")
        kind = params.get("kind", "noise")
        y_hint = params.get("y_hint")
        if not text:
            self.skipped.append(f"[{fid}] mark_noise needs 'text' param")
            return False
        # Append a noise node literal at the end of STRUCTURE
        new_node = (
            "    {\n"
            f'        "type": "noise",\n'
            f'        "text": {json.dumps(text, ensure_ascii=False)},\n'
            f'        "kind": {json.dumps(kind)},\n'
            + (f'        "y_hint": {int(y_hint)},\n' if y_hint else "")
            + "    },\n"
        )
        self._pending_structure_appends.append(new_node)
        self.applied.append(f"[{fid}] mark_noise: text={text!r}")
        return True

    def _apply_add_kv(self, fid: str, loc: dict, params: dict) -> bool:
        self.skipped.append(f"[{fid}] add_kv not yet supported (needs target kv_group id)")
        return False

    def _apply_move(self, fid: str, loc: dict, params: dict) -> bool:
        self.skipped.append(f"[{fid}] move not yet supported")
        return False

    # --- finalisation: write overrides + helper into source -----------------
    def __init_pending(self):
        if not hasattr(self, "_pending_structure_appends"):
            self._pending_structure_appends = []

    def render(self) -> str:
        """Apply collected overrides + helper to source, return new source."""
        self.__init_pending()
        new_src = self.src
        if not self.kv_group_overrides and not self._pending_structure_appends:
            return new_src

        if self.kv_group_overrides:
            new_src = _ensure_helper_injected(new_src)
            for kv_group_id, overrides in self.kv_group_overrides.items():
                new_src = self._inject_overrides_for_group(
                    new_src, kv_group_id, overrides)

        # Apply mark_noise appends (insert before closing `]` of STRUCTURE)
        for noise_literal in self._pending_structure_appends:
            new_src = self._append_to_structure(new_src, noise_literal)

        return new_src

    def _inject_overrides_for_group(self, src: str, kv_group_id: str,
                                     overrides: dict) -> str:
        """Modify the kv_group dict literal so its `pairs:` value is wrapped
        with _apply_overrides(orig_value, {label: {...}, ...}).

        We rewrite the file textually: find the `"id": "<group_id>"` line, then
        find the `"pairs":` key and wrap its value expression.
        """
        # Parse to find exact line/col of the pairs value in this group
        tree = ast.parse(src)
        target_value_node = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            if _get_str_key(node, "id") != kv_group_id:
                continue
            if _get_str_key(node, "type") != "kv_group":
                continue
            target_value_node = _get_value_for_key(node, "pairs")
            break
        if target_value_node is None:
            self.skipped.append(
                f"could not locate kv_group id={kv_group_id!r} pairs in source")
            return src

        # Extract exact source segment for the pairs value, replace with wrapped
        orig_segment = ast.get_source_segment(src, target_value_node)
        if orig_segment is None:
            self.skipped.append(
                f"could not extract source segment for kv_group {kv_group_id}")
            return src
        overrides_repr = _format_overrides_dict(overrides)
        # Handle the _delete flag: that gets dropped from per-label dict but
        # signals we want to remove the pair. We rely on _apply_overrides to
        # propagate the marker; deletion happens post-wrap with a filter:
        if any(v.get("_delete") for v in overrides.values()):
            wrapped = (
                "[p for p in _apply_overrides(" + orig_segment + ", "
                + overrides_repr
                + ') if not p.get("_delete")]'
            )
        else:
            wrapped = "_apply_overrides(" + orig_segment + ", " + overrides_repr + ")"
        # Replace in source — orig_segment is unique enough (pairs values are
        # unique per call due to y_base differences in our pattern).
        if src.count(orig_segment) != 1:
            self.skipped.append(
                f"non-unique pairs segment for {kv_group_id}, refusing to patch")
            return src
        return src.replace(orig_segment, wrapped, 1)

    def _append_to_structure(self, src: str, literal: str) -> str:
        """Insert a literal node just before the closing ] of STRUCTURE list."""
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == "STRUCTURE":
                    end_line = node.end_lineno  # the line with `]`
                    lines = src.split("\n")
                    lines.insert(end_line - 1, literal.rstrip())
                    return "\n".join(lines)
        return src


def _format_overrides_dict(overrides: dict) -> str:
    """Render overrides dict as Python source. Drop _delete (filtered separately)."""
    parts = []
    for label, fields in overrides.items():
        clean = {k: v for k, v in fields.items() if k != "_delete"}
        if not clean and fields.get("_delete"):
            # represent as marker
            inner = '"_delete": True'
        else:
            inner = ", ".join(
                f'"{k}": {json.dumps(v, ensure_ascii=False) if isinstance(v, str) else v}'
                for k, v in clean.items()
            )
        parts.append(f'    {json.dumps(label, ensure_ascii=False)}: {{{inner}}}')
    return "{\n" + ",\n".join(parts) + ",\n}"


# ----- CLI -------------------------------------------------------------------

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="Path to spec .py file")
    ap.add_argument("--findings", required=True, help="Path to findings.json")
    ap.add_argument("--out", default=None,
                    help="Path to write patched spec (default: overwrite --spec)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print planned changes without writing")
    args = ap.parse_args(argv)

    spec_path = Path(args.spec)
    findings_path = Path(args.findings)
    out_path = Path(args.out) if args.out else spec_path

    if not spec_path.exists():
        print(f"ERROR: spec not found: {spec_path}", file=sys.stderr)
        return 1
    if not findings_path.exists():
        print(f"ERROR: findings not found: {findings_path}", file=sys.stderr)
        return 1

    findings_doc = json.loads(findings_path.read_text(encoding="utf-8"))
    verdict = findings_doc.get("summary", {}).get("verdict")
    if verdict == "NEEDS_HUMAN":
        print(f"ERROR: findings verdict is NEEDS_HUMAN — refusing to patch",
              file=sys.stderr)
        return 2

    findings = [_translate_finding(f) for f in findings_doc.get("findings", [])]

    applier = PatchApplier(spec_path)
    applier._PatchApplier__init_pending()

    for f in findings:
        applier.apply(f)

    new_src = applier.render()

    # Validate the new source is parseable
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"ERROR: patched spec failed to parse: {e}", file=sys.stderr)
        return 3

    # Print log
    if applier.applied:
        print(f"✓ Applied {len(applier.applied)} patches:")
        for line in applier.applied:
            print(f"  {line}")
    else:
        print("✓ Applied 0 patches")
    if applier.skipped:
        print(f"⚠ Skipped {len(applier.skipped)} patches:")
        for line in applier.skipped:
            print(f"  {line}")
    else:
        print("⚠ Skipped 0 patches")

    if args.dry_run:
        print("\n[DRY RUN] No file written.")
        if new_src != applier.src:
            print("--- diff preview (first 30 changed lines) ---")
            import difflib
            diff = list(difflib.unified_diff(
                applier.src.splitlines(), new_src.splitlines(),
                fromfile=str(spec_path), tofile=str(out_path),
                lineterm="", n=2))
            for line in diff[:80]:
                print(line)
        return 0

    if new_src == applier.src:
        print("(no changes to write)")
        return 0

    out_path.write_text(new_src, encoding="utf-8")
    print(f"\n→ wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
