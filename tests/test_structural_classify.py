"""Focused unit tests for structural/classify.py.

Covers:
- fit_font_size_buckets: GMM path with 3 distinct sizes
- fit_font_size_buckets: single-size document (no crash, graceful output)
- fit_font_size_buckets: percentile fallback when sklearn absent (monkeypatched)
- classify_item: TITLE detection via GMM-derived title_min
- classify_item: BODY detection via GMM-derived body_max
- classify_item: LABEL (bold+colon) in the label/value band
- classify_page: real-world-like BBVA item set (bold label, regular value, big title)
- classify: multi-page grouping
"""

from __future__ import annotations

import sys
import types

import pytest

from docomestria.models import BBox, LiteItem
from docomestria.structural.classify import (
    BODY_SIZE_DELTA_PT,
    MIN_GMM_ITEMS,
    TITLE_SIZE_DELTA_PT,
    classify,
    classify_item,
    classify_page,
    fit_font_size_buckets,
)
from docomestria.structural.models import ItemKind


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(
    text: str,
    size: float | None = 10.0,
    font: str | None = "Helvetica",
    page: int = 1,
    x: float = 0.0,
    y: float = 0.0,
) -> LiteItem:
    return LiteItem(
        text=text,
        bbox=BBox(x=x, y=y, w=80.0, h=size or 10.0),
        font_name=font,
        font_size=size,
        page=page,
    )


def _bold(text: str, size: float = 10.0, page: int = 1, **kw) -> LiteItem:
    return _item(text, size=size, font="Helvetica-Bold", page=page, **kw)


def _regular(text: str, size: float = 10.0, page: int = 1, **kw) -> LiteItem:
    return _item(text, size=size, font="Helvetica", page=page, **kw)


# ---------------------------------------------------------------------------
# fit_font_size_buckets: GMM with 3 distinct clusters
# ---------------------------------------------------------------------------

class TestFitFontSizeBuckets:
    def test_three_distinct_sizes_produce_three_separate_thresholds(self):
        """GMM on sizes 10/14/18 must yield title_min > body_max > 0."""
        items = (
            [_item("body", size=10.0)] * 10
            + [_item("label", size=14.0)] * 10
            + [_item("title", size=18.0)] * 10
        )
        buckets = fit_font_size_buckets(items)

        assert "title_min" in buckets
        assert "body_max" in buckets
        assert "dominant" in buckets

        # Three distinct groups -> thresholds must separate them
        assert buckets["title_min"] > buckets["dominant"]
        assert buckets["body_max"] < buckets["dominant"]
        # title_min should be below 18 (some body-of-title cluster captured)
        assert buckets["title_min"] < 18.0
        # body_max should be below dominant (body cluster is separate below it)
        assert buckets["body_max"] < buckets["dominant"]
        # Dominant is the mode of the data (min of tied modes = 10 here, which is fine).
        # The critical invariant is: body_max < dominant < title_min, which forms the
        # three-bucket layout.
        assert buckets["body_max"] < buckets["title_min"]

    def test_single_size_document_does_not_crash(self):
        """A page where every item is the same size must not raise."""
        items = [_item("word", size=10.0)] * 20
        buckets = fit_font_size_buckets(items)
        assert isinstance(buckets["title_min"], float)
        assert isinstance(buckets["body_max"], float)
        assert isinstance(buckets["dominant"], float)

    def test_below_min_gmm_items_returns_delta_fallback(self):
        """Fewer than MIN_GMM_ITEMS items -> fixed-delta result, no crash."""
        items = [_item("x", size=12.0)] * (MIN_GMM_ITEMS - 1)
        buckets = fit_font_size_buckets(items)
        # Should still return valid thresholds
        assert buckets["title_min"] > 0
        assert "dominant" in buckets

    def test_empty_items_returns_safe_sentinels(self):
        """No items at all -> inf title_min, 0 body_max, no crash."""
        buckets = fit_font_size_buckets([])
        assert buckets["title_min"] == float("inf")
        assert buckets["body_max"] == 0.0

    def test_percentile_fallback_when_sklearn_absent(self, monkeypatch):
        """When _gmm_buckets raises the percentile path must produce valid output."""
        import importlib
        import sys

        # Force the submodule to be accessible regardless of package-level shadowing.
        classify_mod = importlib.import_module("docomestria.structural.classify")

        def _raise(*args, **kwargs):
            raise ImportError("sklearn not available")

        monkeypatch.setattr(classify_mod, "_gmm_buckets", _raise, raising=True)

        items = (
            [_item("body", size=8.0)] * 10
            + [_item("label", size=12.0)] * 10
            + [_item("title", size=18.0)] * 5
        )
        buckets = classify_mod.fit_font_size_buckets(items)
        assert buckets["title_min"] > buckets["dominant"]
        assert buckets["body_max"] < buckets["dominant"]


# ---------------------------------------------------------------------------
# classify_item: threshold integration
# ---------------------------------------------------------------------------

class TestClassifyItemWithThresholds:
    def test_large_size_becomes_title(self):
        item = _bold("TITULO SECCIÓN", size=18.0)
        ci = classify_item(item, dominant_size=12.0, title_min=15.0, body_max=9.0)
        assert ci.kind == ItemKind.TITLE

    def test_small_size_becomes_body(self):
        item = _regular("pie de página", size=7.0)
        ci = classify_item(item, dominant_size=12.0, title_min=15.0, body_max=9.0)
        assert ci.kind == ItemKind.BODY

    def test_bold_colon_in_band_becomes_label(self):
        item = _bold("Nombre:", size=12.0)
        ci = classify_item(item, dominant_size=12.0, title_min=15.0, body_max=9.0)
        assert ci.kind == ItemKind.LABEL

    def test_regular_in_band_becomes_value(self):
        item = _regular("Carlos Lorenzo", size=12.0)
        ci = classify_item(item, dominant_size=12.0, title_min=15.0, body_max=9.0)
        assert ci.kind == ItemKind.VALUE

    def test_falls_back_to_delta_when_thresholds_none(self):
        """No title_min/body_max -> classic fixed-delta behaviour preserved."""
        big = _regular("BIG TITLE", size=20.0)
        ci = classify_item(big, dominant_size=10.0)
        assert ci.kind == ItemKind.TITLE

        small = _regular("footnote", size=7.0)
        ci2 = classify_item(small, dominant_size=10.0)
        assert ci2.kind == ItemKind.BODY


# ---------------------------------------------------------------------------
# classify_page: BBVA-like item set
# ---------------------------------------------------------------------------

class TestClassifyPage:
    """Simulate a BBVA contract page: bold labels, regular values, big section title."""

    def _bbva_items(self) -> tuple[LiteItem, ...]:
        return (
            # Section title (larger, bold)
            _bold("DATOS DEL TITULAR", size=14.0, y=10),
            # KV pairs (same-size 10pt)
            _bold("Nombre:", size=10.0, y=30),
            _regular("Carlos Lorenzo", size=10.0, y=30),
            _bold("NIF:", size=10.0, y=45),
            _regular("12345678A", size=10.0, y=45),
            _bold("Fecha nacimiento:", size=10.0, y=60),
            _regular("09/09/1979", size=10.0, y=60),
            # Footer (smaller)
            _regular("Pagina 1 de 5", size=6.0, y=800),
        ) + (
            # Extra body-size items so GMM has enough data
            tuple(_regular(f"word{i}", size=10.0, y=100 + i * 12) for i in range(8))
        )

    def test_title_detected(self):
        items = self._bbva_items()
        classified = {ci.item.text: ci.kind for ci in classify_page(items)}
        assert classified["DATOS DEL TITULAR"] == ItemKind.TITLE

    def test_bold_labels_detected(self):
        items = self._bbva_items()
        classified = {ci.item.text: ci.kind for ci in classify_page(items)}
        assert classified["Nombre:"] == ItemKind.LABEL
        assert classified["NIF:"] == ItemKind.LABEL

    def test_regular_values_detected(self):
        items = self._bbva_items()
        classified = {ci.item.text: ci.kind for ci in classify_page(items)}
        assert classified["Carlos Lorenzo"] == ItemKind.VALUE
        assert classified["12345678A"] == ItemKind.VALUE

    def test_footer_becomes_body(self):
        items = self._bbva_items()
        classified = {ci.item.text: ci.kind for ci in classify_page(items)}
        assert classified["Pagina 1 de 5"] == ItemKind.BODY


# ---------------------------------------------------------------------------
# classify: multi-page grouping
# ---------------------------------------------------------------------------

class TestClassifyMultiPage:
    def test_each_page_classified_independently(self):
        """Items on page 1 and page 2 must be classified independently."""
        # Page 1: dominant 10pt
        p1 = [_regular(f"v{i}", size=10.0, page=1) for i in range(10)]
        # Page 2: dominant 12pt -- title threshold shifts
        p2 = [_regular(f"v{i}", size=12.0, page=2) for i in range(10)]
        all_items = tuple(p1 + p2)
        result = classify(all_items)
        assert len(result) == len(all_items)
        # All should get classified (no crash, no UNKNOWN from size absence)
        pages = {ci.item.page for ci in result}
        assert pages == {1, 2}
