"""Reusable golden-builder library.

Usage:
    from docomestria.golden import GoldenBuilder
    builder = GoldenBuilder(pdf_path, page_num=1)
    golden = builder.build(structure_spec, meta={...})
    builder.save(golden, out_path)
"""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

from .engine_data import EngineData
from .walker import walk_and_link


class GoldenBuilder:
    def __init__(self, pdf_path, page_num: int = 1, atoms_path=None):
        self.pdf_path = Path(pdf_path)
        self.page_num = page_num
        if atoms_path is None:
            root = self.pdf_path
            # Default atoms location relative to project: .planning/extraction/atoms/<stem>-pNN.atoms.json
            stem = f"{self.pdf_path.stem}-p{page_num:02d}.atoms.json"
            atoms_path = Path.cwd() / ".planning" / "extraction" / "atoms" / stem
        self.atoms_path = Path(atoms_path)
        if not self.atoms_path.exists():
            raise FileNotFoundError(
                f"Atoms file not found: {self.atoms_path}\n"
                f"Run: PYTHONPATH=src python3 scripts/extract_atoms.py "
                f"'{self.pdf_path}' --page {self.page_num}"
            )
        self.eng = EngineData(self.pdf_path, self.atoms_path, self.page_num)

    def build(self, structure: list, meta: dict | None = None) -> dict:
        # Defensive copy: the walker mutates nodes in place (adds bbox/evidence).
        # Without this, calling build() twice on the same spec object yields
        # different counts on the second run.
        structure = copy.deepcopy(structure)
        meta = dict(meta or {})
        structure, flat_kv, stats = walk_and_link(structure, self.eng)
        # `sections` is a flat compat view (id, title, bboxes only) used by the
        # legacy viewer. The hierarchical truth lives in `structure`.
        sections = []
        for node in structure:
            if node.get("type") == "section":
                sections.append({
                    "id": node.get("id"),
                    "title": node.get("title"),
                    "title_bbox": node.get("title_bbox"),
                    "container_bbox": node.get("container_bbox"),
                    "_view": "compat_flat",
                })
        return {
            "pdf": str(self.pdf_path),
            "page": self.page_num,
            "page_size_pt": [self.eng.width, self.eng.height],
            "document_type": meta.get("document_type"),
            "structure": structure,
            "sections": sections,
            "kv_pairs": flat_kv,
            "noise": meta.get("noise", []),
            "diagnostics": {
                "method": "hand-curated structured-model golden, 3-engine linked",
                "annotator": meta.get("annotator", "carlos"),
                "n_chars": len(self.eng.chars),
                "n_rows": len(self.eng.rows),
                "n_liteparse_spans": len(self.eng.spans),
                "n_docling_blocks": len(self.eng.blocks),
                "n_rects": len(self.eng.rects),
                # kv_pair_breakdown sums to len(kv_pairs). 3/2/1/0_eng are real
                # value cells classified by engine-link count; empty/footnote/
                # footnote_ref are alternate paths (not value-bearing leaves).
                "kv_pair_breakdown": stats,
            },
            "_meta": {
                "annotator": meta.get("annotator", "carlos"),
                "annotated_at": str(date.today()),
                "method": "hand-curated reference (structured + 3-engine linked)",
                "covers_cases": meta.get("covers_cases", []),
                "needs_review": False,
                "document_type": meta.get("document_type"),
            },
        }

    def save(self, golden: dict, out_path: Path) -> None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(golden, ensure_ascii=False, indent=2),
                            encoding="utf-8")


__all__ = ["GoldenBuilder", "EngineData", "walk_and_link"]
