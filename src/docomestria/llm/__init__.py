"""LLM provenance layer — bind LLM-extracted outputs back to source PDF items.

Optional sub-package. Requires `rapidfuzz` (install via `pip install docomestria[llm]`).

LLM-agnostic: takes plain JSON dicts. Works with Gemini, Claude, OpenAI, local models.
"""

from __future__ import annotations

from .models import BoundValue, ProvenanceIssue
from .provenance import bind_provenance
from .validation import detect_hallucinations, detect_role_mismatches

__all__ = [
    "BoundValue",
    "ProvenanceIssue",
    "bind_provenance",
    "detect_hallucinations",
    "detect_role_mismatches",
]
