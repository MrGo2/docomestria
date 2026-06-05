"""`Pipeline` — fuse → context → LLM → bind → schema → trace, in one call.

The orchestrator exposes two complementary entry points:

- `Pipeline.run(pdf)` — run to completion, return a single `ExtractionResult`.
- `Pipeline.stream(pdf)` — yield one `PipelineStep` per phase so UIs and
  observability tools can react to intermediate state. `run()` is implemented
  on top of `stream()` so both APIs produce identical results.

Per-phase implementations live in `_stream.py`; small pure helpers (JSON
parsing, cost aggregation, issue collection, timing/step emission) live in
`_helpers.py`. This module is the public composition + caching surface.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from ..llm.models import BoundValue
from ..llm.provenance import bind_provenance
from ..result import FusionResult
from ._helpers import HallucinationPolicy, StepEmitter, llm_id, parse_json, with_cache_hit
from ._stream import stream_bind_and_type, stream_cache_hit, stream_extract, stream_llm
from .cache import CacheBackend, DiskCache, build_cache_key
from .prompts import SYSTEM_PROMPT, build_reprompt
from .providers.base import LLMProvider, LLMResponse
from .result import ExtractionResult
from .retry import RetryPolicy
from .step import PipelineStep

# Type alias for the fuse hook (kept open for tests).
FuseFn = Callable[[str | Path], FusionResult]


class Pipeline:
    """End-to-end extraction orchestrator.

    The pipeline is intentionally mutable (not a frozen dataclass) because it
    composes long-lived collaborators (cache, retry, provider) that benefit
    from a regular __init__. Every value it *returns* is immutable.
    """

    def __init__(
        self,
        *,
        schema: Any,
        llm: LLMProvider,
        cache_dir: str | None = ".docomestria_cache",
        cache: CacheBackend | None = None,
        retry: RetryPolicy | None = None,
        on_hallucination: HallucinationPolicy = "flag",
        on_low_confidence_field: float = 0.0,
        fuse_fn: FuseFn | None = None,
        parallel_extract: bool = False,
        step_callback: Callable[[PipelineStep], None] | None = None,
    ) -> None:
        self.schema = schema
        self.llm = llm
        self.retry = retry or RetryPolicy()
        self.on_hallucination = on_hallucination
        self.on_low_confidence_field = on_low_confidence_field
        self._fuse_fn = fuse_fn
        self.parallel_extract = parallel_extract
        self.step_callback = step_callback
        self._last_cache_key: str | None = None
        if cache is not None:
            self.cache: CacheBackend | None = cache
        elif cache_dir is None:
            self.cache = None
        else:
            self.cache = DiskCache(cache_dir=cache_dir)

    # ----------------------------------------------------------------- API

    def run(self, pdf_path: str | Path) -> ExtractionResult:
        """Run the pipeline to completion and return an `ExtractionResult`.

        Internally implemented on top of `stream()`: we consume every step,
        keep the terminal one, and build the result from its captured state.
        """
        terminal: PipelineStep | None = None
        cached: ExtractionResult | None = None
        for step in self._stream_internal(pdf_path, lang="es"):
            if step.name == "cache_hit":
                cached = step.payload.get("result")
            if step.is_terminal:
                terminal = step
        if cached is not None:
            return with_cache_hit(cached)
        if terminal is None:  # pragma: no cover — stream always emits complete
            raise RuntimeError("Pipeline.stream() did not yield a terminal step")
        return terminal.payload["result"]

    def stream(
        self,
        pdf_path: str | Path,
        *,
        lang: str = "es",
    ) -> Iterator[PipelineStep]:
        """Run the pipeline as a sequence of observable steps.

        Yields one `PipelineStep` per phase. Consumer code can iterate at its
        own pace — pull manually for a Next-button UI, or simply
        `for step in pipe.stream(...): ...` for streaming progress.

        The final step has `is_terminal=True` and carries full state in
        `fusion`, `bound`, `issues`, `typed_fields`.
        """
        yield from self._stream_internal(pdf_path, lang=lang)

    # ------------------------------------------------------------ internals

    def _stream_internal(
        self,
        pdf_path: str | Path,
        *,
        lang: str,
    ) -> Iterator[PipelineStep]:
        emitter = StepEmitter(lang=lang, callback=self.step_callback)

        yield emitter.emit("start", "system")

        self._last_cache_key = self._cache_key(pdf_path)
        cached = self._cache_get(self._last_cache_key)
        yield emitter.emit(
            "cache_check",
            "system",
            payload={"cache_enabled": self.cache is not None, "hit": cached is not None},
        )

        if cached is not None:
            yield from stream_cache_hit(emitter, cached)
            return

        fusion = yield from stream_extract(self, pdf_path, emitter)
        parsed, llm_calls, context = yield from stream_llm(self, emitter, fusion)
        yield from stream_bind_and_type(self, emitter, fusion, parsed, llm_calls, context)

    # --------------------------------------------------------- LLM helpers

    def _fuse(self, pdf_path: str | Path) -> FusionResult:
        if self._fuse_fn is not None:
            return self._fuse_fn(pdf_path)
        from ..fusion import fuse  # lazy: avoid importing engines at module load

        return fuse(pdf_path)

    def _call_llm(self, system: str, user: str) -> LLMResponse:
        return self.retry.call(
            lambda: self.llm.complete(system, user, response_format={"type": "json_object"})
        )

    def _maybe_reprompt(
        self,
        bound: list[BoundValue],
        fusion: FusionResult,
        context: dict[str, Any],
        llm_calls: list[LLMResponse],
    ) -> tuple[list[BoundValue], list[LLMResponse]]:
        """Optionally re-prompt for hallucinations / low-confidence fields."""
        hallucinated = tuple(bv.field_name for bv in bound if bv.match_method == "not_found")
        low_conf = ()
        if self.on_low_confidence_field > 0:
            low_conf = tuple(
                bv.field_name
                for bv in bound
                if bv.match_method != "not_found" and bv.match_score < self.on_low_confidence_field
            )

        needs_rerun = (self.on_hallucination == "retry_llm" and hallucinated) or low_conf
        if not needs_rerun:
            return bound, llm_calls

        prompt = build_reprompt(
            self.schema, context, hallucinated=hallucinated, low_confidence=low_conf
        )
        response = self._call_llm(SYSTEM_PROMPT, prompt)
        llm_calls.append(response)
        parsed = parse_json(response.text)
        bound = bind_provenance(parsed, list(fusion.items))
        return bound, llm_calls

    # --------------------------------------------------------------- cache

    def _cache_key(self, pdf_path: str | Path) -> str | None:
        if self.cache is None:
            return None
        return build_cache_key(pdf_path, repr(self.schema), llm_id(self.llm))

    def _cache_get(self, key: str | None) -> ExtractionResult | None:
        if self.cache is None or key is None:
            return None
        return self.cache.get(key)

    def _cache_set(self, key: str | None, value: ExtractionResult) -> None:
        if self.cache is None or key is None:
            return
        self.cache.set(key, value)


__all__ = ["Pipeline"]
