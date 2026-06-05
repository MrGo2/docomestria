"""Typed extraction layer — convert raw strings to typed values, preserve bbox.

Optional sub-package. Requires `python-dateutil`, `python-stdnum`, `babel`,
and `phonenumbers` (install via `pip install docomestria[transform]`).

The transform layer takes BoundValues from the LLM provenance layer (or any
source of raw strings) and produces TypedValues that carry the normalized
typed payload alongside the original bbox/page/source_items provenance.
"""

from __future__ import annotations

from . import transformers
from .models import Field, Schema, TransformContext, TransformError, TypedValue

__all__ = [
    "Field",
    "Schema",
    "TransformContext",
    "TransformError",
    "TypedValue",
    "transformers",
]
