"""Classify each LiteItem by kind: TITLE / LABEL / VALUE / BODY.

Classification is *local* -- it inspects only the item's own font, size, text,
and the page's font-size distribution. Geometric context (is this item inside
a sub-header box? on the same row as a regular item?) is left to later stages
(`structure.py`, `candidates.py`), which may refine an item's role without
contradicting the kind assigned here.

The page-level signal we need is the *dominant body font size* -- the size used
for the bulk of the document's primary content. We compute it as the mode of
font sizes weighted by item count. Items meaningfully larger than the dominant
are titles; meaningfully smaller are body/footer text; same-size items split
into LABEL (bold) and VALUE (regular).

Font-size thresholds (TITLE / LABEL / BODY) are discovered per page via a
Gaussian Mixture Model (K=3) fitted on the font sizes present on that page.
The GMM separates the three natural clusters -- small (footnotes/body), medium
(labels/values), and large (titles) -- without relying on hardcoded deltas.

When scikit-learn is unavailable, `fit_font_size_buckets` degrades gracefully
to a percentile-based approximation: p75 of observed sizes -> title_min,
p40 -> body_max.  The GMM should always win for real documents; the fallback
exists so unit tests and environments without sklearn still work.
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

# Fallback fixed deltas used when the GMM has fewer than MIN_GMM_ITEMS items
# or when sklearn is unavailable AND there are too few sizes for percentiles.
# Deliberately wide so borderline same-size items stay LABEL/VALUE and only
# clear outliers become TITLE/BODY.
TITLE_SIZE_DELTA_PT = 1.5
BODY_SIZE_DELTA_PT = 1.5

# Minimum number of items needed to trust the page's dominant-size estimate.
# Below this we fall back to the page-level median to avoid letting a single
# 1-item page label everything as the wrong kind.
MIN_ITEMS_FOR_MODE = 4

# Minimum number of items (with a font_size) needed to attempt a GMM or
# percentile fit.  With fewer items the signal is unreliable; we fall back to
# dominant + fixed delta.
MIN_GMM_ITEMS = 6

# A bold item with no colon and this many words or more is almost certainly
# prose (warning paragraph, contract clause body) and not a label. Calibrated
# from BBVA contracts: "Tomese su tiempo y lealo atentamente..." (11 words),
# "En MADRID, a 03 de Abril de 2019" (8 words). Real bold labels in this
# corpus top out at 5 words ("AEAT - Consulta Actividades Economicas").
PROSE_MIN_WORDS = 6

# Pattern for list-enumeration markers ("1.", "a)", "iii.", "A.").
_ENUMERATION_RE = re.compile(r"^[A-Za-z0-9]{1,3}[\.\)]\s*$")


# ---------------------------------------------------------------------------
# GMM / percentile font-size bucket fitting
# ---------------------------------------------------------------------------

def fit_font_size_buckets(items: Iterable[LiteItem]) -> dict[str, float]:
    """Return per-page font-size thresholds discovered from the data.

    Returns a dict with two keys:
        title_min  -- items with font_size >= this are TITLE candidates
        body_max   -- items with font_size <= this are BODY candidates
        dominant   -- the estimated body/label font size (mode)

    Strategy (in priority order):
    1. sklearn GMM K=3  -- fits three gaussians, derives thresholds from the
       cluster means and their standard deviations (sqrt of variance).
    2. Percentile fallback  -- when sklearn is absent, uses numpy-free sorted
       percentiles: p75 -> title_min, p40 -> body_max.
    3. Hard delta fallback  -- when fewer than MIN_GMM_ITEMS sized items exist,
       returns dominant +/- the classic fixed deltas.
    """
    sized = [it.font_size for it in items if it.font_size]
    dominant = _dominant_from_sizes(sized)

    if len(sized) < MIN_GMM_ITEMS or dominant is None:
        # Not enough data -- keep the historic fixed-delta behaviour.
        if dominant is None:
            return {"title_min": float("inf"), "body_max": 0.0, "dominant": 0.0}
        return {
            "title_min": dominant + TITLE_SIZE_DELTA_PT,
            "body_max": dominant - BODY_SIZE_DELTA_PT,
            "dominant": dominant,
        }

    try:
        return _gmm_buckets(sized, dominant)
    except Exception:
        return _percentile_buckets(sized, dominant)


def _dominant_from_sizes(sizes: list[float]) -> float | None:
    """Mode of rounded font sizes, or median when too few items."""
    rounded = [round(s, 1) for s in sizes]
    if not rounded:
        return None
    if len(rounded) < MIN_ITEMS_FOR_MODE:
        return sorted(rounded)[len(rounded) // 2]
    counter = Counter(rounded)
    most_common = counter.most_common()
    top_count = most_common[0][1]
    candidates = [s for s, n in most_common if n == top_count]
    return min(candidates)


def _gmm_buckets(sizes: list[float], dominant: float) -> dict[str, float]:
    """Fit a 3-component GMM and derive TITLE/BODY thresholds.

    The GMM discovers up to 3 natural font-size clusters in the page.
    We identify each cluster by its mean relative to `dominant`:
      - largest mean  -> title cluster
      - smallest mean -> body/footnote cluster
      - middle mean   -> label/value cluster (the dominant)

    title_min  = title_mean  - 1 * title_std   (lower edge of title cluster)
    body_max   = body_mean   + 1 * body_std    (upper edge of body cluster)

    Both are clamped so they cannot cross the dominant size (which would
    collapse the label/value band entirely).
    """
    # Lazy import -- sklearn is listed in [stats] optional dep.
    import warnings  # noqa: PLC0415

    from sklearn.exceptions import ConvergenceWarning  # noqa: PLC0415
    from sklearn.mixture import GaussianMixture  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415

    X = np.array(sizes).reshape(-1, 1)
    gmm = GaussianMixture(n_components=3, random_state=0, n_init=3)
    with warnings.catch_warnings():
        # Degenerate inputs (single-size pages, near-duplicate sizes) trigger
        # ConvergenceWarning. We handle the collapse by clamping below, so
        # the warning is noise, not signal.
        warnings.simplefilter("ignore", ConvergenceWarning)
        gmm.fit(X)

    means = gmm.means_.flatten()
    stds = gmm.covariances_.flatten() ** 0.5

    # Sort clusters by mean ascending: body < label < title
    order = means.argsort()
    body_mean, _label_mean, title_mean = means[order]
    body_std, _label_std, title_std = stds[order]

    title_min = float(title_mean - title_std)
    body_max = float(body_mean + body_std)

    # Clamp: title_min must be above dominant; body_max must be below dominant.
    title_min = max(title_min, dominant + 0.5)
    body_max = min(body_max, dominant - 0.5)

    return {"title_min": title_min, "body_max": body_max, "dominant": dominant}


def _percentile_buckets(sizes: list[float], dominant: float) -> dict[str, float]:
    """Percentile-based fallback when sklearn is unavailable.

    p75 of observed sizes -> title_min (large sizes are title candidates)
    p40 of observed sizes -> body_max  (small sizes are body/footnote)
    Both are clamped against dominant as in the GMM path.
    """
    s = sorted(sizes)
    n = len(s)

    def percentile(p: float) -> float:
        idx = p / 100.0 * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return s[lo] * (1 - frac) + s[hi] * frac

    title_min = max(percentile(75), dominant + 0.5)
    body_max = min(percentile(40), dominant - 0.5)
    return {"title_min": title_min, "body_max": body_max, "dominant": dominant}


# ---------------------------------------------------------------------------
# Per-item classification helpers
# ---------------------------------------------------------------------------

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

    Catches "1.", "a)", "iii.", "-", "*" -- items that PDFs use as visual
    bullets but that carry no semantic key. Classifying these as BODY
    prevents the geometric pairer from emitting nonsense like
    `'1.' -> 'BBVA podra exigir...'`.
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
    on banking contracts -- this check downgrades them to BODY before
    pairing runs.
    """
    stripped = text.strip()
    if not stripped or ":" in stripped:
        return False
    return len(stripped.split()) >= PROSE_MIN_WORDS


def dominant_font_size(items: Iterable[LiteItem]) -> float | None:
    """Most common font size across the items, or None if we can't tell.

    Items missing a font_size are ignored. We return the *mode* -- not the
    mean -- because mean is skewed by titles and footers in skinny docs.
    """
    sizes = [round(it.font_size, 1) for it in items if it.font_size]
    return _dominant_from_sizes(sizes)


def classify_item(
    item: LiteItem,
    dominant_size: float | None,
    *,
    title_min: float | None = None,
    body_max: float | None = None,
) -> ClassifiedItem:
    """Apply local rules to one item and return its ClassifiedItem.

    When `title_min` / `body_max` are provided (from `fit_font_size_buckets`),
    those absolute thresholds are used instead of the historic fixed deltas
    relative to `dominant_size`.  Either way, the decision tree is the same:

    Decision order (each rule appended to `evidence` so we can audit later):
        1. No usable font signal at all          -> UNKNOWN
        2. Significantly smaller than dominant   -> BODY (footer / fine print)
        3. Bold + significantly larger           -> TITLE (page or section title)
        4. Regular + significantly larger        -> TITLE (rare, but logo / banner)
        5. Bold + same-size + ends with ":"      -> LABEL (high confidence)
        6. Bold + same-size                      -> LABEL (may be title or empty
                                                   label -- structure.py decides)
        7. Regular + same-size                   -> VALUE
        8. Anything else                         -> UNKNOWN
    """
    evidence: list[str] = []
    text = item.text or ""
    size = item.font_size
    bold = is_bold(item.font_name)

    if not item.font_name and not size:
        return ClassifiedItem(item=item, kind=ItemKind.UNKNOWN, evidence=("no-font-signal",))

    # Pre-checks that override the size/bold matrix below -- items matching
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

    # Resolve effective thresholds: use GMM-derived absolutes when available,
    # otherwise fall back to the classic fixed deltas relative to dominant.
    effective_title_min = title_min if title_min is not None else (dominant_size + TITLE_SIZE_DELTA_PT)
    effective_body_max = body_max if body_max is not None else (dominant_size - BODY_SIZE_DELTA_PT)

    # Bold items are never classified as BODY by size alone: in form documents
    # small bold text is almost always a label (e.g. "Primera Tarjeta Emitida"
    # at 7pt bold). Only non-bold items can be demoted to BODY by size.
    if size < effective_body_max and not bold:
        delta = dominant_size - size
        evidence.append(f"size-{delta:.1f}pt-below-dominant")
        return ClassifiedItem(item, ItemKind.BODY, tuple(evidence))

    if size > effective_title_min:
        delta = size - dominant_size
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

    The font-size buckets are computed once per page via GMM (or percentile
    fallback) so a multi-page document with different scales per page still
    classifies consistently within each.
    """
    items = tuple(items)
    buckets = fit_font_size_buckets(items)
    dominant = buckets["dominant"] or None
    title_min = buckets["title_min"]
    body_max = buckets["body_max"]
    return tuple(
        classify_item(it, dominant, title_min=title_min, body_max=body_max)
        for it in items
    )


def classify(items: Iterable[LiteItem]) -> tuple[ClassifiedItem, ...]:
    """Classify a flat list of LiteItems, grouping by page so each page gets
    its own font-size reference. Order of the result matches input order.
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
