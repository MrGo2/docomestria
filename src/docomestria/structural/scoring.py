"""Score `PairCandidate` instances, dedupe by label, and emit final `Pair`s.

Scoring is rule-based, no learned weights — starting weights come from the
strategy doc and will be tuned as we score against ParseBench. Every emitted
`Pair` carries `score` (raw 0..1), `confidence` (banded), and `evidence` (the
list of rules that contributed).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .models import Confidence, Pair, PairCandidate

# Base score per emitter — calibrated so the cleanest signal (Docling 2-col
# matrix matched by TableFormer, validated on LABORAL & PATRIMONIAL) wins
# ties against bare geometric pairing. See `.planning/structural-extraction-strategy.md`.
BASE_SCORE = {
    "D-2col": 0.80,
    "L-inline-split": 0.75,
    "L-horizontal": 0.70,
    "L-vertical": 0.55,
}

# Bonuses are additive and capped at +0.20 total so a perfect candidate
# from a weaker rule cannot leapfrog a Docling table candidate.
BONUS_COLON = 0.10
BONUS_TIGHT_X_GAP = 0.05    # horizontal gap < 30pt suggests intentional pairing
BONUS_VALUE_EMPTY_BUT_CONFIRMED = 0.05  # empty value confirmed by 2-col table

# Penalties.
PENALTY_VALUE_SMALL_FONT = 0.05  # value font notably smaller than label
PENALTY_LONG_VALUE = 0.05        # value text > 60 chars on geometric rules
                                 # (we don't penalise long table values; tables
                                 # legitimately hold paragraphs)

# Confidence bands. The thresholds are deliberately conservative — anything
# below 0.50 is emitted but flagged LOW so callers can suppress it.
HIGH_THRESHOLD = 0.80
MEDIUM_THRESHOLD = 0.50

# Dedup key uses normalised text rather than bbox proximity — two candidates
# with the same label and the same value (modulo whitespace and case) are the
# same pair regardless of where they were detected. This handles:
#   - Engine duplication (pdfplumber re-detecting a Docling table at a
#     different Y on rotated/fold-out pages — observed on BBVA5 p16 glossary).
#   - Cross-emitter agreement on a real pair, where D-2col and L-horizontal
#     both produce the same logical pair from different geometric inputs.
# Intentional duplicates (Titular 1 vs Titular 2 forms in BBVA: same label,
# different values) are preserved because the value component differs.


# --------------------------------------------------------------------------
# Scoring one candidate
# --------------------------------------------------------------------------


def _bonus(c: PairCandidate) -> float:
    bonus = 0.0
    if c.features.get("label_ends_with_colon"):
        bonus += BONUS_COLON
    if c.rule == "L-horizontal":
        gap = c.features.get("x_gap", 999)
        if isinstance(gap, (int, float)) and gap < 30:
            bonus += BONUS_TIGHT_X_GAP
    if c.features.get("value_empty") and c.rule == "D-2col":
        bonus += BONUS_VALUE_EMPTY_BUT_CONFIRMED
    return min(bonus, 0.20)


def _penalty(c: PairCandidate) -> float:
    pen = 0.0
    if c.rule in ("L-horizontal", "L-vertical") and len(c.value_text) > 60:
        pen += PENALTY_LONG_VALUE
    if c.label_item and c.value_item:
        lf = c.label_item.item.font_size or 0
        vf = c.value_item.item.font_size or 0
        if lf and vf and vf < lf - 1.5:
            pen += PENALTY_VALUE_SMALL_FONT
    return pen


def score_one(c: PairCandidate) -> float:
    base = BASE_SCORE.get(c.rule, 0.40)
    return max(0.0, min(1.0, base + _bonus(c) - _penalty(c)))


def confidence_for(score: float) -> Confidence:
    if score >= HIGH_THRESHOLD:
        return Confidence.HIGH
    if score >= MEDIUM_THRESHOLD:
        return Confidence.MEDIUM
    return Confidence.LOW


# --------------------------------------------------------------------------
# Dedup across emitters
# --------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Whitespace-collapsed, lowercased, colon-stripped version of `text`."""
    return "".join(text.lower().split()).rstrip(":")


def _dedup_key(c: PairCandidate) -> tuple[int, str, str]:
    """Group candidates representing the same logical pair.

    Two candidates collapse to the same key when both their label AND value
    normalise to the same string on the same page — preserving intentional
    duplicates (e.g. Titular 1 / Titular 2 forms have identical labels but
    different values) while removing parsing artefacts.
    """
    return (c.page, _normalise(c.label_text), _normalise(c.value_text))


def _pick_winner(group: list[PairCandidate]) -> tuple[PairCandidate, list[str]]:
    """Return the winning candidate and the merged evidence list.

    Highest score wins; ties broken by emitter base score (so D-2col beats
    L-horizontal on a tie). Evidence aggregates every rule that fired for
    this label — we use that to bump confidence when 2+ rules agree.
    """
    scored = sorted(
        group, key=lambda c: (score_one(c), BASE_SCORE.get(c.rule, 0)), reverse=True
    )
    winner = scored[0]
    evidence = []
    seen: set[str] = set()
    for c in scored:
        if c.rule not in seen:
            evidence.append(c.rule)
            seen.add(c.rule)
    return winner, evidence


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def resolve_pairs(candidates: Iterable[PairCandidate]) -> tuple[Pair, ...]:
    """Score every candidate, dedupe by label, and return final Pairs.

    When two emitters agree on the same label, the winner's score gets a
    small bump (max 0.10) and confidence may upgrade from MEDIUM to HIGH —
    cross-engine corroboration is the strongest signal we have.
    """
    groups: dict[tuple, list[PairCandidate]] = defaultdict(list)
    for c in candidates:
        groups[_dedup_key(c)].append(c)

    out: list[Pair] = []
    for group in groups.values():
        winner, evidence = _pick_winner(group)
        score = score_one(winner)
        if len(evidence) >= 2:
            score = min(1.0, score + 0.10)
        conf = confidence_for(score)
        sub_title = winner.features.get("subsection_title") or None
        out.append(
            Pair(
                label_text=winner.label_text,
                value_text=winner.value_text,
                label_bbox=winner.label_bbox,
                value_bbox=winner.value_bbox,
                page=winner.page,
                score=round(score, 3),
                confidence=conf,
                evidence=tuple(evidence),
                section_title=None,  # filled by extractor.py with page sections
                subsection_title=sub_title if isinstance(sub_title, str) else None,
            )
        )

    out.sort(key=lambda p: (p.page, p.label_bbox.top, p.label_bbox.left))
    return tuple(out)
