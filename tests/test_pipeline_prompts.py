"""Tests for prompt builders — verifies schema field inclusion."""

from __future__ import annotations

import pytest

pytest.importorskip("stdnum", reason="transform layer depends on stdnum")

from docomestria.pipeline.prompts import (  # noqa: E402
    SYSTEM_PROMPT,
    build_extraction_prompt,
    build_reprompt,
)
from docomestria.transform import Field, Schema  # noqa: E402
from docomestria.transform import transformers as tr  # noqa: E402


def _schema() -> Schema:
    return Schema(
        {
            "nif": Field(tr.nif_es, required=True),
            "fecha": Field(tr.date_es_long, description="Fecha del contrato"),
        }
    )


def test_system_prompt_mentions_json():
    assert "JSON" in SYSTEM_PROMPT


def test_extraction_prompt_lists_each_schema_field():
    prompt = build_extraction_prompt(_schema(), {"sections": []})
    assert "nif" in prompt
    assert "fecha" in prompt
    assert "required" in prompt
    assert "Fecha del contrato" in prompt


def test_extraction_prompt_embeds_context_json():
    ctx = {"sections": [{"title": "S", "items": [{"i": 0, "t": "hi"}]}]}
    prompt = build_extraction_prompt(_schema(), ctx)
    assert '"title": "S"' in prompt
    assert '"hi"' in prompt


def test_reprompt_lists_hallucinated_fields():
    prompt = build_reprompt(
        _schema(),
        {"sections": []},
        hallucinated=("nif",),
        low_confidence=("fecha",),
    )
    assert "nif" in prompt
    assert "fecha" in prompt
    assert "could not be found" in prompt
    assert "weak match" in prompt
