"""Prompt builders for the pipeline orchestrator.

Prompts are intentionally minimal and provider-agnostic. They ask for a flat
JSON object whose keys match the schema field names.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ..transform.models import Schema

SYSTEM_PROMPT = (
    "You extract structured data from Spanish business documents. "
    "Return ONLY a JSON object that matches the requested schema. "
    "Use exact text from the document — do not invent or paraphrase values. "
    "If a field is not present, omit it. Do not wrap the JSON in markdown."
)


def build_extraction_prompt(schema: "Schema", context: dict[str, Any]) -> str:
    """Build the user prompt: schema description + document context."""
    fields_block = _describe_schema(schema)
    context_block = json.dumps(context, ensure_ascii=False, indent=2)
    return (
        "Extract the following fields from the document.\n"
        "Return a flat JSON object whose keys are exactly the field names below.\n"
        "Nested keys (with dots) should be returned as nested objects.\n\n"
        "Fields:\n"
        f"{fields_block}\n\n"
        "Document content (grouped by section):\n"
        f"{context_block}\n"
    )


def build_reprompt(
    schema: "Schema",
    context: dict[str, Any],
    *,
    hallucinated: tuple[str, ...] = (),
    low_confidence: tuple[str, ...] = (),
) -> str:
    """Build a follow-up prompt highlighting fields to redo."""
    feedback_lines: list[str] = []
    if hallucinated:
        feedback_lines.append(
            "These fields had values that could not be found in the document — "
            "re-extract them using ONLY exact text present in the document below: "
            + ", ".join(hallucinated)
        )
    if low_confidence:
        feedback_lines.append(
            "These fields had a weak match — produce a more literal extraction: "
            + ", ".join(low_confidence)
        )
    feedback = "\n".join(feedback_lines) or "Re-extract all fields with stricter literalness."
    base = build_extraction_prompt(schema, context)
    return f"{feedback}\n\n{base}"


def _describe_schema(schema: "Schema") -> str:
    lines: list[str] = []
    for name, fld in schema.fields.items():
        transformer = fld.transformer
        ttype = getattr(transformer, "name", transformer.__name__)
        req = " (required)" if fld.required else ""
        desc = f" — {fld.description}" if fld.description else ""
        lines.append(f"  - {name}: {ttype}{req}{desc}")
    return "\n".join(lines)


__all__ = ["SYSTEM_PROMPT", "build_extraction_prompt", "build_reprompt"]
