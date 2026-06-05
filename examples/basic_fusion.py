"""Minimal example: fuse a PDF and print one line per text item."""

from __future__ import annotations

import sys
from pathlib import Path

from docomestria import fuse


def main(pdf_path: str) -> int:
    result = fuse(pdf_path)
    items = result.items
    print(f"fused {len(items)} text items from {Path(pdf_path).name}")
    for it in items[:20]:
        section = it.section_title or "-"
        label = it.docling_label or "-"
        print(f"  [{label:18}] section={section!r:30} text={it.text!r}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python basic_fusion.py <pdf>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
