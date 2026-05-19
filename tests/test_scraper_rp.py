import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from usi_scrapers.scraper_rp import (
    fetch_rp_details,
    fetch_rp_gallery,
    scrape_rynek_pierwotny,
    discover_rp_investments,
    _parse_rp_results,
    resolve_rp_vendor_id,
)
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig


@pytest.fixture
def config(tmp_path):
    return ScraperConfig(public_dir=tmp_path, scraperapi_key="test_key")


@pytest.fixture
def fetcher(config):
    f = Fetcher(config)
    f.fetch_json = MagicMock()
    f.fetch = MagicMock()
    return f


# ---------------------------------------------------------------------------
# fetch_rp_details
# ---------------------------------------------------------------------------

def test_fetch_rp_details(fetcher):
    fetcher.fetch_json.return_value = {"id": 123, "name": "Test Investment"}
    details = fetch_rp_details("123", fetcher)
    assert details == {"id": 123, "name": "Test Investment"}
    args, _ = fetcher.fetch_json.call_args
    assert "123" in args[0]
    assert "offer-detail" in args[0]


def test_fetch_rp_details_returns_empty_on_failure(fetcher):
    fetcher.fetch_json.return_value = None
    assert fetch_rp_details("999", fetcher) == {}


# ---------------------------------------------------------------------------
# fetch_rp_gallery
# ---------------------------------------------------------------------------

def test_fetch_rp_gallery(fetcher):
    fetcher.fetch_json.return_value = {
        "gallery": [
            {"image": {"g_img_1500": "https://cdn.rp.pl/1.jpg"}},
            {"image": {"g_img_1500": "https://cdn.rp.pl/2.jpg"}},
        ]
    }
    gallery = fetch_rp_gallery("123", fetcher)
    assert gallery == ["https://cdn.rp.pl/1.jpg", "https://cdn.rp.pl/2.jpg"]


def test_fetch_rp_gallery_skips_missing_resolution(fetcher):
    fetcher.fetch_json.return_value = {
        "gallery": [
            {"image": {"g_img_1500": "https://cdn.rp.pl/1.jpg"}},
            {"image": {}},  # no g_img_1500
        ]
    }
    gallery = fetch_rp_gallery("123", fetcher)
    assert len(gallery) == 1
    assert gallery[0] == "https://cdn.rp.pl/1.jpg"


def test_fetch_rp_gallery_empty(fetcher):
    fetcher.fetch_json.return_value = {"gallery": []}
    assert fetch_rp_gallery("123", fetcher) == []


# ---------------------------------------------------------------------------
# _parse_rp_results — stage flattening
# ---------------------------------------------------------------------------

_RP_SIMPLE_ITEM = {
    "id": 1001,
    "name": "Osiedle Zielone",
    "slug": "osiedle-zielone",
    "vendor": {"value": {"slug": "dom-dev", "name": "Dom Dev SA"}},
    "main_image": {"m_img_1500": "https://cdn.rp.pl/main.jpg"},
    "groups": None,
}

_RP_MULTISTAGE_ITEM = {
    "id": 2000,
    "name": "Lawinowa 18 (parent)",
    "slug": "lawinowa-18",
    "vendor": {"value": {"slug": "budrem", "name": "BudRem"}},
    "main_image": None,
    "groups": {
        "value": {
            "stages": {
                "value": [
                    {
                        "id": 11,
                        "sort": 1,
                        "current": False,
                        "offer": {
                            "value": {
                                "id": 2001,
                                "name": "Lawinowa 18 Etap I",
                                "slug": "lawinowa-18-etap-i",
                                "vendor": {"value": {"slug": "budrem", "name": "BudRem"}},
                                "main_photo": {"image": "https://cdn.rp.pl/etap1.jpg"},
                            }
                        },
                    },
                    {
                        "id": 12,
                        "sort": 2,
                        "current": True,
                        "offer": {
                            "value": {
                                "id": 2002,
                                "name": "Lawinowa 18 Etap II",
                                "slug": "lawinowa-18-etap-ii",
                                "vendor": {"value": {"slug": "budrem", "name": "BudRem"}},
                                "main_photo": None,
                            }
                        },
                    },
                ]
            }
        }
    },
}


def test_parse_rp_results_simple():
    offers = _parse_rp_results([_RP_SIMPLE_ITEM])
    assert len(offers) == 1
    o = offers[0]
    assert o["id"] == "1001"
    assert "dom-dev" in o["url"]
    assert "osiedle-zielone" in o["url"]


def test_parse_rp_results_stage_flattening():
    offers = _parse_rp_results([_RP_MULTISTAGE_ITEM])
    assert len(offers) == 2
    ids = {o["id"] for o in offers}
    assert ids == {"2001", "2002"}
    for o in offers:
        assert "show_sold_stage=true" in o["url"]


def test_parse_rp_results_empty():
    assert _parse_rp_results([]) == []


# ---------------------------------------------------------------------------
# scrape_rynek_pierwotny — end-to-end
# ---------------------------------------------------------------------------

_RP_DETAILS = {
    "id": 5000,
    "name": "Testowa Inwestycja",
    "slug": "testowa-inwestycja",
    "address": "ul. Testowa 1, Warszawa",
    "geo_point": {"coordinates": [21.01, 52.23]},  # [lng, lat]
    "vendor": {"value": {"id": 123, "slug": "test-dev"}},
    "construction_date_range": {"upper": "2026-12-31"},
    "groups": None,
}

_RP_GALLERY = {
    "gallery": [
        {"image": {"g_img_1500": "https://cdn.rp.pl/a.jpg"}},
        {"image": {"g_img_1500": "https://cdn.rp.pl/b.jpg"}},
    ]
}


_RP_DEV_PROFILE = {"id": 123, "slug": "test-dev", "name": "Test Dev"}


def test_scrape_rynek_pierwotny_coords(fetcher):
    fetcher.fetch_json.side_effect = [_RP_DETAILS, _RP_GALLERY, _RP_DEV_PROFILE]
    result = scrape_rynek_pierwotny("5000", fetcher)

    assert "error" not in result
    assert result["longitude"] == 21.01
    assert result["latitude"] == 52.23


def test_scrape_rynek_pierwotny_coords_single_element(fetcher):
    details = dict(_RP_DETAILS)
    details["geo_point"] = {"coordinates": [21.01]}  # only one element
    fetcher.fetch_json.side_effect = [details, _RP_GALLERY, _RP_DEV_PROFILE]
    result = scrape_rynek_pierwotny("5000", fetcher)
    # latitude must be None, not the same as longitude
    assert "error" not in result
    assert result["longitude"] == 21.01
    assert result["latitude"] is None


def test_scrape_rynek_pierwotny_images(fetcher):
    fetcher.fetch_json.side_effect = [_RP_DETAILS, _RP_GALLERY, _RP_DEV_PROFILE]
    result = scrape_rynek_pierwotny("5000", fetcher)
    assert "error" not in result
    assert len(result["image_urls"]) == 2
    assert "https://cdn.rp.pl/a.jpg" in result["image_urls"]


def test_scrape_rynek_pierwotny_missing_details(fetcher):
    fetcher.fetch_json.return_value = None
    result = scrape_rynek_pierwotny("9999", fetcher)
    assert "error" in result


def test_scrape_rynek_pierwotny_sibling_stages(fetcher):
    # offer-detail API returns groups already unwrapped (flat structure)
    details = dict(_RP_DETAILS)
    details["groups"] = {
        "id": 10,
        "stages": [
            {"id": 1, "sort": 1, "current": True,
             "offer": {"id": 5000, "slug": "testowa-inwestycja", "vendor": {"id": 123}}},
            {"id": 2, "sort": 2, "current": False,
             "offer": {"id": 5001, "slug": "testowa-inwestycja-ii", "vendor": {"id": 123}}},
        ]
    }
    fetcher.fetch_json.side_effect = [details, _RP_GALLERY, _RP_DEV_PROFILE]
    result = scrape_rynek_pierwotny("5000", fetcher)
    assert "error" not in result
    assert result["stage_sort"] == 1
    assert result["stage_is_current"] is True
    assert len(result["sibling_stage_folders"]) == 1
    assert "testowa-inwestycja-ii" in result["sibling_stage_folders"][0]


# ---------------------------------------------------------------------------
# discover_rp_investments — pagination
# ---------------------------------------------------------------------------

def _rp_page(items, total=None):
    return {"results": items, "count": total or len(items)}


def test_discover_rp_by_vendor(fetcher, config):
    page1 = _rp_page([_RP_SIMPLE_ITEM])
    fetcher.fetch_json.return_value = page1

    results = discover_rp_investments(config, fetcher, identifier="123")
    assert len(results) == 1
    assert results[0]["id"] == "1001"


def test_discover_rp_pagination_stops_on_partial_page(fetcher, config):
    full_page = _rp_page([_RP_SIMPLE_ITEM] * 30)
    partial_page = _rp_page([_RP_SIMPLE_ITEM])
    fetcher.fetch_json.side_effect = [full_page, partial_page]

    config.rp_discovery_urls = ["https://rynekpierwotny.pl/api/v2/offers/offer/?s=offer-list&page=1&page_size=30"]
    results = discover_rp_investments(config, fetcher)
    assert fetcher.fetch_json.call_count == 2


def test_discover_rp_deduplicates(fetcher, config):
    page = _rp_page([_RP_SIMPLE_ITEM, _RP_SIMPLE_ITEM])
    fetcher.fetch_json.return_value = page
    results = discover_rp_investments(config, fetcher, identifier="123")
    ids = [r["id"] for r in results]
    assert ids.count("1001") == 1


# ---------------------------------------------------------------------------
# resolve_rp_vendor_id
# ---------------------------------------------------------------------------

def test_resolve_rp_vendor_id_from_html(fetcher):
    fetcher.fetch.return_value = '<script>"vendor": 9876</script>'
    vid = resolve_rp_vendor_id("dom-dev", fetcher)
    assert vid == "9876"


def test_resolve_rp_vendor_id_from_slug_suffix(fetcher):
    fetcher.fetch.return_value = "<html>no vendor json here</html>"
    vid = resolve_rp_vendor_id("dom-development-sa-955", fetcher)
    assert vid == "955"


def test_resolve_rp_vendor_id_returns_none(fetcher):
    fetcher.fetch.return_value = "<html></html>"
    vid = resolve_rp_vendor_id("unknown-dev", fetcher)
    assert vid is None
