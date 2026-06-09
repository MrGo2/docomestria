from docomestria.engines.pdfplumber import _words_from_page
from docomestria.models import WordItem


def test_words_from_page_converts_pdfplumber_dicts_to_top_left_bbox():
    raw = [
        {"text": "Nombre:", "x0": 10.0, "x1": 55.0, "top": 100.0, "bottom": 112.0},
        {"text": "Adrian", "x0": 60.0, "x1": 95.0, "top": 100.0, "bottom": 112.0},
    ]
    words = _words_from_page(raw, page=1)
    assert [type(w) for w in words] == [WordItem, WordItem]
    w0 = words[0]
    assert w0.text == "Nombre:"
    assert w0.page == 1
    assert (w0.bbox.x, w0.bbox.y, w0.bbox.w, w0.bbox.h) == (10.0, 100.0, 45.0, 12.0)


def test_words_from_page_skips_blank_text():
    raw = [{"text": "   ", "x0": 0.0, "x1": 1.0, "top": 0.0, "bottom": 1.0}]
    assert _words_from_page(raw, page=1) == []
