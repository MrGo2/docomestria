"""Transformer building blocks: protocol, compose, regex, enum."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from ..models import TransformContext

TransformerFn = Callable[..., tuple[Any, float, tuple[str, ...]]]


def _named(name: str) -> Callable[[TransformerFn], TransformerFn]:
    """Attach a `.name` attribute to a transformer function."""

    def deco(fn: TransformerFn) -> TransformerFn:
        fn.name = name  # type: ignore[attr-defined]
        return fn

    return deco


def regex(pattern: str, *, flags: int = 0, name: str | None = None) -> TransformerFn:
    """Validate that `raw` fully matches `pattern`.

    Returns the original string when it matches, None otherwise.
    """
    compiled = re.compile(pattern, flags=flags)
    tr_name = name or f"regex({pattern!r})"

    @_named(tr_name)
    def _tr(
        raw: str, *, context: TransformContext | None = None
    ) -> tuple[Any, float, tuple[str, ...]]:
        raw = (raw or "").strip()
        if not raw:
            return None, 0.0, ("empty",)
        if compiled.fullmatch(raw):
            return raw, 1.0, ()
        return None, 0.0, ("regex_no_match",)

    return _tr


def enum(
    values: list[str], *, case_insensitive: bool = True, name: str | None = None
) -> TransformerFn:
    """Validate that `raw` is one of `values`."""
    norm = {v.lower(): v for v in values} if case_insensitive else {v: v for v in values}
    tr_name = name or f"enum({values!r})"

    @_named(tr_name)
    def _tr(
        raw: str, *, context: TransformContext | None = None
    ) -> tuple[Any, float, tuple[str, ...]]:
        raw_s = (raw or "").strip()
        if not raw_s:
            return None, 0.0, ("empty",)
        key = raw_s.lower() if case_insensitive else raw_s
        if key in norm:
            return norm[key], 1.0, ()
        return None, 0.0, ("not_in_enum",)

    return _tr


def compose(*transformers: TransformerFn, name: str | None = None) -> TransformerFn:
    """Chain transformers — each runs against the previous output if string-coerced.

    The combined confidence is the product. Issues from all stages accumulate.
    The final normalized value is the last stage's output.
    """
    tr_name = (
        name or "compose(" + ",".join(getattr(t, "name", t.__name__) for t in transformers) + ")"
    )

    @_named(tr_name)
    def _tr(
        raw: str, *, context: TransformContext | None = None
    ) -> tuple[Any, float, tuple[str, ...]]:
        current_raw = raw
        normalized: Any = raw
        score = 1.0
        all_issues: list[str] = []
        for t in transformers:
            normalized, s, issues = t(current_raw, context=context)
            score *= float(s)
            all_issues.extend(issues)
            if normalized is None:
                break
            current_raw = str(normalized)
        return normalized, round(score, 4), tuple(all_issues)

    return _tr
