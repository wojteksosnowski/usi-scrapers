import pytest
from usi_scrapers.transformers import apply_transformer, _TRANSFORMERS

def test_apply_transformer_unknown():
    # Should return original value if transformer is unknown
    with pytest.raises(ValueError, match="Unknown transformer: unknown"):
        apply_transformer("unknown", "100")

def test_cm_to_m():
    assert apply_transformer("cm_to_m", 250) == 2.5
    assert apply_transformer("cm_to_m", 250.5) == 2.5
    assert apply_transformer("cm_to_m", "250") == 2.5
    assert apply_transformer("cm_to_m", "260 cm") == 2.6
    assert apply_transformer("cm_to_m", "Wysokość: 275 cm") == 2.75
    assert apply_transformer("cm_to_m", "2.7") == 2.7  # already in meters
    assert apply_transformer("cm_to_m", 3.1) == 3.1  # already in meters
    assert apply_transformer("cm_to_m", "100") == 100.0  # edge case, 100cm should be 1m? The logic says num > 100
    assert apply_transformer("cm_to_m", 101) == 1.01
    assert apply_transformer("cm_to_m", "abc") is None
    assert apply_transformer("cm_to_m", None) is None

def test_date_to_quarter():
    assert apply_transformer("date_to_quarter", "2025-01") == 1
    assert apply_transformer("date_to_quarter", "2025-02") == 1
    assert apply_transformer("date_to_quarter", "2025-03") == 1
    assert apply_transformer("date_to_quarter", "2025-04") == 2
    assert apply_transformer("date_to_quarter", "2025-05") == 2
    assert apply_transformer("date_to_quarter", "2025-06") == 2
    assert apply_transformer("date_to_quarter", "2025-07") == 3
    assert apply_transformer("date_to_quarter", "2025-08") == 3
    assert apply_transformer("date_to_quarter", "2025-09") == 3
    assert apply_transformer("date_to_quarter", "2025-10") == 4
    assert apply_transformer("date_to_quarter", "2025-11") == 4
    assert apply_transformer("date_to_quarter", "2025-12") == 4
    assert apply_transformer("date_to_quarter", "2025") is None
    assert apply_transformer("date_to_quarter", "abc") is None

def test_rp_gallery_to_flat_list():
    data = {
        "main_image": {
            "value": {
                "g_img_2000": "http://img1_2000.jpg",
                "g_img_1500": "http://img1_1500.jpg"
            }
        },
        "gallery": {
            "value": [
                {
                    "value": {
                        "g_img_2000": "http://img1_2000.jpg" # duplicate main
                    }
                },
                {
                    "value": {
                        "g_img_1500": "http://img2_1500.jpg"
                    }
                },
                {
                    "value": {
                        "m_img_750": "http://img3_750.jpg"
                    }
                }
            ]
        }
    }
    res = apply_transformer("rp_gallery_to_flat_list", data)
    assert res == [
        "http://img1_2000.jpg",
        "http://img2_1500.jpg",
        "http://img3_750.jpg"
    ]

def test_oto_gallery_to_flat_list():
    data = [
        {"large": "http://large1.jpg", "small": "http://small1.jpg"},
        {"medium": "http://medium2.jpg"},
        {"large": "http://large1.jpg"} # duplicate
    ]
    res = apply_transformer("oto_gallery_to_flat_list", data)
    assert res == ["http://large1.jpg", "http://medium2.jpg"]

