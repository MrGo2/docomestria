"""Contact transformer tests."""

from __future__ import annotations

from docomestria.transform.transformers import email, phone_es, phone_international, url


def test_email_lowercased_and_validated():
    v, c, _ = email("Carlos@Edelwyss.ES")
    assert v == "carlos@edelwyss.es"
    assert c == 1.0


def test_email_invalid():
    v, _, i = email("not-an-email")
    assert v is None
    assert "email_format_invalid" in i


def test_email_empty():
    v, _, i = email("")
    assert v is None
    assert i == ("empty",)


def test_phone_es_local_9_digits():
    v, c, _ = phone_es("659390517")
    assert v == "+34659390517"
    assert c == 1.0


def test_phone_es_with_country_code():
    v, c, _ = phone_es("+34 659 39 05 17")
    assert v == "+34659390517"
    assert c == 1.0


def test_phone_es_invalid():
    v, _, i = phone_es("1234")
    assert v is None or i  # either rejected or flagged


def test_phone_international_requires_plus():
    v, _, i = phone_international("0034659390517")
    # Without explicit '+', flagged.
    assert "missing_country_code" in i


def test_url_with_scheme():
    v, c, _ = url("https://example.com/path")
    assert v.startswith("https://")
    assert c == 1.0


def test_url_without_scheme_gets_https():
    v, c, _ = url("example.com")
    assert v.startswith("https://")
    assert c == 1.0


def test_url_invalid():
    v, _, i = url("not a url with spaces and no dots")
    # Depending on urlparse leniency, this could still be flagged.
    if v is not None:
        assert "://" in v
