"""Core dataclasses for the transform layer.

`TypedValue` is the public output type: it carries both the normalized typed
value AND the original bbox/page/source_items provenance from BoundValue.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as _dc_field
from typing import TYPE_CHECKING, Any, Protocol

from ..models import BBox

if TYPE_CHECKING:  # pragma: no cover
    from ..llm.models import BoundValue
    from .schema import Schema as _Schema  # noqa: F401


class TransformError(Exception):
    """Raised when a transform fails at the schema level (not per-field)."""


@dataclass(frozen=True)
class TransformContext:
    """Optional context passed to transformers that need it.

    `bound_value` carries the upstream BoundValue (for source items / bbox).
    `fusion_result` is the FusionResult container — only needed by transformers
    that read VisualRect data, e.g. checkbox transformers.
    """

    bound_value: "BoundValue | None" = None
    fusion_result: Any | None = None  # FusionResult, kept as Any to avoid cycles
    field_name: str | None = None


class Transformer(Protocol):
    """Callable contract for a transformer.

    Returns `(normalized_value, confidence, issues)`. Implementations should be
    pure functions of their inputs.
    """

    name: str

    def __call__(
        self,
        raw: str,
        *,
        context: TransformContext | None = None,
    ) -> tuple[Any, float, tuple[str, ...]]: ...


@dataclass(frozen=True)
class Field:
    """A schema field — pairs a key with a transformer and optional flags.

    `labels` is an optional tuple of label hints used by `Pipeline(llm=None)`
    deterministic mode. When `None`, hints are inferred from the schema key's
    last segment via `infer_labels_from_key()`.
    """

    transformer: Callable[..., tuple[Any, float, tuple[str, ...]]]
    required: bool = False
    description: str | None = None
    labels: tuple[str, ...] | None = None


def infer_labels_from_key(key: str) -> tuple[str, ...]:
    """Derive label hints from a schema key's last segment.

    Examples:
        ``"datos_titular.fecha_nacimiento"`` -> ``("Fecha de nacimiento", "Fecha nacimiento")``
        ``"nif"``                            -> ``("Nif",)``

    The rules are intentionally simple — explicit `Field(labels=...)` is the
    recommended escape hatch when the heuristic gets it wrong.
    """
    last = key.rsplit(".", 1)[-1].strip()
    if not last:
        return ()
    parts = [p for p in last.replace("-", "_").split("_") if p]
    if not parts:
        return ()
    spaced = " ".join(parts)
    pretty = spaced[:1].upper() + spaced[1:]
    if len(parts) >= 2:
        joined = parts[0].capitalize() + " de " + " ".join(parts[1:])
        return (joined, pretty)
    return (pretty,)


@dataclass(frozen=True)
class TypedValue:
    """A typed value preserving the original bbox/page/source_items provenance.

    The `trace()` method walks the provenance chain back to the engine-level
    items (LiteItem + DoclingBlock + VisualRect). It is implemented in
    `docomestria.result` to avoid a circular import.
    """

    field: str
    raw: str
    normalized: Any
    bbox: BBox | None
    page: int | None
    source_items: tuple[str, ...]
    confidence: float
    transform_used: str
    issues: tuple[str, ...] = _dc_field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        """True when the value has no issues and a non-None normalized payload."""
        return not self.issues and self.normalized is not None

    def trace(self, fusion_result: Any) -> Any:
        """Walk back to LiteItems / DoclingBlocks / VisualRects.

        Implemented in `docomestria.result.build_trace`. Imported lazily to
        avoid the cycle transform -> result -> llm.models -> transform.
        """
        from ..result import build_trace

        return build_trace(self, fusion_result)


# Re-export Schema lazily — defined in schema.py to keep this module small.
from .schema import Schema  # noqa: E402, F401  (re-export)
