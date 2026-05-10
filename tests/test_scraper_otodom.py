import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock
from usi_scrapers.scraper_otodom import (
    extract_next_data,
    scrape_otodom,
    discover_otodom_investments,
    discover_otodom_listing,
    _parse_otodom_slug,
    _parse_otodom_item,
)
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig


@pytest.fixture
def config(tmp_path):
    return ScraperConfig(public_dir=tmp_path)


@pytest.fixture
def fetcher(config):
    f = Fetcher(config)
    f.fetch = MagicMock()
    return f


# ---------------------------------------------------------------------------
# _parse_otodom_slug
# ---------------------------------------------------------------------------

def test_parse_otodom_slug_with_dash_id():
    slug, hash_id = _parse_otodom_slug("apartamenty-kameliowa-vi-etap-ID4AYaT")
    assert slug == "apartamenty-kameliowa-vi-etap"
    assert hash_id == "4AYaT"


def test_parse_otodom_slug_with_id_no_dash():
    slug, hash_id = _parse_otodom_slug("osiedleIDAbCd")
    assert slug == "osiedle"
    assert hash_id == "AbCd"


def test_parse_otodom_slug_no_id():
    slug, hash_id = _parse_otodom_slug("plain-slug")
    assert slug == "plain-slug"
    assert hash_id is None


# ---------------------------------------------------------------------------
# _parse_otodom_item
# ---------------------------------------------------------------------------

_ITEM = {
    "id": 67916467,
    "title": "Apartamenty Kameliowa VI Etap",
    "slug": "apartamenty-kameliowa-vi-etap-ID4AYaT",
    "images": [{"medium": "https://cdn.oto.pl/thumb.jpg"}],
    "agency": {"name": "GH Development"},
}


def test_parse_otodom_item_basic():
    parsed = _parse_otodom_item(_ITEM)
    assert parsed["id"] == 67916467
    assert parsed["slug"] == "apartamenty-kameliowa-vi-etap"
    assert parsed["hash_id"] == "4AYaT"
    assert parsed["developer"] == "GH Development"
    assert parsed["url"] == "https://www.otodom.pl/pl/oferta/apartamenty-kameliowa-vi-etap-ID4AYaT"
    assert parsed["image"] == "https://cdn.oto.pl/thumb.jpg"


def test_parse_otodom_item_advertiser_fallback():
    item = dict(_ITEM)
    item["agency"] = {}
    item["advertiser"] = {"name": "Fallback Dev"}
    parsed = _parse_otodom_item(item)
    assert parsed["developer"] == "Fallback Dev"


def test_parse_otodom_item_no_slug_returns_none():
    parsed = _parse_otodom_item({"id": 1, "title": "No slug"})
    assert parsed is None


def test_parse_otodom_item_explicit_offer_id():
    parsed = _parse_otodom_item(_ITEM, offer_id=99999)
    assert parsed["id"] == 99999


# ---------------------------------------------------------------------------
# extract_next_data
# ---------------------------------------------------------------------------

def test_extract_next_data_parses_correctly():
    html = """<html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props": {"pageProps": {"ad": {"title": "Test Ad", "id": 123}}}}
    </script></body></html>"""
    data = extract_next_data(html)
    assert data["ad"]["title"] == "Test Ad"


def test_extract_next_data_missing_returns_empty():
    assert extract_next_data("<html><body></body></html>") == {}


def test_extract_next_data_invalid_json_returns_empty():
    html = '<script id="__NEXT_DATA__" type="application/json">{invalid}</script>'
    assert extract_next_data(html) == {}


# ---------------------------------------------------------------------------
# scrape_otodom
# ---------------------------------------------------------------------------

def _make_html(ad_override=None):
    ad = {
        "id": 67916467,
        "title": "Testowa Inwestycja",
        "agency": {"id": 99, "name": "TestDev", "url": "https://www.otodom.pl/pl/firmy/deweloperzy/testdev-ID99"},
        "location": {"coordinates": {"latitude": 52.2, "longitude": 21.0}},
        "topInformation": [
            {"label": "project_finish_date", "values": ["2027-09-30"]}
        ],
        "images": [
            {"large": "https://cdn.oto.pl/1.jpg"},
            {"large": "https://cdn.oto.pl/2.jpg"},
        ],
    }
    if ad_override:
        ad.update(ad_override)
    payload = {"props": {"pageProps": {"ad": ad}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'


def test_scrape_otodom_success(fetcher):
    fetcher.fetch.return_value = _make_html()
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", "test-dev", "test-inv", fetcher)

    assert "error" not in result
    assert result["title"] == "Testowa Inwestycja"
    assert result["latitude"] == 52.2
    assert result["longitude"] == 21.0
    assert result["delivery_quarter"] == 3
    assert result["delivery_year"] == 2027
    assert len(result["image_urls"]) == 2


def test_scrape_otodom_delivery_fallback_to_estimated(fetcher):
    fetcher.fetch.return_value = _make_html({
        "topInformation": [],
        "investmentEstimatedDelivery": {"quarter": 2, "year": 2026},
    })
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", "test-dev", "test-inv", fetcher)
    assert result["delivery_quarter"] == 2
    assert result["delivery_year"] == 2026


def test_scrape_otodom_agency_slug_from_url(fetcher):
    fetcher.fetch.return_value = _make_html()
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", "unknown", "test-inv", fetcher)
    assert result["developer_slug"] == "testdev"


def test_scrape_otodom_no_agency_falls_back_to_owner(fetcher):
    fetcher.fetch.return_value = _make_html({
        "agency": None,
        "owner": {"name": "Jan Kowalski"},
    })
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", "test-dev", "test-inv", fetcher)
    assert result["agency_name"] == "Jan Kowalski"


def test_scrape_otodom_empty_images(fetcher):
    fetcher.fetch.return_value = _make_html({"images": []})
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", "test-dev", "test-inv", fetcher)
    assert result["image_urls"] == []


def test_scrape_otodom_fetch_failure(fetcher):
    fetcher.fetch.return_value = None
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", "test-dev", "test-inv", fetcher)
    assert "error" in result


# ---------------------------------------------------------------------------
# discover_otodom_investments (by agency ID)
# ---------------------------------------------------------------------------

def _make_agency_html(items, total_pages=1, current_page=1):
    # searchAds is directly under pageProps (not nested under data)
    payload = {"props": {"pageProps": {"searchAds": {
        "items": items,
        "pagination": {"totalPages": total_pages, "currentPage": current_page},
    }}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'


_AGENCY_ITEM = {
    "id": 111,
    "title": "Osiedle Testowe",
    "slug": "osiedle-testowe-ID4xF1A",
    "images": [{"medium": "https://cdn.oto.pl/thumb.jpg"}],
    "agency": {"name": "TestDev"},
}


def test_discover_otodom_investments_returns_offers(fetcher):
    fetcher.fetch.return_value = _make_agency_html([_AGENCY_ITEM])
    offers = discover_otodom_investments("99", fetcher)
    assert len(offers) == 1
    assert offers[0]["slug"] == "osiedle-testowe"
    assert offers[0]["hash_id"] == "4xF1A"
    assert "/pl/oferta/" in offers[0]["url"]


def test_discover_otodom_investments_empty(fetcher):
    fetcher.fetch.return_value = _make_agency_html([])
    assert discover_otodom_investments("99", fetcher) == []


def test_discover_otodom_investments_fetch_fail(fetcher):
    fetcher.fetch.return_value = None
    assert discover_otodom_investments("99", fetcher) == []


def test_discover_otodom_investments_pagination(fetcher):
    item_a = dict(_AGENCY_ITEM, id=1, slug="inv-a-ID1111")
    item_b = dict(_AGENCY_ITEM, id=2, slug="inv-b-ID2222")
    fetcher.fetch.side_effect = [
        _make_agency_html([item_a], total_pages=2, current_page=1),
        _make_agency_html([item_b], total_pages=2, current_page=2),
    ]
    offers = discover_otodom_investments("99", fetcher)
    assert len(offers) == 2
    assert fetcher.fetch.call_count == 2
    # Strona 2 musi być odpytana przez ?currentPage=2
    page2_url = fetcher.fetch.call_args_list[1][0][0]
    assert "currentPage=2" in page2_url


def test_discover_otodom_investments_deduplicates(fetcher):
    fetcher.fetch.side_effect = [
        _make_agency_html([_AGENCY_ITEM, _AGENCY_ITEM], total_pages=1),
    ]
    offers = discover_otodom_investments("99", fetcher)
    assert len(offers) == 1


def test_discover_otodom_investments_limit(fetcher):
    items = [dict(_AGENCY_ITEM, id=i, slug=f"inv-{i}-ID{i}000") for i in range(3)]
    fetcher.fetch.return_value = _make_agency_html(items, total_pages=5)
    offers = discover_otodom_investments("99", fetcher, limit=2)
    assert len(offers) == 2


# ---------------------------------------------------------------------------
# discover_otodom_listing (by listing URL, paginated)
# ---------------------------------------------------------------------------

def _make_listing_html(items, total_pages=1):
    payload = {
        "props": {
            "pageProps": {
                "data": {
                    "searchAds": {
                        "items": items,
                        "pagination": {"totalPages": total_pages},
                    }
                }
            }
        }
    }
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'


def test_discover_otodom_listing_single_page(fetcher):
    fetcher.fetch.return_value = _make_listing_html([_AGENCY_ITEM])
    offers = discover_otodom_listing("https://www.otodom.pl/pl/inwestycje/oferty/warszawa", fetcher)
    assert len(offers) == 1
    assert "/pl/oferta/" in offers[0]["url"]


def test_discover_otodom_listing_pagination(fetcher):
    item_a = dict(_AGENCY_ITEM, id=1, slug="inv-a-ID1111")
    item_b = dict(_AGENCY_ITEM, id=2, slug="inv-b-ID2222")
    fetcher.fetch.side_effect = [
        _make_listing_html([item_a], total_pages=2),
        _make_listing_html([item_b], total_pages=2),
    ]
    offers = discover_otodom_listing("https://www.otodom.pl/pl/inwestycje/oferty/warszawa", fetcher)
    assert len(offers) == 2
    assert fetcher.fetch.call_count == 2


def test_discover_otodom_listing_deduplicates(fetcher):
    fetcher.fetch.side_effect = [
        _make_listing_html([_AGENCY_ITEM, _AGENCY_ITEM], total_pages=2),
        _make_listing_html([], total_pages=2),
    ]
    offers = discover_otodom_listing("https://www.otodom.pl/pl/inwestycje/oferty/warszawa", fetcher)
    assert len(offers) == 1


def test_discover_otodom_listing_limit(fetcher):
    items = [dict(_AGENCY_ITEM, id=i, slug=f"inv-{i}-ID{i}000") for i in range(10)]
    fetcher.fetch.return_value = _make_listing_html(items, total_pages=5)
    offers = discover_otodom_listing("https://www.otodom.pl/pl/inwestycje/oferty/warszawa", fetcher, limit=3)
    assert len(offers) == 3
