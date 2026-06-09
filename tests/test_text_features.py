from docomestria.text_features import content_flags, case_class


def test_case_class_values():
    assert case_class("TOTAL DEUDA") == "UPPER"
    assert case_class("importe pendiente") == "lower"
    assert case_class("DNI Titular") == "Title"
    assert case_class("IBAN es20") == "mixed"
    assert case_class("123,45") == "none"


def test_content_flags_keys_and_values():
    f = content_flags("1.234,56 €")
    assert set(f) == {
        "digit_ratio", "has_currency", "has_date", "has_percent",
        "has_iban", "has_nif", "starts_paren", "ends_colon",
        "n_numeric_tokens", "len_chars",
    }
    assert f["has_currency"] is True
    assert f["len_chars"] == len("1.234,56 €")
    assert content_flags("Nº Modelo:")["ends_colon"] is True
    assert content_flags("(ver nota)")["starts_paren"] is True
