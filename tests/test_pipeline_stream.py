"""Tests for `Pipeline.stream()` — step-by-step observable execution."""

from __future__ import annotations

import json

import pytest

from docomestria import BBox, FusedItem
from docomestria.result import FusionResult

pytest.importorskip("rapidfuzz")

from docomestria.pipeline import (  # noqa: E402
    ExtractionResult,
    MemoryCache,
    Pipeline,
    PipelineStep,
)
from docomestria.pipeline.providers.base import LLMResponse  # noqa: E402
from docomestria.pipeline.step import TOTAL_STEPS, explanation_for  # noqa: E402
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


def _pdf(tmp_path) -> str:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return pdf


def test_stream_yields_expected_steps_in_order(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)

    steps = list(pipe.stream(_pdf(tmp_path)))
    names = [s.name for s in steps]

    # With a fuse_fn stub we get the bundled extract_all path.
    assert names == [
        "start",
        "cache_check",
        "extract_all",
        "fuse",
        "build_context",
        "llm_call",
        "parse_response",
        "bind_provenance",
        "detect_issues",
        "apply_schema",
        "complete",
    ]


def test_stream_step_index_and_total_are_consistent(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)

    steps = list(pipe.stream(_pdf(tmp_path)))
    for i, step in enumerate(steps, start=1):
        assert step.step_index == i
        assert step.total_steps == TOTAL_STEPS
        assert 0.0 < step.progress <= step.step_index / TOTAL_STEPS + 1e-9


def test_stream_cumulative_ms_monotonic(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)

    steps = list(pipe.stream(_pdf(tmp_path)))
    cumulatives = [s.cumulative_ms for s in steps]
    assert cumulatives == sorted(cumulatives)


def test_stream_terminal_step_carries_full_state(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)

    steps = list(pipe.stream(_pdf(tmp_path)))
    terminal = steps[-1]

    assert terminal.is_terminal is True
    assert terminal.name == "complete"
    assert terminal.fusion is not None
    assert terminal.bound is not None and len(terminal.bound) > 0
    assert terminal.issues is not None
    assert terminal.typed_fields is not None
    assert "nif" in terminal.typed_fields


def test_stream_cache_hit_short_circuits(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    cache = MemoryCache()
    pipe = _pipeline(provider, cache=cache)

    pdf = _pdf(tmp_path)

    # First run populates the cache.
    list(pipe.stream(pdf))

    # Second run should short-circuit: start → cache_check → cache_hit → complete.
    steps2 = list(pipe.stream(pdf))
    names = [s.name for s in steps2]
    assert names == ["start", "cache_check", "cache_hit", "complete"]
    assert steps2[-1].is_terminal is True
    assert steps2[-1].typed_fields is not None


def test_stream_english_explanations(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)

    steps = list(pipe.stream(_pdf(tmp_path), lang="en"))
    start = next(s for s in steps if s.name == "start")
    assert start.explanation == explanation_for("start", "en")
    assert "PDF received" in start.explanation


def test_stream_spanish_default(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)

    steps = list(pipe.stream(_pdf(tmp_path)))
    start = next(s for s in steps if s.name == "start")
    assert "PDF" in start.explanation
    assert start.explanation == explanation_for("start", "es")


def test_step_callback_fires_once_per_step(tmp_path):
    seen: list[PipelineStep] = []
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider, step_callback=seen.append)

    steps = list(pipe.stream(_pdf(tmp_path)))
    assert len(seen) == len(steps)
    assert [s.name for s in seen] == [s.name for s in steps]


def test_step_callback_fires_for_run(tmp_path):
    seen: list[str] = []
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider, step_callback=lambda s: seen.append(s.name))

    pipe.run(_pdf(tmp_path))
    assert "start" in seen
    assert "complete" in seen


def test_run_still_returns_extraction_result(tmp_path):
    """Regression: `run()` API surface must match v0.4.0."""
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)

    result = pipe.run(_pdf(tmp_path))

    assert isinstance(result, ExtractionResult)
    assert result.typed_fields["nif"].normalized == "51789286W"
    assert result.cost.usd == pytest.approx(0.001)
    assert result.cost.tokens_in == 100
    assert result.cost.model_used == "mock-model"
    assert result.cache_hit is False
    assert result.llm_calls == 1


def test_run_cache_hit_marks_result(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    cache = MemoryCache()
    pipe = _pipeline(provider, cache=cache)

    pdf = _pdf(tmp_path)
    pipe.run(pdf)
    result2 = pipe.run(pdf)

    assert result2.cache_hit is True
    assert result2.typed_fields["nif"].normalized == "51789286W"


def test_stream_bind_provenance_carries_bboxes(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)

    steps = list(pipe.stream(_pdf(tmp_path)))
    bind = next(s for s in steps if s.name == "bind_provenance")
    assert len(bind.bboxes) >= 1
    assert all(isinstance(b, BBox) for b in bind.bboxes)


def test_stream_payload_includes_samples(tmp_path):
    provider = MockProvider({"nif": "51789286W"})
    pipe = _pipeline(provider)

    steps = list(pipe.stream(_pdf(tmp_path)))
    fuse_step = next(s for s in steps if s.name == "fuse")
    assert fuse_step.payload["items_count"] == 2
    assert "sample_texts" in fuse_step.payload


# --------------------------------------------------------------------------- v0.6.2: rich extract payloads


def test_stream_extract_steps_include_raw_payload(tmp_path, monkeypatch):
    """extract_liteparse / extract_docling / extract_pdfplumber expose `_text_items`
    / `_blocks` / `_rects` for the studio UI."""
    from docomestria import BBox, DoclingBlock, LiteItem, VisualRect
    from docomestria.fusion import FusionStats
    from docomestria.pipeline import _stream

    lite_items = [
        LiteItem(
            text="HELLO",
            bbox=BBox(x=10, y=20, w=40, h=10),
            font_name="Helvetica-Bold",
            font_size=12.0,
            page=1,
        )
    ]
    docling_blocks = [
        DoclingBlock(
            bbox=BBox(x=5, y=5, w=200, h=300),
            label="section_header",
            heading_level=1,
            content_layer="body",
            page=1,
            text="DATOS",
            self_ref="ref-1",
        )
    ]
    rects = [
        VisualRect(
            bbox=BBox(x=8, y=8, w=10, h=10),
            is_checkbox=True,
            is_filled=True,
            page=1,
            rect_id="rect_0",
            rect_type="checkbox",
        )
    ]

    monkeypatch.setattr("docomestria.engines.extract_lite_items", lambda _p: lite_items)
    monkeypatch.setattr(
        "docomestria.engines.extract_docling_blocks", lambda _p: docling_blocks
    )
    monkeypatch.setattr(
        "docomestria.engines.extract_visual_rects", lambda _p: rects
    )

    def _fake_fuse(_lite, _doc, _rects):
        return FusionStats(
            items=(),
            coverage=0.0,
            matched_to_docling=0,
            matched_to_box=0,
            total_items=0,
        )

    monkeypatch.setattr("docomestria.fusion.fuse_from_engines", _fake_fuse)

    # Build a pipeline with NO fuse_fn so the per-engine extract path runs.
    provider = MockProvider({"nif": "51789286W"})
    pipe = Pipeline(schema=_schema(), llm=provider, cache_dir=None)

    pdf = _pdf(tmp_path)
    from docomestria.pipeline._helpers import StepEmitter

    emitter = StepEmitter(lang="es", callback=None, total_steps=13)
    steps = list(_stream.stream_extract(pipe, pdf, emitter))

    by_name = {s.name: s for s in steps}
    assert "extract_liteparse" in by_name
    assert "extract_docling" in by_name
    assert "extract_pdfplumber" in by_name

    text_items = by_name["extract_liteparse"].payload["_text_items"]
    assert isinstance(text_items, list) and len(text_items) == 1
    assert text_items[0]["text"] == "HELLO"
    assert text_items[0]["font"] == "Helvetica-Bold"
    assert text_items[0]["size"] == 12.0
    assert text_items[0]["bbox"] == [10.0, 20.0, 40.0, 10.0]

    blocks = by_name["extract_docling"].payload["_blocks"]
    assert isinstance(blocks, list) and len(blocks) == 1
    assert blocks[0]["label"] == "section_header"
    assert blocks[0]["level"] == 1
    assert blocks[0]["layer"] == "body"

    rects_payload = by_name["extract_pdfplumber"].payload["_rects"]
    assert isinstance(rects_payload, list) and len(rects_payload) == 1
    assert rects_payload[0]["rect_type"] == "checkbox"
    assert rects_payload[0]["is_filled"] is True
    assert rects_payload[0]["rect_id"] == "rect_0"


# --------------------------------------------------------------------------- v0.6.3: table cells + contained_text


def test_stream_blocks_payload_carries_cells_for_tables(tmp_path, monkeypatch):
    """A Docling block of label='table' surfaces `cells` matrix in the payload."""
    from docomestria import BBox, DoclingBlock, LiteItem, VisualRect
    from docomestria.fusion import FusionStats
    from docomestria.pipeline import _stream

    cells = (
        ("", "Datos Petición", ""),
        ("Nº Procedimiento", "987-15", ""),
    )
    docling_blocks = [
        DoclingBlock(
            bbox=BBox(x=10, y=10, w=300, h=200),
            label="table",
            heading_level=None,
            content_layer="body",
            page=1,
            text="",
            self_ref="ref-t",
            cells=cells,
        )
    ]

    monkeypatch.setattr("docomestria.engines.extract_lite_items", lambda _p: [])
    monkeypatch.setattr(
        "docomestria.engines.extract_docling_blocks", lambda _p: docling_blocks
    )
    monkeypatch.setattr("docomestria.engines.extract_visual_rects", lambda _p: [])
    monkeypatch.setattr(
        "docomestria.fusion.fuse_from_engines",
        lambda _l, _d, _r: FusionStats(
            items=(), coverage=0.0, matched_to_docling=0, matched_to_box=0, total_items=0
        ),
    )

    provider = MockProvider({"nif": "51789286W"})
    pipe = Pipeline(schema=_schema(), llm=provider, cache_dir=None)
    pdf = _pdf(tmp_path)
    from docomestria.pipeline._helpers import StepEmitter

    emitter = StepEmitter(lang="es", callback=None, total_steps=13)
    steps = list(_stream.stream_extract(pipe, pdf, emitter))
    by_name = {s.name: s for s in steps}

    blocks = by_name["extract_docling"].payload["_blocks"]
    assert blocks[0]["label"] == "table"
    assert blocks[0]["cells"] == [
        ["", "Datos Petición", ""],
        ["Nº Procedimiento", "987-15", ""],
    ]
    # Tables don't get contained_text — they have cells instead.
    assert "contained_text" not in blocks[0]


def test_stream_blocks_payload_carries_contained_text_for_headers(tmp_path, monkeypatch):
    """A non-table block surfaces `contained_text` from LiteParse items inside its bbox."""
    from docomestria import BBox, DoclingBlock, LiteItem
    from docomestria.fusion import FusionStats
    from docomestria.pipeline import _stream

    lite_items = [
        LiteItem(
            text="Consulta",
            bbox=BBox(x=20, y=20, w=40, h=10),
            font_name="Helvetica",
            font_size=10.0,
            page=1,
        ),
        LiteItem(
            text="TGSS",
            bbox=BBox(x=70, y=20, w=30, h=10),
            font_name="Helvetica",
            font_size=10.0,
            page=1,
        ),
        LiteItem(
            text="outside",
            bbox=BBox(x=500, y=500, w=20, h=10),
            font_name="Helvetica",
            font_size=10.0,
            page=1,
        ),
    ]
    docling_blocks = [
        DoclingBlock(
            bbox=BBox(x=10, y=10, w=200, h=30),
            label="section_header",
            heading_level=1,
            content_layer="body",
            page=1,
            text="Consulta TGSS",
            self_ref="ref-h",
        )
    ]

    monkeypatch.setattr("docomestria.engines.extract_lite_items", lambda _p: lite_items)
    monkeypatch.setattr(
        "docomestria.engines.extract_docling_blocks", lambda _p: docling_blocks
    )
    monkeypatch.setattr("docomestria.engines.extract_visual_rects", lambda _p: [])
    monkeypatch.setattr(
        "docomestria.fusion.fuse_from_engines",
        lambda _l, _d, _r: FusionStats(
            items=(), coverage=0.0, matched_to_docling=0, matched_to_box=0, total_items=0
        ),
    )

    provider = MockProvider({"nif": "51789286W"})
    pipe = Pipeline(schema=_schema(), llm=provider, cache_dir=None)
    pdf = _pdf(tmp_path)
    from docomestria.pipeline._helpers import StepEmitter

    emitter = StepEmitter(lang="es", callback=None, total_steps=13)
    steps = list(_stream.stream_extract(pipe, pdf, emitter))
    by_name = {s.name: s for s in steps}

    blocks = by_name["extract_docling"].payload["_blocks"]
    assert blocks[0]["label"] == "section_header"
    assert blocks[0]["contained_text"] == "Consulta TGSS"
    assert "cells" not in blocks[0]


def test_stream_rects_payload_carries_cells_for_tables(tmp_path, monkeypatch):
    """A pdfplumber rect of type 'table' surfaces `cells` matrix in the payload."""
    from docomestria import BBox, VisualRect
    from docomestria.fusion import FusionStats
    from docomestria.pipeline import _stream

    cells = (
        ("Header A", "Header B"),
        ("v1", "v2"),
    )
    rects = [
        VisualRect(
            bbox=BBox(x=10, y=10, w=200, h=100),
            is_checkbox=False,
            is_filled=False,
            page=1,
            rect_id="p1-t0",
            rect_type="table",
            cells=cells,
        )
    ]

    monkeypatch.setattr("docomestria.engines.extract_lite_items", lambda _p: [])
    monkeypatch.setattr("docomestria.engines.extract_docling_blocks", lambda _p: [])
    monkeypatch.setattr("docomestria.engines.extract_visual_rects", lambda _p: rects)
    monkeypatch.setattr(
        "docomestria.fusion.fuse_from_engines",
        lambda _l, _d, _r: FusionStats(
            items=(), coverage=0.0, matched_to_docling=0, matched_to_box=0, total_items=0
        ),
    )

    provider = MockProvider({"nif": "51789286W"})
    pipe = Pipeline(schema=_schema(), llm=provider, cache_dir=None)
    pdf = _pdf(tmp_path)
    from docomestria.pipeline._helpers import StepEmitter

    emitter = StepEmitter(lang="es", callback=None, total_steps=13)
    steps = list(_stream.stream_extract(pipe, pdf, emitter))
    by_name = {s.name: s for s in steps}

    rects_payload = by_name["extract_pdfplumber"].payload["_rects"]
    assert rects_payload[0]["rect_type"] == "table"
    assert rects_payload[0]["cells"] == [["Header A", "Header B"], ["v1", "v2"]]
    assert "contained_text" not in rects_payload[0]
