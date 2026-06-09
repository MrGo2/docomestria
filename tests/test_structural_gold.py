"""Gold structural annotations for the five Spanish validation PDFs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = ROOT / "data" / "parsebench" / "gold_structural"
OUTPUTS_DIR = ROOT / "data" / "parsebench" / "outputs"

GOLD_STEMS = (
    "azuredemo__LABORAL",
    "azuredemo__PATRIMONIAL",
    "azuredemo__BBVA3",
    "azuredemo__BBVA4",
    "azuredemo__BBVA5",
)


def _known_gap_cases() -> list[tuple[str, dict]]:
    cases: list[tuple[str, dict]] = []
    if not GOLD_DIR.exists():
        return cases
    for stem in GOLD_STEMS:
        path = GOLD_DIR / f"{stem}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases.extend((stem, gap) for gap in payload.get("known_gaps", ()))
    return cases


KNOWN_GAP_CASES = _known_gap_cases()
KNOWN_GAP_IDS = [
    f"{stem}:gap-{index}:{gap['kind']}"
    for index, (stem, gap) in enumerate(KNOWN_GAP_CASES, start=1)
]


def test_gold_annotations_exist_for_spanish_regression_corpus():
    for stem in GOLD_STEMS:
        path = GOLD_DIR / f"{stem}.json"
        assert path.exists(), f"missing gold annotation: {path}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["document_id"] == stem
        assert payload["schema_version"] == 1
        assert (
            payload["expected_pairs"] or payload.get("expected_tables")
        ), f"{stem} has no expected structural assertions"
        assert payload["forbidden_pairs"], f"{stem} has no forbidden pairs"
        assert isinstance(payload["known_gaps"], list)


@pytest.mark.parametrize("stem", GOLD_STEMS)
def test_structural_extraction_matches_gold_annotations(stem):
    payload = json.loads((GOLD_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    result = _run_structural_extract(stem)
    pairs = list(result.pairs)

    for expected in payload["expected_pairs"]:
        _assert_expected_pair(stem, pairs, expected)

    for forbidden in payload["forbidden_pairs"]:
        _assert_forbidden_pair_absent(stem, pairs, forbidden)

    for forbidden_page in payload.get("forbidden_pages", ()):
        _assert_forbidden_page_empty(stem, pairs, forbidden_page)

    for expected_table in payload.get("expected_tables", ()):
        _assert_expected_table(stem, result.pages, expected_table)


if KNOWN_GAP_CASES:

    @pytest.mark.xfail(strict=True, reason="documents desired behavior not fixed yet")
    @pytest.mark.parametrize(
        ("stem", "gap"),
        KNOWN_GAP_CASES,
        ids=KNOWN_GAP_IDS,
    )
    def test_structural_extraction_known_gold_gaps(stem, gap):
        result = _run_structural_extract(stem)
        pairs = list(result.pairs)

        if gap["kind"] == "expected_pair":
            _assert_expected_pair(stem, pairs, gap)
        elif gap["kind"] == "forbidden_pair":
            _assert_forbidden_pair_absent(stem, pairs, gap)
        elif gap["kind"] == "forbidden_page":
            _assert_forbidden_page_empty(stem, pairs, gap)
        else:
            raise AssertionError(f"{stem}: unknown gap kind {gap['kind']!r}")

else:

    def test_structural_extraction_known_gold_gaps():
        assert KNOWN_GAP_CASES == []


def _run_structural_extract(stem: str):
    required_outputs = [
        OUTPUTS_DIR / "docling" / f"{stem}.json",
        OUTPUTS_DIR / "liteparse" / f"{stem}.json",
        OUTPUTS_DIR / "pdfplumber" / f"{stem}.json",
    ]
    missing_outputs = [p for p in required_outputs if not p.exists()]
    if missing_outputs:
        raise AssertionError(
            f"cached engine output fixture missing: {missing_outputs[0]}"
        )

    from docomestria.structural import structural_extract_from_engines
    from scripts.validate_extract import load_docling, load_lite, load_plumber

    return structural_extract_from_engines(
        load_docling(stem),
        load_lite(stem),
        load_plumber(stem),
    )


def _assert_expected_pair(stem: str, pairs: list, expected: dict) -> None:
    matches = [
        p
        for p in pairs
        if _norm(p.label_text) == _norm(expected["label"])
        and (expected.get("page") is None or p.page == expected["page"])
    ]
    assert matches, f"{stem}: missing expected label {expected['label']!r}"
    value_matches = [p for p in matches if _value_matches(p.value_text, expected["value"])]
    observed_values = [p.value_text for p in matches]
    assert value_matches, (
        f"{stem}: {expected['label']!r} expected {expected['value']!r}, "
        f"observed {observed_values!r}"
    )
    observed = value_matches[0]
    if expected.get("confidence"):
        assert observed.confidence.value == expected["confidence"]
    if expected.get("section"):
        assert observed.section_title == expected["section"]
    if expected.get("subsection"):
        assert observed.subsection_title == expected["subsection"]
    if expected.get("evidence"):
        assert expected["evidence"] in observed.evidence
    if "column_index" in expected:
        assert getattr(observed, "column_index", None) == expected["column_index"]


def _assert_forbidden_pair_absent(stem: str, pairs: list, forbidden: dict) -> None:
    bad = [
        p
        for p in pairs
        if _norm(p.label_text) == _norm(forbidden["label"])
        and _value_matches(p.value_text, forbidden["value"])
        and (forbidden.get("page") is None or p.page == forbidden["page"])
        and (
            "column_index" not in forbidden
            or getattr(p, "column_index", None) == forbidden["column_index"]
        )
    ]
    assert not bad, (
        f"{stem}: forbidden pair emitted: "
        f"{forbidden['label']!r} -> {forbidden['value']!r}"
    )


def _assert_forbidden_page_empty(stem: str, pairs: list, forbidden_page: dict) -> None:
    start = forbidden_page["start"]
    end = forbidden_page.get("end", start)
    bad = [p for p in pairs if start <= p.page <= end]
    assert not bad, (
        f"{stem}: expected no pairs on pages {start}-{end}, "
        f"observed {[(p.page, p.label_text, p.value_text) for p in bad]}"
    )


def _assert_expected_table(stem: str, pages: tuple, expected_table: dict) -> None:
    page = next((p for p in pages if p.number == expected_table["page"]), None)
    assert page is not None, f"{stem}: missing page {expected_table['page']}"

    candidates = []
    for table in page.tables:
        cells = table.cells or ()
        row_count = len(cells)
        col_count = max((len(row) for row in cells), default=0)
        if row_count < expected_table.get("min_rows", 0):
            continue
        if col_count < expected_table.get("min_cols", 0):
            continue
        if all(_table_has_row(cells, row) for row in expected_table["contains_rows"]):
            candidates.append(table)

    assert candidates, f"{stem}: missing expected table {expected_table!r}"


def _table_has_row(cells: tuple[tuple[str, ...], ...], expected_row: list[str]) -> bool:
    for row in cells:
        normalised_cells = [_norm(cell) for cell in row]
        if all(any(_norm(expected) in cell for cell in normalised_cells) for expected in expected_row):
            return True
    return False


def _norm(text: str) -> str:
    return "".join(text.lower().rstrip(":").split())


def _value_matches(observed: str, expected: str) -> bool:
    if expected == "<empty>":
        return observed.strip() == ""
    if expected.startswith("contains:"):
        return expected.removeprefix("contains:").lower() in observed.lower()
    return observed.strip() == expected
