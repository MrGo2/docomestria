"""End-to-end extraction with OpenRouter as the LLM provider.

OpenRouter gives you access to 200+ models with one API key plus built-in
fallback routing. This is the recommended default for new projects.

Setup:
    1. Sign up at https://openrouter.ai and get an API key
    2. Add credits (a few dollars goes a long way with Gemini Flash Lite)
    3. export OPENROUTER_API_KEY=...
    4. pip install docomestria[openrouter,transform,llm,pipeline]
    5. python examples/openrouter_pipeline.py path/to/contract.pdf
"""

from __future__ import annotations

import os
import sys

from docomestria.pipeline import Pipeline, RetryPolicy
from docomestria.pipeline.providers import OpenRouter
from docomestria.transform import Field, Schema
from docomestria.transform import transformers as tr


def main(pdf_path: str) -> None:
    schema = Schema(
        {
            "fecha_contrato": Field(tr.date_es_long),
            "datos_titular.apellidos": Field(tr.regex(r"^[A-ZÀ-Ú ]+$")),
            "datos_titular.nombre": Field(tr.regex(r"^[A-ZÀ-Ú ]+$")),
            "datos_titular.nif": Field(tr.nif_es),
            "datos_titular.fecha_nacimiento": Field(tr.date_es_short),
            "datos_titular.telefono_movil": Field(tr.phone_es),
            "datos_titular.email": Field(tr.email),
            "datos_titular.cp": Field(tr.postal_code_es),
            "datos_titular.vivienda": Field(
                tr.checkbox_choice(["propia", "alquiler", "padres", "otros"])
            ),
            "datos_titular.sexo": Field(tr.checkbox_binary("V", "H")),
        }
    )

    llm = OpenRouter(
        api_key=os.environ["OPENROUTER_API_KEY"],
        models=(
            "google/gemini-2.5-flash-lite",  # cheapest, primary
            "anthropic/claude-haiku-4.5",  # fallback if Google fails
        ),
        route="fallback",
    )

    pipe = Pipeline(
        schema=schema,
        llm=llm,
        cache_dir=".docomestria_cache",
        retry=RetryPolicy(max_retries=3),
    )

    extraction = pipe.run(pdf_path)

    print(f"Model used: {extraction.cost.model_used}")
    print(f"Cost: ${extraction.cost.usd:.6f}")
    print(f"Duration: {extraction.duration_ms} ms (cache: {extraction.cache_hit})")
    print()

    for field_key, tv in extraction.typed_fields.items():
        marker = " " if not tv.issues else " [" + ",".join(tv.issues) + "]"
        print(f"  {field_key}: {tv.normalized}{marker}")

    if extraction.issues:
        print("\nProvenance issues:")
        for issue in extraction.issues:
            print(f"  [{issue.severity}] {issue.field_name}: {issue.detail}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python openrouter_pipeline.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
