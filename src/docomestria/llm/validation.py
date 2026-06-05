"""QA checks over `BoundValue` lists — hallucinations and role mismatches."""

from __future__ import annotations

from .models import BoundValue, ProvenanceIssue

# Semantic roles that almost never carry data values — if an extracted value
# binds inside one of these, the LLM probably mistook a heading for a datum.
ROLE_MISMATCH_LABELS: frozenset[str] = frozenset(
    {"section_header", "title", "page_header", "page_footer", "picture"}
)


def detect_hallucinations(
    bound_values: list[BoundValue],
    *,
    require_score: float = 0.7,
) -> list[ProvenanceIssue]:
    """Flag values that could not be matched to any FusedItem above threshold.

    Two outcomes raise an issue:
      - `match_method == "not_found"` (hallucination, severity=high)
      - matched but `match_score < require_score` (low_confidence, severity=medium)
    """
    issues: list[ProvenanceIssue] = []
    for bv in bound_values:
        if bv.match_method == "not_found":
            issues.append(
                ProvenanceIssue(
                    field_name=bv.field_name,
                    value=bv.value,
                    issue_type="hallucination",
                    severity="high",
                    detail=(
                        f"Value {bv.value!r} for field {bv.field_name!r} was not found "
                        f"in any source item; the LLM may have invented it."
                    ),
                )
            )
            continue
        if bv.match_score < require_score:
            issues.append(
                ProvenanceIssue(
                    field_name=bv.field_name,
                    value=bv.value,
                    issue_type="low_confidence",
                    severity="medium",
                    detail=(
                        f"Value {bv.value!r} matched with score {bv.match_score:.2f} "
                        f"(< {require_score:.2f})."
                    ),
                )
            )
    return issues


def detect_role_mismatches(
    bound_values: list[BoundValue],
) -> list[ProvenanceIssue]:
    """Flag values whose docling_label suggests heading or furniture, not data."""
    issues: list[ProvenanceIssue] = []
    for bv in bound_values:
        if bv.match_method == "not_found":
            continue
        label = bv.docling_label
        if label and label in ROLE_MISMATCH_LABELS:
            issues.append(
                ProvenanceIssue(
                    field_name=bv.field_name,
                    value=bv.value,
                    issue_type="role_mismatch",
                    severity="medium",
                    detail=(
                        f"Value {bv.value!r} for field {bv.field_name!r} is located "
                        f"inside a {label!r} block; it is likely a heading, not data."
                    ),
                )
            )
    return issues
