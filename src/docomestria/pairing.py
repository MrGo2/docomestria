"""Optional helper: pair labels to values within enclosing boxes."""

from __future__ import annotations

from collections import defaultdict

from .models import FusedItem

# Two items are considered to be on the same row when their vertical centres
# differ by less than this many points.
ROW_TOLERANCE_PT = 4.0


def _is_label(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return t.endswith(":") or t.endswith("：")


def _strip_label(text: str) -> str:
    return (text or "").rstrip(":：").strip()


def pair_labels_to_values(items: list[FusedItem]) -> dict[str, str]:
    """Pair label-like items to their value items within the same enclosing box.

    Heuristic:
      - An item ending in ``:`` is treated as a label.
      - The value is the nearest item to the right on the same row that lives
        in the same enclosing box.
      - Labels without a matching value are skipped.

    Items with no enclosing box are grouped together under a single bucket so
    labels in the page body still pair to their values.
    """
    by_box: dict[str | None, list[FusedItem]] = defaultdict(list)
    for it in items:
        by_box[it.enclosing_box_id].append(it)

    pairs: dict[str, str] = {}
    for group in by_box.values():
        group_sorted = sorted(group, key=lambda i: (i.bbox.top, i.bbox.left))
        for i, item in enumerate(group_sorted):
            if not _is_label(item.text):
                continue
            label_cy = item.bbox.centroid[1]
            label_right = item.bbox.right
            best: FusedItem | None = None
            best_dx = float("inf")
            for other in group_sorted[i + 1 :]:
                if other is item:
                    continue
                other_cy = other.bbox.centroid[1]
                if abs(other_cy - label_cy) > ROW_TOLERANCE_PT:
                    continue
                if other.bbox.left < label_right:
                    continue
                if _is_label(other.text):
                    continue
                dx = other.bbox.left - label_right
                if dx < best_dx:
                    best, best_dx = other, dx
            if best is not None:
                key = _strip_label(item.text)
                if key:
                    pairs[key] = best.text.strip()
    return pairs
