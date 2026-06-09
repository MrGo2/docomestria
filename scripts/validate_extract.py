"""End-to-end validation of `structural_extract` against cached engine outputs.

Loads pre-saved Docling / LiteParse / pdfplumber outputs from
`data/parsebench/outputs/`, runs `structural_extract_from_engines()`, and
prints every emitted Pair with its score, confidence, evidence, and section
context. Also checks each PDF's regression cases from the strategy doc and
reports PASS/FAIL.

Usage:
    python scripts/validate_extract.py azuredemo__LABORAL
    python scripts/validate_extract.py azuredemo__PATRIMONIAL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from docomestria.models import BBox, DoclingBlock, LiteItem, VisualRect
from docomestria.structural import Pair, structural_extract_from_engines

ROOT = Path(__file__).resolve().parent.parent / "data" / "parsebench" / "outputs"


def _bbox(d: dict) -> BBox:
    return BBox(x=d["x"], y=d["y"], w=d["w"], h=d["h"])


def load_docling(stem: str) -> list[DoclingBlock]:
    payload = json.loads((ROOT / "docling" / f"{stem}.json").read_text())
    out = []
    for it in payload["items"]:
        cells = it.get("cells")
        out.append(
            DoclingBlock(
                bbox=_bbox(it["bbox"]),
                label=it["label"],
                heading_level=it.get("heading_level"),
                content_layer=it.get("content_layer", "body"),
                page=it["page"],
                text=it.get("text") or "",
                self_ref=it.get("self_ref"),
                cells=tuple(tuple(r) for r in cells) if cells else None,
            )
        )
    return out


def load_lite(stem: str) -> list[LiteItem]:
    payload = json.loads((ROOT / "liteparse" / f"{stem}.json").read_text())
    return [
        LiteItem(
            text=it["text"],
            bbox=_bbox(it["bbox"]),
            font_name=it.get("font_name"),
            font_size=it.get("font_size"),
            page=it["page"],
        )
        for it in payload["items"]
    ]


def load_plumber(stem: str) -> list[VisualRect]:
    payload = json.loads((ROOT / "pdfplumber" / f"{stem}.json").read_text())
    out = []
    for it in payload["items"]:
        cells = it.get("cells")
        out.append(
            VisualRect(
                bbox=_bbox(it["bbox"]),
                is_checkbox=it.get("is_checkbox", False),
                is_filled=it.get("is_filled", False),
                page=it["page"],
                rect_id=it.get("rect_id", ""),
                rect_type=it.get("rect_type", "box"),
                cells=tuple(tuple(r) for r in cells) if cells else None,
            )
        )
    return out


# Each entry: (label_text_must_match, expected_value_predicate)
# Predicate is either an exact string (case-insensitive), a "contains:..."
# prefix, or "empty" for an empty value.
REGRESSION_CASES: dict[str, list[tuple[str, str]]] = {
    "azuredemo__LABORAL": [
        ("CCC:", "empty"),
        ("Razón Social/Convenio/Régimen:", "contains:RGIMEN ESPECIAL"),
        ("Titular:", "contains:GHEORGHE ADRIAN OPREA"),
        ("Nº Seguridad Social:", "exact:341005311371"),
        ("Situación actual:", "exact:BAJA"),
        ("Fecha Situación:", "exact:31.05.2019"),
        ("NIF/CIF - Domicilio de Empresa:", "exact:No Consta"),
        ("Fecha Alta:", "exact:10.04.2018"),
        ("Tipo Contrato:", "empty"),
        ("Grupo Cotización:", "empty"),
        ("Nº Procedimiento", "exact:987-15"),
        ("Nº Documento", "exact:X6573514E"),
    ],
    "azuredemo__PATRIMONIAL": [
        ("AEAT - Consulta Percepciones:", "contains:0001 Operación Correcta"),
        ("AEAT - Consulta Actividades Economicas:", "contains:0001 Operación Correcta"),
        ("AEAT - CuentasAmpliadas (mod. 196):", "contains:0001 Operación Correcta"),
        ("Nombre:", "exact:GHEORGHE ADRIAN"),
        ("Primer Apellido:", "exact:OPREA"),
        ("DNI:", "exact:X6573514E"),
        ("Nacionalidad:", "exact:RUMANIA"),
        ("Nº Procedimiento", "exact:987/2015"),
    ],
}


def _check(pairs: list[Pair], label_key: str, predicate: str) -> tuple[bool, str]:
    """Find a Pair whose label_text matches label_key and check value.

    Prefer EXACT match (case-insensitive, ignoring trailing colon). Fall back
    to substring containment only if no exact match exists.
    """
    norm_key = label_key.lower().rstrip(":").strip()
    exact = [
        p for p in pairs
        if p.label_text.lower().rstrip(":").strip() == norm_key
    ]
    matches = exact or [
        p for p in pairs if label_key.lower() in p.label_text.lower()
    ]
    if not matches:
        return False, "<no matching label>"
    observed = matches[0].value_text
    if predicate == "empty":
        return observed.strip() == "", observed
    if predicate.startswith("exact:"):
        return observed.strip() == predicate[len("exact:") :], observed
    if predicate.startswith("contains:"):
        return predicate[len("contains:") :].lower() in observed.lower(), observed
    return False, observed


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_extract.py <stem>")
        print("Available:")
        for k in REGRESSION_CASES:
            print(f"  {k}")
        sys.exit(1)
    stem = sys.argv[1].removesuffix(".pdf")

    d, l, p = load_docling(stem), load_lite(stem), load_plumber(stem)
    result = structural_extract_from_engines(d, l, p)
    print(f"=== {stem} ===")
    print(f"  Pages: {len(result.pages)}  Pairs: {len(result.pairs)}  "
          f"Classified items: {len(result.classified)}")
    print()

    # Print every pair, grouped by page.
    current_page = None
    for pair in result.pairs:
        if pair.page != current_page:
            current_page = pair.page
            print(f"\n--- Page {pair.page} ---")
        marker = {"high": "★", "medium": "·", "low": "?"}.get(pair.confidence.value, " ")
        ctx = ""
        if pair.subsection_title:
            ctx = f"  [{pair.subsection_title}]"
        elif pair.section_title:
            ctx = f"  ({pair.section_title})"
        print(f"  {marker} {pair.score:.2f} {pair.confidence.value:6s}  "
              f"{pair.label_text!r:50s} → {pair.value_text!r:50s}  "
              f"{list(pair.evidence)}{ctx}")

    # Regression checks
    cases = REGRESSION_CASES.get(stem, [])
    if cases:
        print()
        print(f"=== Regression checks ({len(cases)} cases) ===")
        passed = 0
        failed = 0
        pairs_list = list(result.pairs)
        for label, predicate in cases:
            ok, observed = _check(pairs_list, label, predicate)
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {label!r} expect {predicate!r}  observed: {observed!r}")
            if ok:
                passed += 1
            else:
                failed += 1
        print()
        print(f"  {passed}/{passed + failed} regression cases passed.")


if __name__ == "__main__":
    main()
