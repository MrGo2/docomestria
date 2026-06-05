"""Deterministic extraction — no LLM, no API keys, free and instant.

Best for structured forms with clear labels (Apellidos:, NIF:, ...) and
visual boxes. For free-text contracts or scanned PDFs, use the LLM mode
in `openrouter_pipeline.py` instead.
"""

from __future__ import annotations

import sys

from docomestria import Pipeline
from docomestria.transform import Field, Schema
from docomestria.transform import transformers as tr


def main(pdf_path: str) -> None:
    schema = Schema(
        {
            "fecha_contrato": Field(tr.date_es_long, labels=("Fecha",)),
            "datos_titular.apellidos": Field(tr.regex(r"^[A-ZÀ-Ú ]+$"), labels=("Apellidos",)),
            "datos_titular.nombre": Field(tr.regex(r"^[A-ZÀ-Ú ]+$"), labels=("Nombre",)),
            "datos_titular.nif": Field(tr.nif_es, labels=("NIF", "DNI")),
            "datos_titular.cp": Field(tr.postal_code_es, labels=("C.P.", "CP", "Código postal")),
            "datos_titular.vivienda": Field(
                tr.checkbox_choice(["propia", "alquiler", "padres", "otros"]),
                labels=("Vivienda",),
            ),
            "datos_titular.sexo": Field(tr.checkbox_binary("V", "H"), labels=("Sexo",)),
        }
    )

    pipe = Pipeline(schema=schema, llm=None)  # deterministic
    result = pipe.run(pdf_path)

    print(f"Mode: deterministic | Duration: {result.duration_ms} ms | Cost: $0.00")
    print()
    for key, tv in result.typed_fields.items():
        status = " " if not tv.issues else f" [{','.join(tv.issues)}]"
        print(f"  {key}: {tv.normalized}{status}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python deterministic_extraction.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
