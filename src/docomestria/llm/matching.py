"""Substring and fuzzy matching helpers over a list of FusedItems.

Three-tier strategy (cheapest first):
  1. exact   — needle == haystack (normalized)
  2. substring — needle appears verbatim inside the joined haystack
  3. fuzzy   — `rapidfuzz.fuzz.partial_ratio` over the joined haystack

Multi-token values that span adjacent items on the same visual line are
supported because the haystack joins items in reading order with spaces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import FusedItem

try:  # pragma: no cover — optional dep guard
    from rapidfuzz import fuzz
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "docomestria.llm requires `rapidfuzz`. Install with `pip install docomestria[llm]`."
    ) from exc


_WS_RE = re.compile(r"\s+")
_MIN_FUZZY_LEN = 6  # short needles produce too many false positives


def normalize(text: str) -> str:
    """Lowercase and collapse internal whitespace."""
    return _WS_RE.sub(" ", (text or "").strip().lower())


@dataclass(frozen=True)
class MatchResult:
    """Outcome of looking a value up against the FusedItem haystack."""

    source_indices: tuple[int, ...]
    method: str  # "exact" | "substring" | "fuzzy" | "not_found"
    score: float


class FusedItemIndex:
    """Builds a normalized haystack from FusedItems with a char-to-item map.

    Items are joined in their original order, separated by single spaces.
    Each character in the haystack maps back to the source item index (or -1
    for filler spaces). This lets us recover the exact items a match spans.
    """

    def __init__(self, items: list[FusedItem]) -> None:
        self._items = items
        chunks: list[str] = []
        char_map: list[int] = []
        for i, it in enumerate(items):
            t = normalize(it.text)
            if not t:
                continue
            if chunks:
                chunks.append(" ")
                char_map.append(-1)
            chunks.append(t)
            char_map.extend([i] * len(t))
        self._haystack = "".join(chunks)
        self._char_to_item = char_map

    @property
    def haystack(self) -> str:
        return self._haystack

    def find(self, value: str, fuzzy_threshold: float = 0.85) -> MatchResult:
        """Locate `value` in the haystack. Returns a `MatchResult`."""
        needle = normalize(value)
        if not needle:
            return MatchResult(source_indices=(), method="not_found", score=0.0)

        # 1. exact match against the full haystack
        if needle == self._haystack:
            idxs = self._collect_indices(0, len(self._haystack))
            return MatchResult(source_indices=idxs, method="exact", score=1.0)

        # 2. substring
        pos = self._haystack.find(needle)
        if pos >= 0:
            idxs = self._collect_indices(pos, pos + len(needle))
            return MatchResult(source_indices=idxs, method="substring", score=0.95)

        # 2b. relaxed substring after dropping inner punctuation
        soft = re.sub(r"[^\w\s%]", "", needle)
        if soft and soft != needle:
            pos = self._haystack.find(soft)
            if pos >= 0:
                idxs = self._collect_indices(pos, pos + len(soft))
                return MatchResult(source_indices=idxs, method="substring", score=0.9)

        # 3. fuzzy (skip very short needles)
        if len(needle) < _MIN_FUZZY_LEN or not self._haystack:
            return MatchResult(source_indices=(), method="not_found", score=0.0)

        ratio = fuzz.partial_ratio(needle, self._haystack) / 100.0
        if ratio < fuzzy_threshold:
            return MatchResult(source_indices=(), method="not_found", score=0.0)

        # Locate the best window so we can attribute source items.
        best_pos = self._best_partial_window(needle)
        if best_pos < 0:
            return MatchResult(source_indices=(), method="not_found", score=0.0)
        idxs = self._collect_indices(best_pos, best_pos + len(needle))
        return MatchResult(source_indices=idxs, method="fuzzy", score=round(ratio, 3))

    def _collect_indices(self, start: int, end: int) -> tuple[int, ...]:
        seen = {i for i in self._char_to_item[start:end] if i >= 0}
        return tuple(sorted(seen))

    def _best_partial_window(self, needle: str) -> int:
        """Sliding window scan to find the best fuzzy match position."""
        win = len(needle)
        if win <= 0 or len(self._haystack) < win:
            return -1
        step = max(1, win // 4)
        best_score = 0.0
        best_pos = -1
        end = max(1, len(self._haystack) - win + 1)
        for start in range(0, end, step):
            window = self._haystack[start : start + win]
            score = fuzz.ratio(needle, window)
            if score > best_score:
                best_score = score
                best_pos = start
                if score >= 97:
                    break
        return best_pos
