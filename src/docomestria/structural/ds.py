"""Dempster-Shafer evidence combination for cross-engine voting.

Bayesian scoring penalises engine abstention: an engine that does not opine
on a region contributes negative evidence even when it simply has no view.
Dempster-Shafer (DS) models *ignorance* explicitly — an engine that doesn't
apply to a candidate produces high ``ignorance`` mass rather than refutation.

For each ``PairCandidate`` we build three mass functions (Docling, LiteParse,
pdfplumber), combine them via Dempster's rule, and use the combined belief as
a small modulator on the rule-based score (see ``scoring.score_one``).

The framework is intentionally conservative — its job is to provide a
principled cross-vote signal without overpowering the calibrated additive
scoring already in place.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import PairCandidate


@dataclass(frozen=True)
class MassFunction:
    """Three-way mass assignment over {supports, refutes, unknown}.

    Components must sum to 1.0 (within a small float epsilon). The
    ``ignorance`` slot represents an engine that has no opinion — neither
    supporting nor refuting the candidate.

    Belief = ``support`` (lower bound on probability of "is a real pair").
    Plausibility = ``1 - refute`` (upper bound).
    """

    support: float
    refute: float
    ignorance: float

    def __post_init__(self) -> None:
        total = self.support + self.refute + self.ignorance
        if not (0.999 <= total <= 1.001):
            raise ValueError(
                f"MassFunction components must sum to 1.0, got {total:.4f}"
            )
        if self.support < 0 or self.refute < 0 or self.ignorance < 0:
            raise ValueError("MassFunction components must be non-negative")


# A vacuous mass function — pure ignorance, used when an engine has nothing
# to say about a candidate.
VACUOUS = MassFunction(support=0.0, refute=0.0, ignorance=1.0)


def combine_dempster(m1: MassFunction, m2: MassFunction) -> MassFunction:
    """Combine two mass functions using Dempster's rule.

    Conflict mass K = m1(support)*m2(refute) + m1(refute)*m2(support).
    Combined components are normalised by (1 - K).  When K == 1 the
    evidence is fully contradictory; we degrade gracefully to the
    average of the two inputs rather than raising.
    """
    # Direct support: both support, or one supports + other ignorant.
    s = (
        m1.support * m2.support
        + m1.support * m2.ignorance
        + m1.ignorance * m2.support
    )
    r = (
        m1.refute * m2.refute
        + m1.refute * m2.ignorance
        + m1.ignorance * m2.refute
    )
    i = m1.ignorance * m2.ignorance
    k = m1.support * m2.refute + m1.refute * m2.support

    denom = 1.0 - k
    if denom < 1e-9:
        # Fully conflicting evidence — fall back to a simple average so
        # downstream callers still get a usable belief value.
        avg_support = (m1.support + m2.support) / 2.0
        avg_refute = (m1.refute + m2.refute) / 2.0
        avg_ignorance = max(0.0, 1.0 - avg_support - avg_refute)
        # Renormalise in case of float drift.
        total = avg_support + avg_refute + avg_ignorance or 1.0
        return MassFunction(
            support=avg_support / total,
            refute=avg_refute / total,
            ignorance=avg_ignorance / total,
        )

    return MassFunction(
        support=s / denom,
        refute=r / denom,
        ignorance=i / denom,
    )


def belief(m: MassFunction) -> float:
    """Belief = lower bound on the probability of 'is a real pair'."""
    return m.support


def plausibility(m: MassFunction) -> float:
    """Plausibility = upper bound on the probability of 'is a real pair'."""
    return 1.0 - m.refute


# --------------------------------------------------------------------------
# Per-engine mass functions
# --------------------------------------------------------------------------
#
# Each ``*_mass`` function inspects ``PairCandidate`` features to decide:
#   - Does this engine actually apply to this candidate?
#   - If yes, how strongly does its evidence support / refute the pair?
#
# When an engine does not apply, the returned mass is mostly ignorance — DS
# will then preserve the other engines' signal during combination.


def docling_mass(c: PairCandidate) -> MassFunction:
    """Docling's evidence for the pair.

    Strong support when the candidate comes directly from a Docling /
    fused table cell (``D-2col`` rule, or ``table_source`` in
    {docling, fused}).  Modest support when the value is empty but the
    table-cell confirmation flag is set.  Otherwise mostly ignorance —
    Docling did not produce this candidate.
    """
    rule = c.rule
    source = c.features.get("table_source")
    is_docling_rule = rule == "D-2col" or source in ("docling", "fused")
    if is_docling_rule:
        # Slight refutation when Docling marks the row as unresolved /
        # low confidence (shape-5 fallback in candidates.py).
        if c.features.get("unresolved_matrix"):
            return MassFunction(support=0.40, refute=0.10, ignorance=0.50)
        return MassFunction(support=0.60, refute=0.0, ignorance=0.40)
    return MassFunction(support=0.0, refute=0.0, ignorance=1.0)


def liteparse_mass(c: PairCandidate) -> MassFunction:
    """LiteParse's evidence for the pair.

    LiteParse opines on candidates that come from text-run analysis
    (``L-*`` rules) or whose features describe a colon / tight x-gap
    pattern.  A tight x-gap on ``L-horizontal`` is a strong signal that
    the label and value were laid out as a pair; a colon in the label
    likewise supports the pairing.
    """
    rule = c.rule
    is_lite_rule = rule.startswith("L-")
    if not is_lite_rule:
        return MassFunction(support=0.0, refute=0.0, ignorance=1.0)

    support = 0.40  # baseline LiteParse opinion
    if c.features.get("label_ends_with_colon"):
        support += 0.15
    gap = c.features.get("x_gap")
    if isinstance(gap, (int, float)) and gap < 30:
        support += 0.10
    # Cap below the docling support so cross-engine agreement still
    # produces a noticeable lift rather than saturating on LiteParse alone.
    support = min(support, 0.55)
    ignorance = max(0.0, 1.0 - support)
    return MassFunction(support=support, refute=0.0, ignorance=ignorance)


def pdfplumber_mass(c: PairCandidate) -> MassFunction:
    """pdfplumber's evidence for the pair.

    pdfplumber's contribution is geometric: it confirms a pair when both
    label and value sit inside a visual grid (fused table).  Detecting
    that purely from the candidate's features is approximate — we use
    ``table_source == "fused"`` as the strongest proxy (the table was
    seen by BOTH pdfplumber and Docling).  A pdfplumber-only source is
    weaker; absence of any table source means pdfplumber has no opinion.
    """
    source = c.features.get("table_source")
    if source == "fused":
        return MassFunction(support=0.50, refute=0.0, ignorance=0.50)
    if source == "pdfplumber":
        return MassFunction(support=0.35, refute=0.0, ignorance=0.65)
    return MassFunction(support=0.0, refute=0.0, ignorance=1.0)


def combined_mass(c: PairCandidate) -> MassFunction:
    """Combine all three engine masses for one candidate."""
    return combine_dempster(
        docling_mass(c),
        combine_dempster(liteparse_mass(c), pdfplumber_mass(c)),
    )
