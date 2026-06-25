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

def test_clean_street():
    assert apply_transformer("clean_street", "ul. Akacjowa") == "Akacjowa"
    assert apply_transformer("clean_street", "ul.Akacjowa") == "Akacjowa"
    assert apply_transformer("clean_street", "al. Jana Pawła") == "Jana Pawła"
    assert apply_transformer("clean_street", "Al. Jana Pawła") == "Jana Pawła"
    assert apply_transformer("clean_street", "Aleja Jana Pawła") == "Aleja Jana Pawła"
    assert apply_transformer("clean_street", "Prosta 10") == "Prosta 10"
    assert apply_transformer("clean_street", None) is None

def test_rp_extract_city():
    assert apply_transformer("rp_extract_city", "Kraków, Czyżyny, ul. Akacjowa") == "Kraków"
    assert apply_transformer("rp_extract_city", "Warszawa, Mokotów, Sielce, ul. Dziekońskiego 10") == "Warszawa"
    assert apply_transformer("rp_extract_city", "Gdańsk") == "Gdańsk"

def test_rp_extract_region():
    assert apply_transformer("rp_extract_region", "Kraków, Czyżyny, ul. Akacjowa") == "Czyżyny"
    assert apply_transformer("rp_extract_region", "Warszawa, Mokotów, Sielce, ul. Dziekońskiego 10") == "Mokotów"
    assert apply_transformer("rp_extract_region", "Gdańsk") is None

def test_rp_extract_street():
    assert apply_transformer("rp_extract_street", "Kraków, Czyżyny, ul. Akacjowa") == "Akacjowa"
    assert apply_transformer("rp_extract_street", "Warszawa, Mokotów, Sielce, ul. Dziekońskiego 10") == "Dziekońskiego 10"
    assert apply_transformer("rp_extract_street", "Gdańsk, Zaspa-Rozstaje, Al. Jana Pawła") == "Jana Pawła"
    assert apply_transformer("rp_extract_street", "Gdańsk") is None


def test_rp_extract_amenities():
    from usi_scrapers.transformers import apply_transformer
    data = [{"id": 34, "name": "foo"}, {"name": "bar"}, {"id": 35}]
    assert sorted(apply_transformer("rp_extract_amenities", data)) == ["34", "35"]
    assert apply_transformer("rp_extract_amenities", None) is None

def test_oto_extract_amenities():
    from usi_scrapers.transformers import apply_transformer
    data = {"features": ["Balkon ", " windy"]}
    assert sorted(apply_transformer("oto_extract_amenities", data)) == ["balkon", "windy"]

def test_oto_extract_delivery():
    from usi_scrapers.transformers import apply_transformer
    data = [
        {"label": "other", "values": ["2023"]},
        {"label": "project_finish_date", "values": ["2024-Q3"]}
    ]
    assert apply_transformer("oto_extract_delivery", data) == "2024-Q3"
    assert apply_transformer("oto_extract_delivery", [{"label": "project_finish_date", "values": []}]) == None

def test_to_extract_amenities():
    from usi_scrapers.transformers import apply_transformer
    data = [
        {"name": "Garaż", "value": "parking naziemny"},
        {"name": "Winda", "value": "tak"},
        {"name": "Basen", "value": "nie"}
    ]
    assert sorted(apply_transformer("to_extract_amenities", data)) == ["garaż:parking naziemny", "winda"]

def test_strip_html():
    from usi_scrapers.transformers import apply_transformer
    assert apply_transformer("strip_html", "<p>Opis</p>") == "Opis"
    assert apply_transformer("strip_html", "<b>Bold</b><br>Nowa linia") == "Bold\nNowa linia"
    assert apply_transformer("strip_html", "Czysty tekst") == "Czysty tekst"
    assert apply_transformer("strip_html", "<br/>Opis<br />") == "Opis"
    assert apply_transformer("strip_html", "  Text   spaces  ") == "Text spaces"

def test_clean_phone():
    from usi_scrapers.transformers import apply_transformer
    assert apply_transformer("clean_phone", "+48 123 456 789") == "+48123456789"
    assert apply_transformer("clean_phone", "(22) 123-45-67") == "221234567"
    assert apply_transformer("clean_phone", "tel. 500 600 700") == "500600700"
    assert apply_transformer("clean_phone", ["+48 111 222 333", "other"]) == "+48111222333"
    assert apply_transformer("clean_phone", None) is None

def test_extract_first_item():
    from usi_scrapers.transformers import apply_transformer
    assert apply_transformer("extract_first_item", ["a", "b"]) == "a"
    assert apply_transformer("extract_first_item", []) is None
    assert apply_transformer("extract_first_item", "string") == "string"

def test_extract_social():
    from usi_scrapers.transformers import apply_transformer
    
    # Facebook
    assert apply_transformer("extract_facebook", "http://facebook.com/dev") == "http://facebook.com/dev"
    assert apply_transformer("extract_facebook", ["http://twitter.com", "http://facebook.com/dev"]) == "http://facebook.com/dev"
    assert apply_transformer("extract_facebook", [{"url": "http://facebook.com/dev"}]) == "http://facebook.com/dev"
    assert apply_transformer("extract_facebook", [{"type": "fb", "value": "http://facebook.com/dev"}]) == "http://facebook.com/dev"
    
    # Instagram
    assert apply_transformer("extract_instagram", ["http://instagram.com/dev"]) == "http://instagram.com/dev"
    assert apply_transformer("extract_instagram", [{"name": "instagram", "value": "http://ig.com/dev"}]) == "http://ig.com/dev"
    
    # YouTube
    assert apply_transformer("extract_youtube", "http://youtube.com/channel/123") == "http://youtube.com/channel/123"
    
    # LinkedIn
    assert apply_transformer("extract_linkedin", [{"link": "http://linkedin.com/company/abc"}]) == "http://linkedin.com/company/abc"


def test_extract_quarter_from_qformat():
    from usi_scrapers.transformers import apply_transformer
    # Format YYYY-QX
    assert apply_transformer("extract_quarter_from_qformat", "2026-Q1") == 1
    assert apply_transformer("extract_quarter_from_qformat", "2025-Q2") == 2
    assert apply_transformer("extract_quarter_from_qformat", "2024-Q3") == 3
    assert apply_transformer("extract_quarter_from_qformat", "2023-Q4") == 4
    assert apply_transformer("extract_quarter_from_qformat", "2026-q2") == 2  # lowercase
    # Format ISO YYYY-MM-DD
    assert apply_transformer("extract_quarter_from_qformat", "2026-01-01") == 1
    assert apply_transformer("extract_quarter_from_qformat", "2026-04") == 2
    assert apply_transformer("extract_quarter_from_qformat", "2026-07") == 3
    assert apply_transformer("extract_quarter_from_qformat", "2026-10") == 4
    # Edge cases
    assert apply_transformer("extract_quarter_from_qformat", "2026") is None
    assert apply_transformer("extract_quarter_from_qformat", "invalid") is None
    assert apply_transformer("extract_quarter_from_qformat", None) is None
    assert apply_transformer("extract_quarter_from_qformat", 2026) is None


def test_extract_year_from_qformat():
    from usi_scrapers.transformers import apply_transformer
    assert apply_transformer("extract_year_from_qformat", "2026-Q2") == 2026
    assert apply_transformer("extract_year_from_qformat", "2025-03-15") == 2025
    assert apply_transformer("extract_year_from_qformat", "2024") == 2024
    assert apply_transformer("extract_year_from_qformat", "invalid") is None
    assert apply_transformer("extract_year_from_qformat", None) is None
    assert apply_transformer("extract_year_from_qformat", 2026) is None


def test_transform_to_unified_unflatten():
    """Testy rozwijania kluczy z notacją kropkową (unflatten) oraz automatycznych wyliczeń."""
    from usi_scrapers.mapping import transform_to_unified
    import usi_scrapers.mapping as mapping_module

    original_get_mapping = mapping_module.get_mapping
    original_normalize = mapping_module.normalize_to_legacy_props

    def fake_normalize(data, portal):
        return data

    def fake_get_mapping(portal, entity):
        return {
            "name": "title",
            "location.city": "city",
            "location.district": "district",
            "specifications.delivery_date": "delivery_date",
            "specifications.delivery_quarter": "delivery_quarter",
            "specifications.delivery_year": "delivery_year",
            "financials.price_min": {"path": "price_min", "transform": "to_float"},
            "financials.price_max": {"path": "price_max", "transform": "to_float"},
        }

    mapping_module.get_mapping = fake_get_mapping
    mapping_module.normalize_to_legacy_props = fake_normalize

    try:
        # Test: unflatten i auto-wyliczenia z delivery_date w formacie YYYY-QX
        raw = {
            "title": "Nowa Inwestycja",
            "city": "Warszawa",
            "district": "Mokotów",
            "delivery_date": "2026-Q3",
            "delivery_quarter": None,
            "delivery_year": None,
            "price_min": 500000,
            "price_max": 800000,
        }
        result = transform_to_unified("oto", raw)

        # Struktura zagnieżdżona
        assert result["name"] == "Nowa Inwestycja"
        assert result["location"]["city"] == "Warszawa"
        assert result["location"]["district"] == "Mokotów"

        # Auto-wyliczenia kwartał/rok z delivery_date
        assert result["specifications"]["delivery_date"] == "2026-Q3"
        assert result["specifications"]["delivery_quarter"] == 3
        assert result["specifications"]["delivery_year"] == 2026

        # price_avg
        assert result["financials"]["price_min"] == 500000.0
        assert result["financials"]["price_max"] == 800000.0
        assert result["financials"]["price_avg"] == 650000.0

        # Test: brak nadpisania jawnych wartości quarter/year
        raw2 = {
            "title": "Inna Inwestycja",
            "city": "Kraków",
            "district": None,
            "delivery_date": "2027-Q1",
            "delivery_quarter": 2,   # jawna wartość — nie może być nadpisana
            "delivery_year": 2028,   # jawna wartość — nie może być nadpisana
            "price_min": 300000,
            "price_max": None,
        }
        result2 = transform_to_unified("oto", raw2)
        assert result2["specifications"]["delivery_quarter"] == 2  # nie zmieniony
        assert result2["specifications"]["delivery_year"] == 2028  # nie zmieniony
        # price_avg z samego price_min gdy price_max jest None
        assert result2["financials"]["price_avg"] == 300000.0

        # Test: puste dane
        assert transform_to_unified("oto", {}) == {}

    finally:
        mapping_module.get_mapping = original_get_mapping
        mapping_module.normalize_to_legacy_props = original_normalize

