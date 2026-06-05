"""Classify each LiteParse item by kind: TITLE / LABEL / VALUE / BODY.

Classification is *local* — it inspects only the item's own font, size, text,
and the page's font-size distribution. Geometric context (is this item inside
a sub-header box? on the same row as a regular item?) is left to later stages
(`structure.py`, `candidates.py`), which may refine an item's role without
contradicting the kind assigned here.

The page-level signal we need is the *dominant body font size* — the size used
for the bulk of the document's primary content. We compute it as the mode of
font sizes weighted by item count. Items meaningfully larger than the dominant
are titles; meaningfully smaller are body/footer text; same-size items split
into LABEL (bold) and VALUE (regular).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from ..models import LiteItem
from .models import ClassifiedItem, ItemKind

# Tokens that, when present in a font name, indicate a bold-class weight.
# PDFs use very varied naming; substring match on the lowercased name catches
# the common cases (Helvetica-Bold, Arial-Black, TimesNewRoman-Heavy, etc.).
BOLD_TOKENS = ("bold", "black", "heavy", "demi", "semibold")

# A font size is "the same as dominant" if it falls within this many points
# either side of the dominant size. Two-point tolerance accommodates the
# half-point shifts some PDFs use (10.0 vs 10.5 for the same logical body).
SAME_SIZE_TOLERANCE_PT = 1.0

# A title is significantly larger than dominant; body text significantly
# smaller. Thresholds are deliberately wide so borderline same-size items
# stay LABEL/VALUE and only clear outliers become TITLE/BODY.
TITLE_SIZE_DELTA_PT = 1.5
BODY_SIZE_DELTA_PT = 1.5

# Minimum number of items needed to trust the page's dominant-size estimate.
# Below this we fall back to the page-level median to avoid letting a single
# 1-item page label everything as the wrong kind.
MIN_ITEMS_FOR_MODE = 4

# A bold item with no colon and this many words or more is almost certainly
# prose (warning paragraph, contract clause body) and not a label. Calibrated
# from BBVA contracts: "Tómese su tiempo y léalo atentamente..." (11 words),
# "En MADRID, a 03 de Abril de 2019" (8 words). Real bold labels in this
# corpus top out at 5 words ("AEAT - Consulta Actividades Economicas").
PROSE_MIN_WORDS = 6

# Pattern for list-enumeration markers ("1.", "a)", "iii.", "A.").
_ENUMERATION_RE = re.compile(r"^[A-Za-z0-9]{1,3}[\.\)]\s*$")


def is_bold(font_name: str | None) -> bool:
    if not font_name:
        return False
    lowered = font_name.lower()
    return any(token in lowered for token in BOLD_TOKENS)


def ends_with_colon(text: str) -> bool:
    """True if the visible text ends in a colon (the canonical KV separator).

    Trailing whitespace and ASCII fullwidth colon are both handled.
    """
    stripped = text.rstrip()
    return stripped.endswith(":") or stripped.endswith("：")


def is_meaningless_short(text: str) -> bool:
    """True if the text is an enumeration marker or pure punctuation.

    Catches "1.", "a)", "iii.", "-", "•" — items that PDFs use as visual
    bullets but that carry no semantic key. Classifying these as BODY
    prevents the geometric pairer from emitting nonsense like
    `'1.' -> 'BBVA podrá exigir...'`.
    """
    stripped = text.strip()
    if not stripped or len(stripped) > 4:
        return False
    if _ENUMERATION_RE.match(stripped):
        return True
    return not any(c.isalnum() for c in stripped)


def looks_like_prose(text: str) -> bool:
    """True if the text reads like a sentence fragment rather than a label.

    Trigger: many words AND no colon. Bold paragraphs (warnings, contract
    clauses) misclassified as LABELs are the dominant false-positive source
    on banking contracts — this check downgrades them to BODY before
    pairing runs.
    """
    stripped = text.strip()
    if not stripped or ":" in stripped:
        return False
    return len(stripped.split()) >= PROSE_MIN_WORDS


def dominant_font_size(items: Iterable[LiteItem]) -> float | None:
    """Most common font size across the items, or None if we can't tell.

    Items missing a font_size are ignored. We return the *mode* — not the
    mean — because mean is skewed by titles and footers in skinny docs.
    """
    sizes = [round(it.font_size, 1) for it in items if it.font_size]
    if len(sizes) < MIN_ITEMS_FOR_MODE:
        return sorted(sizes)[len(sizes) // 2] if sizes else None
    counter = Counter(sizes)
    # Counter.most_common is stable; tie-break by smaller size (likelier body).
    most_common = counter.most_common()
    top_count = most_common[0][1]
    candidates = [s for s, n in most_common if n == top_count]
    return min(candidates)


def classify_item(
    item: LiteItem, dominant_size: float | None
) -> ClassifiedItem:
    """Apply local rules to one item and return its ClassifiedItem.

    Decision order (each rule appended to `evidence` so we can audit later):
        1. No usable font signal at all          -> UNKNOWN
        2. Significantly smaller than dominant   -> BODY (footer / fine print)
        3. Bold + significantly larger           -> TITLE (page or section title)
        4. Regular + significantly larger        -> TITLE (rare, but logo / banner)
        5. Bold + same-size + ends with ":"      -> LABEL (high confidence)
        6. Bold + same-size                      -> LABEL (may be title or empty
                                                   label — structure.py decides)
        7. Regular + same-size                   -> VALUE
        8. Anything else                         -> UNKNOWN
    """
    evidence: list[str] = []
    text = item.text or ""
    size = item.font_size
    bold = is_bold(item.font_name)

    if not item.font_name and not size:
        return ClassifiedItem(item=item, kind=ItemKind.UNKNOWN, evidence=("no-font-signal",))

    # Pre-checks that override the size/bold matrix below — items matching
    # these patterns are body text regardless of formatting.
    if is_meaningless_short(text):
        return ClassifiedItem(item, ItemKind.BODY, ("enumeration-or-punct",))
    if looks_like_prose(text):
        return ClassifiedItem(
            item, ItemKind.BODY, (f"prose-{len(text.split())}-words-no-colon",)
        )

    if dominant_size is None or size is None:
        # No page-wide reference: fall back to font-only heuristic.
        if bold and ends_with_colon(text):
            return ClassifiedItem(item, ItemKind.LABEL, ("bold+colon", "no-dominant-size"))
        if bold:
            return ClassifiedItem(item, ItemKind.LABEL, ("bold", "no-dominant-size"))
        return ClassifiedItem(item, ItemKind.VALUE, ("regular", "no-dominant-size"))

    delta = size - dominant_size

    if delta <= -BODY_SIZE_DELTA_PT:
        evidence.append(f"size-{abs(delta):.1f}pt-below-dominant")
        return ClassifiedItem(item, ItemKind.BODY, tuple(evidence))

    if delta >= TITLE_SIZE_DELTA_PT:
        evidence.append(f"size+{delta:.1f}pt-above-dominant")
        evidence.append("bold" if bold else "regular")
        return ClassifiedItem(item, ItemKind.TITLE, tuple(evidence))

    # Same-size band: split by weight and colon.
    if bold:
        if ends_with_colon(text):
            return ClassifiedItem(item, ItemKind.LABEL, ("bold", "ends-with-colon"))
        return ClassifiedItem(item, ItemKind.LABEL, ("bold", "no-colon"))

    return ClassifiedItem(item, ItemKind.VALUE, ("regular", "same-size-as-dominant"))


def classify_page(items: Iterable[LiteItem]) -> tuple[ClassifiedItem, ...]:
    """Classify every item on a single page.

    The dominant font size is computed once per page so a multi-page document
    with different scales per page still classifies consistently within each.
    """
    items = tuple(items)
    dominant = dominant_font_size(items)
    return tuple(classify_item(it, dominant) for it in items)


def classify(items: Iterable[LiteItem]) -> tuple[ClassifiedItem, ...]:
    """Classify a flat list of LiteItems, grouping by page so each page gets
    its own dominant-size reference. Order of the result matches input order.
    """
    items = tuple(items)
    by_page: dict[int, list[LiteItem]] = {}
    for it in items:
        by_page.setdefault(it.page, []).append(it)
    classified_by_id: dict[int, ClassifiedItem] = {}
    for page_items in by_page.values():
        for ci in classify_page(page_items):
            classified_by_id[id(ci.item)] = ci
    return tuple(classified_by_id[id(it)] for it in items)
