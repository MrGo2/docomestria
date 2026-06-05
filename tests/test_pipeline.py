"""End-to-end Pipeline tests using a mock LLM provider and a stub fuse."""

from __future__ import annotations

import json

import pytest

from docomestria import BBox, FusedItem
from docomestria.result import FusionResult

pytest.importorskip("rapidfuzz")

from docomestria.pipeline import ExtractionResult, Pipeline  # noqa: E402
from docomestria.pipeline.providers.base import LLMResponse  # noqa: E402
from docomestria.transform import Field, Schema  # noqa: E402
from docomestria.transform import transformers as tr  # noqa: E402


def _fi(text: str, x: float = 100.0, y: float = 100.0) -> FusedItem:
    return FusedItem(
        text=text,
        bbox=BBox(x=x, y=y, w=80.0, h=12.0),
        font_name="Helvetica",
        font_size=10.0,
        docling_label="text",
        docling_heading_level=None,
        enclosing_box_id="box-a",
        section_title="DATOS PERSONALES",
        page=1,
        match_method="centroid",
        match_score=1.0,
    )


def _fusion() -> FusionResult:
    items = (_fi("CLAUDIO ALEJANDRO", y=100), _fi("51789286W", y=120))
    return FusionResult(
        items=items,
        lite_items=(),
        docling_blocks=(),
        visual_rects=(),
        coverage=1.0,
        matched_to_docling=0,
        matched_to_box=0,
        total_items=len(items),
    )


class MockProvider:
    """Returns a canned JSON response and reports preset cost/tokens."""

    model = "mock-model"

    def __init__(self, payload: dict[str, str], *, usd: float = 0.001) -> None:
        self.payload = payload
        self.usd = usd
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, *, response_format=None) -> LLMResponse:
        self.calls.append((system, user))
        return LLMResponse(
            text=json.dumps(self.payload),
            model_used=self.model,
            tokens_in=100,
            tokens_out=20,
            usd=self.usd,
            raw_response={"ok": True},
        )


def _schema() -> Schema:
    return Schema({"nif": Field(tr.nif_es)})


def _pipeline(provider: MockProvider, **kwargs) -> Pipeline:
    return Pipeline(
        schema=_schema(),
        llm=provider,
        cache_dir=None,
        fuse_fn=lambda _p: _fusion(),
        **kwargs,
    )


def test_pipeline_run_happy_path(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    result = pipe.run(pdf)

    assert isinstance(result, ExtractionResult)
    assert result.typed_fields["nif"].normalized == "51789286W"
    assert result.cost.usd == pytest.approx(0.001)
    assert result.cost.tokens_in == 100
    assert result.cost.model_used == "mock-model"
    assert result.cache_hit is False
    assert result.llm_calls == 1
    assert provider.calls and "DATOS PERSONALES" in provider.calls[0][1]


def test_pipeline_flags_hallucination_by_default(tmp_path):
    provider = MockProvider({"nif": "DOESNOTEXIST"})
    pipe = _pipeline(provider)
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    result = pipe.run(pdf)

    assert any(iss.issue_type == "hallucination" for iss in result.issues)


def test_pipeline_drop_policy_removes_hallucinations(tmp_path):
    provider = MockProvider({"nif": "DOESNOTEXIST"})
    pipe = _pipeline(provider, on_hallucination="drop")
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    result = pipe.run(pdf)

    assert all(iss.issue_type != "hallucination" for iss in result.issues)
    assert all(bv.match_method != "not_found" for bv in result.bound)


def test_pipeline_retry_llm_policy_makes_second_call(tmp_path):
    provider = MockProvider({"nif": "INVENTED"})
    pipe = _pipeline(provider, on_hallucination="retry_llm")
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    result = pipe.run(pdf)

    assert result.llm_calls == 2
    assert len(provider.calls) == 2
