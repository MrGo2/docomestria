"""End-to-end Spanish-form scenario: fuse, bind, type, and audit.

Works with any LLM. The LLM output here is a placeholder dict.
Run with: `uv run examples/typed_extraction.py path/to/contract.pdf`
"""

from __future__ import annotations

import sys
from pathlib import Path

from docomestria import fuse
from docomestria.llm import bind_provenance
from docomestria.transform import Field, Schema
from docomestria.transform import transformers as tr


def main(pdf_path: Path) -> int:
    # 1. Fuse all three engines.
    result = fuse(str(pdf_path))
    print(
        f"fused {result.total_items} items "
        f"({result.matched_to_docling} docling, {result.matched_to_box} boxes)"
    )

    # 2. Placeholder LLM output — replace with your own model call.
    llm_output = {
        "fecha_contrato": "06 de Diciembre",
        "datos_titular": {
            "apellidos": "ZAIDAN HASSAN",
            "nombre": "CLAUDIO ALEJANDRO",
            "nif": "51789286W",
            "fecha_nacimiento": "03/11/71",
            "telefono_movil": "659390517",
            "email": "TANGOTAN22@HOTMAIL.COM",
            "cp": "28026",
            "vivienda": "alquiler",
            "sexo": "V",
        },
    }

    # 3. Bind values to PDF provenance.
    bound = bind_provenance(llm_output, list(result.items))

    # 4. Type and validate.
    schema = Schema(
        {
            "fecha_contrato": Field(tr.date_es_long),
            "datos_titular.apellidos": Field(tr.regex(r"^[A-ZÀ-Ú ]+$")),
            "datos_titular.nombre": Field(tr.regex(r"^[A-ZÀ-Ú ]+$")),
            "datos_titular.nif": Field(tr.nif_es, required=True),
            "datos_titular.fecha_nacimiento": Field(tr.date_es_short),
            "datos_titular.telefono_movil": Field(tr.phone_es),
            "datos_titular.email": Field(tr.email),
            "datos_titular.cp": Field(tr.postal_code_es),
            "datos_titular.vivienda": Field(
                tr.checkbox_choice(
                    [
                        "propia",
                        "alquiler",
                        "padres",
                        "otros",
                    ]
                )
            ),
            "datos_titular.sexo": Field(tr.checkbox_binary("V", "H")),
        }
    )

    typed = schema.apply(bound, result)

    print("\n=== typed values ===")
    for name, tv in typed.items():
        flag = "ok" if tv.ok else f"issues={list(tv.issues)}"
        print(f"  {name:<36}  {tv.normalized!r:<32}  conf={tv.confidence:.2f}  {flag}")

    # 5. Audit one value end-to-end.
    nif = typed.get("datos_titular.nif")
    if nif is None:
        return 0
    trace = nif.trace(result)
    print("\n=== provenance for datos_titular.nif ===")
    print(f"  value     : {nif.normalized}  (valid: {nif.ok})")
    print(f"  bbox      : {nif.bbox}")
    print(f"  page      : {nif.page}")
    if trace.chains:
        ch = trace.chains[0]
        font = ch.lite_items[0].font_name if ch.lite_items else None
        size = ch.lite_items[0].font_size if ch.lite_items else None
        label = ch.docling_block.label if ch.docling_block else None
        box_id = ch.visual_box.rect_id if ch.visual_box else None
        print(f"  font      : {font} {size}pt")
        print(f"  role      : {label}")
        print(f"  visual box: {box_id}")
        print(f"  section   : {' > '.join(ch.section_path) or '(none)'}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: typed_extraction.py <pdf>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(Path(sys.argv[1])))
