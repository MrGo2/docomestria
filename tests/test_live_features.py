from docomestria.models import BBox, LiteItem
from docomestria.live_features import _base_row, _bbox_to_dict


def test_base_row_geometry_normalised_by_page_size():
    it = LiteItem(text="NOMBRE:", bbox=BBox(x=60.0, y=120.0, w=90.0, h=12.0),
                  font_name="Helvetica-Bold", font_size=10.0, page=1)
    row = _base_row(it, page_size_pt=(600.0, 800.0))
    assert row["x"] == 60.0 / 600.0
    assert row["y"] == 120.0 / 800.0
    assert row["w"] == 90.0 / 600.0
    assert row["h"] == 12.0 / 800.0
    assert row["is_bold"] == 1
    assert row["font_size"] == 10.0
    assert row["case_upper"] == 1 and row["case_lower"] == 0
    assert row["ends_colon"] is True or row["ends_colon"] == 1
    assert row["text"] == "NOMBRE:"
    assert row["page"] == 1
    assert row["liteparse_present"] == 1


def test_bbox_to_dict_roundtrip():
    assert _bbox_to_dict(BBox(x=1.0, y=2.0, w=3.0, h=4.0)) == {"x": 1.0, "y": 2.0, "w": 3.0, "h": 4.0}
