import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
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
    assert parsed["id"] == "4AYaT"
    assert parsed["url"] == "https://www.otodom.pl/pl/oferta/apartamenty-kameliowa-vi-etap-ID4AYaT"


def test_parse_otodom_item_no_slug_returns_none():
    parsed = _parse_otodom_item({"id": 1, "title": "No slug"})
    assert parsed is None


def test_parse_otodom_item_explicit_offer_id():
    parsed = _parse_otodom_item(_ITEM, offer_id=99999)
    # Even if offer_id is passed, it should prefer the hash from the slug if available
    assert parsed["id"] == "4AYaT"


# ---------------------------------------------------------------------------
# extract_next_data
# ---------------------------------------------------------------------------

def test_extract_next_data_parses_correctly():
    html = """<html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props": {"pageProps": {"ad": {"title": "Test Ad", "id": 123}}}}
    </script></body></html>"""
    data = extract_next_data(html)
    assert data["props"]["pageProps"]["ad"]["title"] == "Test Ad"


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


@patch("usi_scrapers.scraper_otodom.save_images")
@patch("usi_scrapers.scraper_otodom.download_raw_otodom_dev_json")
def test_scrape_otodom_success(mock_dl, mock_save_images, fetcher):
    fetcher.fetch.return_value = _make_html()
    mock_save_images.return_value = ["1.webp", "2.webp"]
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", fetcher)

    assert "error" not in result
    assert result["title"] == "Testowa Inwestycja"
    assert result["latitude"] == 52.2
    assert result["longitude"] == 21.0
    assert result["delivery_quarter"] == 3
    assert result["delivery_year"] == 2027
    assert len(result["image_urls"]) == 2


@patch("usi_scrapers.scraper_otodom.save_images")
@patch("usi_scrapers.scraper_otodom.download_raw_otodom_dev_json")
def test_scrape_otodom_delivery_fallback_to_estimated(mock_dl, mock_save_images, fetcher):
    fetcher.fetch.return_value = _make_html({
        "topInformation": [],
        "investmentEstimatedDelivery": {"quarter": 2, "year": 2026},
    })
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", fetcher)
    assert result["delivery_quarter"] == 2
    assert result["delivery_year"] == 2026


@patch("usi_scrapers.scraper_otodom.download_raw_otodom_dev_json")
def test_scrape_otodom_agency_slug_from_url(mock_dl, fetcher):
    mock_dl.return_value = "testdev"
    fetcher.fetch.return_value = _make_html()
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", fetcher)
    assert result["developer_slug"] == "testdev"


def test_scrape_otodom_no_agency_falls_back_to_owner(fetcher):
    fetcher.fetch.return_value = _make_html({
        "agency": None,
        "owner": {"name": "Jan Kowalski"},
    })
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", fetcher)
    assert result["agency_name"] == "Jan Kowalski"


@patch("usi_scrapers.scraper_otodom.download_raw_otodom_dev_json")
def test_scrape_otodom_empty_images(mock_dl, fetcher):
    fetcher.fetch.return_value = _make_html({"images": []})
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", fetcher)
    assert result["image_urls"] == []


@patch("usi_scrapers.scraper_otodom.download_raw_otodom_dev_json")
def test_scrape_otodom_inactive_listing_returns_error(mock_dl, fetcher):
    # Mock an archived listing
    fetcher.fetch.return_value = _make_html({
        "status": "archive"
    })
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", fetcher)
    assert "error" in result
    assert "inactive" in result["error"]
    assert "archive" in result["error"]


def test_scrape_otodom_fetch_failure(fetcher):
    fetcher.fetch.return_value = None
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", fetcher)
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


def test_discover_otodom_investments_returns_offers(fetcher, config):
    fetcher.fetch.return_value = _make_agency_html([_AGENCY_ITEM])
    offers = discover_otodom_investments(config, fetcher, identifier="99")
    assert len(offers) == 1
    assert offers[0]["id"] == "4xF1A"
    assert "/pl/oferta/" in offers[0]["url"]
    assert "osiedle-testowe" in offers[0]["url"]


def test_discover_otodom_investments_empty(fetcher, config):
    fetcher.fetch.return_value = _make_agency_html([])
    assert discover_otodom_investments(config, fetcher, identifier="99") == []


def test_discover_otodom_investments_fetch_fail(fetcher, config):
    fetcher.fetch.return_value = None
    assert discover_otodom_investments(config, fetcher, identifier="99") == []


def test_discover_otodom_investments_pagination(fetcher, config):
    item_a = dict(_AGENCY_ITEM, id=1, slug="inv-a-ID1111")
    item_b = dict(_AGENCY_ITEM, id=2, slug="inv-b-ID2222")
    fetcher.fetch.side_effect = [
        _make_agency_html([item_a], total_pages=2, current_page=1),
        _make_agency_html([item_b], total_pages=2, current_page=2),
    ]
    offers = discover_otodom_investments(config, fetcher, identifier="99")
    assert len(offers) == 2
    assert fetcher.fetch.call_count == 2
    # Strona 2 musi być odpytana przez ?currentPage=2
    page2_url = fetcher.fetch.call_args_list[1][0][0]
    assert "currentPage=2" in page2_url


def test_discover_otodom_investments_deduplicates(fetcher, config):
    fetcher.fetch.side_effect = [
        _make_agency_html([_AGENCY_ITEM, _AGENCY_ITEM], total_pages=1),
    ]
    offers = discover_otodom_investments(config, fetcher, identifier="99")
    assert len(offers) == 1


def test_discover_otodom_investments_limit(fetcher, config):
    items = [dict(_AGENCY_ITEM, id=i, slug=f"inv-{i}-ID{i}000") for i in range(3)]
    fetcher.fetch.return_value = _make_agency_html(items, total_pages=5)
    offers = discover_otodom_investments(config, fetcher, identifier="99", limit=2)
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


def test_discover_otodom_listing_single_page(fetcher, config):
    fetcher.fetch.return_value = _make_listing_html([_AGENCY_ITEM])
    offers = discover_otodom_listing(config, fetcher, identifier="https://www.otodom.pl/pl/inwestycje/oferty/warszawa")
    assert len(offers) == 1
    assert "/pl/oferta/" in offers[0]["url"]


def test_discover_otodom_listing_pagination(fetcher, config):
    item_a = dict(_AGENCY_ITEM, id=1, slug="inv-a-ID1111")
    item_b = dict(_AGENCY_ITEM, id=2, slug="inv-b-ID2222")
    fetcher.fetch.side_effect = [
        _make_listing_html([item_a], total_pages=2),
        _make_listing_html([item_b], total_pages=2),
    ]
    offers = discover_otodom_listing(config, fetcher, identifier="https://www.otodom.pl/pl/inwestycje/oferty/warszawa")
    assert len(offers) == 2
    assert fetcher.fetch.call_count == 2


def test_discover_otodom_listing_deduplicates(fetcher, config):
    fetcher.fetch.side_effect = [
        _make_listing_html([_AGENCY_ITEM, _AGENCY_ITEM], total_pages=2),
        _make_listing_html([], total_pages=2),
    ]
    offers = discover_otodom_listing(config, fetcher, identifier="https://www.otodom.pl/pl/inwestycje/oferty/warszawa")
    assert len(offers) == 1


def test_discover_otodom_listing_limit(fetcher, config):
    items = [dict(_AGENCY_ITEM, id=i, slug=f"inv-{i}-ID{i}000") for i in range(10)]
    fetcher.fetch.return_value = _make_listing_html(items, total_pages=5)
    offers = discover_otodom_listing(config, fetcher, identifier="https://www.otodom.pl/pl/inwestycje/oferty/warszawa", limit=3)
    assert len(offers) == 3

def test_discover_otodom_investments_global(fetcher, config):
    config.otodom_discovery_urls = ["https://www.otodom.pl/test1", "https://www.otodom.pl/test2"]
    item1 = dict(_AGENCY_ITEM, id=1, slug="inv-1-ID1")
    item2 = dict(_AGENCY_ITEM, id=2, slug="inv-2-ID2")
    # item1 repeated on second page to test deduplication
    fetcher.fetch.side_effect = [
        _make_listing_html([item1], total_pages=1),
        _make_listing_html([item2, item1], total_pages=1),
    ]
    offers = discover_otodom_investments(config, fetcher, identifier=None)
    assert len(offers) == 2
    assert {o["id"] for o in offers} == {"1", "2"}
    assert fetcher.fetch.call_count == 2
import pytest
from unittest.mock import MagicMock, patch
from usi_scrapers.scraper_otodom import scrape_otodom

@patch("usi_scrapers.scraper_otodom.fetch_otodom_html")
@patch("usi_scrapers.scraper_otodom.download_raw_otodom_dev_json")
@patch("usi_scrapers.scraper_otodom.lookup_developer_by_id")
@patch("usi_scrapers.scraper_otodom.lookup_investment_by_id")
def test_scrape_otodom_fallback_slug(
    mock_inv_lookup, mock_dev_lookup, mock_download_dev, mock_fetch_html, fetcher
):
    # Setup mock data for investment page
    mock_fetch_html.return_value = """
    <script id="__NEXT_DATA__" type="application/json">
    {
        "props": {
            "pageProps": {
                "ad": {
                    "id": 12345,
                    "title": "Test Investment",
                    "slug": "test-investment-ID123",
                    "agency": {
                        "id": 10411233,
                        "name": "Quadro Development",
                        "url": "/pl/wyniki/sprzedaz/inwestycja?sellerId=10411233"
                    },
                    "location": {"coordinates": {"latitude": 52.0, "longitude": 21.0}},
                    "status": "active",
                    "images": []
                }
            }
        }
    }
    </script>
    """
    
    # Simulate that we don't have an existing slug for this ID
    mock_dev_lookup.return_value = None
    mock_inv_lookup.return_value = None
    
    # Simulate that downloading the developer profile (which is a search page) fails to yield a slug
    mock_download_dev.return_value = None
    
    url = "https://www.otodom.pl/pl/oferta/test-investment-ID123"
    result = scrape_otodom(url, fetcher)
    
    assert result["developer_slug"] == "quadro-development"
    assert result["agency_name"] == "Quadro Development"
    assert result["agency_id"] == 10411233
    assert mock_download_dev.called
    
def test_scrape_otodom_no_overwrite_existing_slug(
    fetcher
):
    # Testing that if we already have a slug from lookup, it is not lost if download_raw_otodom_dev_json returns None
    from usi_scrapers.scraper_otodom import scrape_otodom
    
    with patch("usi_scrapers.scraper_otodom.fetch_otodom_html") as mock_fetch_html, \
         patch("usi_scrapers.scraper_otodom.download_raw_otodom_dev_json") as mock_download_dev, \
         patch("usi_scrapers.scraper_otodom.lookup_developer_by_id") as mock_dev_lookup, \
         patch("usi_scrapers.scraper_otodom.lookup_investment_by_id") as mock_inv_lookup:
         
        mock_fetch_html.return_value = """
        <script id="__NEXT_DATA__" type="application/json">
        {
            "props": {
                "pageProps": {
                    "ad": {
                        "id": 12345,
                        "title": "Test Investment",
                        "slug": "test-investment-ID123",
                        "agency": {
                            "id": 10411233,
                            "name": "Quadro Development",
                            "url": "/pl/wyniki/sprzedaz/inwestycja?sellerId=10411233"
                        },
                        "location": {"coordinates": {"latitude": 52.0, "longitude": 21.0}},
                        "status": "active",
                        "images": []
                    }
                }
            }
        }
        </script>
        """
        
        # We already know this developer as 'existing-slug'
        mock_dev_lookup.return_value = "existing-slug"
        mock_inv_lookup.return_value = None
        mock_download_dev.return_value = None # profile download failed/returned nothing
        
        url = "https://www.otodom.pl/pl/oferta/test-investment-ID123"
        result = scrape_otodom(url, fetcher)
        
        # Should retain the existing slug instead of being None or falling back to 'quadro-development'
        assert result["developer_slug"] == "existing-slug"
import pytest
from unittest.mock import MagicMock, patch
from usi_scrapers.scraper_otodom import scrape_otodom

def test_scrape_otodom_search_results_style_slug(
    fetcher
):
    # Testing extraction from search-results style pageProps
    with patch("usi_scrapers.scraper_otodom.fetch_otodom_html") as mock_fetch_html, \
         patch("usi_scrapers.scraper_otodom.lookup_developer_by_id") as mock_dev_lookup, \
         patch("usi_scrapers.scraper_otodom.lookup_investment_by_id") as mock_inv_lookup, \
         patch("usi_scrapers.scraper_otodom.save_raw_json") as mock_save_raw, \
         patch("usi_scrapers.scraper_otodom.save_dev_raw_json") as mock_save_dev, \
         patch("usi_scrapers.utils.scrapers.download_developer_logo") as mock_logo:
         
        # Investment page HTML
        mock_fetch_html.side_effect = [
            # 1. Investment page
            """
            <script id="__NEXT_DATA__" type="application/json">
            {
                "props": {
                    "pageProps": {
                        "ad": {
                            "id": 12345,
                            "title": "Test Inv",
                            "slug": "test-inv-ID1",
                            "agency": {
                                "id": 999,
                                "name": "Deep Agency",
                                "url": "/pl/wyniki/sprzedaz/inwestycja?sellerId=999"
                            },
                            "location": {"coordinates": {"latitude": 52.0, "longitude": 21.0}},
                            "status": "active",
                            "images": []
                        }
                    }
                }
            }
            </script>
            """,
            # 2. Developer "search-results" style page
            """
            <script id="__NEXT_DATA__" type="application/json">
            {
                "props": {
                    "pageProps": {
                        "data": {
                            "searchAds": {
                                "items": [
                                    {
                                        "agency": {
                                            "id": 999,
                                            "name": "Deep Agency",
                                            "slug": "deep-agency-canonical-ID999",
                                            "imageUrl": "https://cdn.pl/logo.png"
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
            </script>
            """
        ]
        
        mock_dev_lookup.return_value = None
        mock_inv_lookup.return_value = None
        
        url = "https://www.otodom.pl/pl/oferta/test-inv-ID1"
        result = scrape_otodom(url, fetcher)
        
        # Should find the canonical slug from the search results items, NOT use slugify fallback
        assert result["developer_slug"] == "deep-agency-canonical"
        assert result["agency_id"] == 999
        assert mock_logo.called
        # Verify first arg to logo download is the imageUrl from nested items
        assert mock_logo.call_args[0][0] == "https://cdn.pl/logo.png"
