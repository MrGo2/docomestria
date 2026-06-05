"""Declarative schema for typed extraction.

`Schema.apply` runs each transformer against the matching BoundValue and
produces a `dict[str, TypedValue]` keyed by the schema field name.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..llm.models import BoundValue
    from .models import Field, TypedValue


@dataclass(frozen=True)
class Schema:
    """A frozen mapping from field name to Field (transformer + flags).

    Use `apply()` to type a list of BoundValues. The optional `fusion_result`
    is needed by transformers that read VisualRect data (checkbox transformers).
    """

    fields: dict[str, "Field"]

    def __init__(self, fields: dict[str, "Field"]) -> None:
        # frozen=True forbids attribute assignment, so use object.__setattr__.
        object.__setattr__(self, "fields", dict(fields))

    def apply(
        self,
        bound_values: Iterable["BoundValue"],
        fusion_result: object | None = None,
    ) -> dict[str, "TypedValue"]:
        """Type every field in the schema using `bound_values`.

        Missing required fields produce a TypedValue with the
        `required_field_missing` issue and no normalized payload.
        """
        from .models import TransformContext, TypedValue

        by_name: dict[str, "BoundValue"] = {}
        for bv in bound_values:
            # Last-write-wins is fine: BoundValues are usually unique per field.
            by_name[bv.field_name] = bv

        out: dict[str, "TypedValue"] = {}
        for name, fld in self.fields.items():
            bv = by_name.get(name)
            transformer = fld.transformer
            transform_name = getattr(transformer, "name", transformer.__name__)
            if bv is None:
                if fld.required:
                    out[name] = TypedValue(
                        field=name,
                        raw="",
                        normalized=None,
                        bbox=None,
                        page=None,
                        source_items=(),
                        confidence=0.0,
                        transform_used=transform_name,
                        issues=("required_field_missing",),
                    )
                continue

            ctx = TransformContext(
                bound_value=bv,
                fusion_result=fusion_result,
                field_name=name,
            )
            try:
                normalized, score, issues = transformer(bv.value, context=ctx)
            except Exception as exc:  # pragma: no cover — defensive
                out[name] = TypedValue(
                    field=name,
                    raw=bv.value,
                    normalized=None,
                    bbox=bv.bbox,
                    page=bv.page,
                    source_items=bv.source_items,
                    confidence=0.0,
                    transform_used=transform_name,
                    issues=(f"transform_exception:{type(exc).__name__}",),
                )
                continue

            combined_conf = round(float(score) * float(bv.match_score), 4)
            out[name] = TypedValue(
                field=name,
                raw=bv.value,
                normalized=normalized,
                bbox=bv.bbox,
                page=bv.page,
                source_items=bv.source_items,
                confidence=combined_conf,
                transform_used=transform_name,
                issues=tuple(issues),
            )
        return out
