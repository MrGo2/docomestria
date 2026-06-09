from docomestria.live_labels import ANNOTATED_ROLES, transfer_labels


def _row(text, x, y, w=40.0, h=12.0, page=1):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "page": page, "role": ""}


def _gitem(text, x, y, role, w=40.0, h=12.0, page=1):
    return {"text": text, "bbox": {"x": x, "y": y, "w": w, "h": h}, "role": role, "page": page}


def test_transfer_labels_matches_by_norm_text_and_overlap():
    rows = [_row("Nombre", 0.1, 0.1)]
    golden = [_gitem("nombre", 0.1, 0.1, "key")]
    labeled, cov = transfer_labels(rows, golden)
    assert labeled[0]["role"] == "key"
    assert cov["matched"] == 1
    assert cov["per_role"]["key"]["matched"] == 1


def test_transfer_labels_unmatched_row_becomes_noise():
    rows = [_row("zzz off page", 0.9, 0.9)]
    golden = [_gitem("nombre", 0.1, 0.1, "key")]
    labeled, cov = transfer_labels(rows, golden)
    assert labeled[0]["role"] == "noise"


def test_transfer_labels_coverage_floor_per_role():
    rows = [_row("Nombre", 0.1, 0.1), _row("Apellido", 0.1, 0.2)]
    golden = [_gitem("nombre", 0.1, 0.1, "key"), _gitem("apellido", 0.1, 0.2, "key")]
    _labeled, cov = transfer_labels(rows, golden)
    assert cov["overall_pct"] == 100.0
    assert cov["per_role"]["key"]["pct"] == 100.0


def test_transfer_labels_bbox_less_table_header_matches_by_text_only():
    rows = [_row("Importe", 0.4, 0.3)]
    golden = [{"text": "importe", "bbox": None, "role": "table_header", "page": 1}]
    labeled, cov = transfer_labels(rows, golden)
    assert labeled[0]["role"] == "table_header"
    assert cov["per_role"]["table_header"]["matched"] == 1


def test_golden_annotated_items_skips_non_string_text(monkeypatch):
    import types

    import docomestria.live_labels as ll

    def _it(text, role, bbox):
        return types.SimpleNamespace(text=text, role=role, bbox=bbox)

    monkeypatch.setattr(
        ll,
        "walk_structure",
        lambda structure, spans: [
            _it("Nombre", "key", {"x": 10.0, "y": 10.0, "w": 40.0, "h": 12.0}),
            _it({"ref": "nota_1"}, "value", {"x": 60.0, "y": 10.0, "w": 40.0, "h": 12.0}),
        ],
    )
    items = ll.golden_annotated_items(
        {"page_size_pt": [600.0, 800.0], "page": 1, "structure": [], "atoms": {"spans": []}}
    )
    assert [g["text"] for g in items] == ["Nombre"]


def test_golden_annotated_items_normalizes_bbox(monkeypatch):
    import types

    import docomestria.live_labels as ll

    monkeypatch.setattr(
        ll,
        "walk_structure",
        lambda structure, spans: [
            types.SimpleNamespace(
                text="Nombre", role="key", bbox={"x": 10.0, "y": 20.0, "w": 40.0, "h": 12.0}
            ),
        ],
    )
    items = ll.golden_annotated_items(
        {"page_size_pt": [600.0, 800.0], "page": 1, "structure": [], "atoms": {"spans": []}}
    )
    assert items[0]["bbox"] == {
        "x": 10.0 / 600.0,
        "y": 20.0 / 800.0,
        "w": 40.0 / 600.0,
        "h": 12.0 / 800.0,
    }


def test_transfer_labels_used_set_prevents_double_match():
    rows = [_row("Nombre", 0.1, 0.1), _row("Nombre", 0.1, 0.1)]
    golden = [_gitem("nombre", 0.1, 0.1, "key")]
    labeled, cov = transfer_labels(rows, golden)
    roles = sorted(r["role"] for r in labeled)
    assert roles == ["key", "noise"]
    assert cov["per_role"]["key"]["matched"] == 1


def test_annotated_roles_excludes_noise():
    assert "noise" not in ANNOTATED_ROLES
    assert {
        "key",
        "value",
        "section_header",
        "table_header",
        "signature",
        "prose",
    } <= ANNOTATED_ROLES
