"""Cache hit/miss tests for Pipeline using MemoryCache."""

from __future__ import annotations

import json

import pytest

from docomestria import BBox, FusedItem
from docomestria.result import FusionResult

pytest.importorskip("rapidfuzz")

from docomestria.pipeline import MemoryCache, Pipeline  # noqa: E402
from docomestria.pipeline.providers.base import LLMResponse  # noqa: E402
from docomestria.transform import Field, Schema  # noqa: E402
from docomestria.transform import transformers as tr  # noqa: E402


def _fi(text: str, y: float = 100.0) -> FusedItem:
    return FusedItem(
        text=text,
        bbox=BBox(x=100, y=y, w=80.0, h=12.0),
        font_name="Helvetica",
        font_size=10.0,
        docling_label="text",
        docling_heading_level=None,
        enclosing_box_id=None,
        section_title="S",
        page=1,
        match_method="centroid",
        match_score=1.0,
    )


def _fusion() -> FusionResult:
    items = (_fi("51789286W"),)
    return FusionResult(
        items=items,
        lite_items=(),
        docling_blocks=(),
        visual_rects=(),
        coverage=1.0,
        matched_to_docling=0,
        matched_to_box=0,
        total_items=1,
    )


class CountingProvider:
    model = "mock-model"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system, user, *, response_format=None) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            text=json.dumps({"nif": "51789286W"}),
            model_used=self.model,
            tokens_in=10,
            tokens_out=2,
            usd=0.0001,
        )


def test_memory_cache_hit_skips_llm(tmp_path):
    provider = CountingProvider()
    cache = MemoryCache()
    pipe = Pipeline(
        schema=Schema({"nif": Field(tr.nif_es)}),
        llm=provider,
        cache=cache,
        cache_dir=None,
        fuse_fn=lambda _p: _fusion(),
    )
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    r1 = pipe.run(pdf)
    r2 = pipe.run(pdf)

    assert provider.calls == 1
    assert r1.cache_hit is False
    assert r2.cache_hit is True
    assert r2.typed_fields["nif"].normalized == "51789286W"


def test_memory_cache_miss_on_different_pdf(tmp_path):
    provider = CountingProvider()
    cache = MemoryCache()
    pipe = Pipeline(
        schema=Schema({"nif": Field(tr.nif_es)}),
        llm=provider,
        cache=cache,
        cache_dir=None,
        fuse_fn=lambda _p: _fusion(),
    )
    p1 = tmp_path / "a.pdf"
    p2 = tmp_path / "b.pdf"
    p1.write_bytes(b"%PDF-A")
    p2.write_bytes(b"%PDF-B")

    pipe.run(p1)
    pipe.run(p2)

    assert provider.calls == 2
