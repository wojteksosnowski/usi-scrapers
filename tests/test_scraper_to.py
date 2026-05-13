import pytest
import json
import requests_mock
from pathlib import Path
from unittest.mock import MagicMock, patch
from usi_scrapers.scraper_to import (
    parse_to_product,
    extract_geo,
    extract_gallery_urls,
    extract_to_api_token,
    fetch_to_api_gallery,
    extract_to_data,
    filter_investment_images,
    discover_to_listing,
    _extract_to_id,
    _cdn_filename,
    scrape_tabelaofert,
)
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig

TO_URL = "https://tabelaofert.pl/inwestycja/test-inv,i12345"

@pytest.fixture
def config(tmp_path):
    return ScraperConfig(public_dir=tmp_path, scraperapi_key="test_key")

@pytest.fixture
def fetcher(config):
    f = Fetcher(config)
    f.fetch = MagicMock()
    f.fetch_json = MagicMock()
    return f


# ---------------------------------------------------------------------------
# _extract_to_id
# ---------------------------------------------------------------------------

def test_extract_to_id_standard():
    assert _extract_to_id(TO_URL) == "12345"

def test_extract_to_id_trailing_slash():
    assert _extract_to_id("https://tabelaofert.pl/inwestycja/abc,i67890/") == "67890"

def test_extract_to_id_none():
    assert _extract_to_id(None) is None

def test_extract_to_id_no_match():
    assert _extract_to_id("https://tabelaofert.pl/katalog") is None


# ---------------------------------------------------------------------------
# _cdn_filename
# ---------------------------------------------------------------------------

def test_cdn_filename_plain():
    assert _cdn_filename("https://content.tabelaofert.pl/zdjecia/inwestycja-01.jpg") == "inwestycja-01.jpg"

def test_cdn_filename_with_scale_prefix():
    url = "https://tabelaofert.pl/oferty/zdjecia/quality_70,scale_425x283,ID-32981-01_Budynek.jpg"
    assert _cdn_filename(url) == "ID-32981-01_Budynek.jpg"


# ---------------------------------------------------------------------------
# parse_to_product
# ---------------------------------------------------------------------------

def test_parse_to_product():
    html = """<html><script type="application/ld+json">
    {"@type": "Product", "name": "Test Investment", "brand": {"name": "Test Dev"}}
    </script></html>"""
    product = parse_to_product(html)
    assert product["name"] == "Test Investment"
    assert product["brand"]["name"] == "Test Dev"

def test_parse_to_product_missing_returns_empty():
    assert parse_to_product("<html></html>") == {}

def test_parse_to_product_invalid_json_skipped():
    html = '<script type="application/ld+json">{invalid json "@type":"Product"}</script>'
    assert parse_to_product(html) == {}


# ---------------------------------------------------------------------------
# extract_geo
# ---------------------------------------------------------------------------

def test_extract_geo():
    product = {
        "offers": {
            "offers": [{"itemOffered": {"geo": {"latitude": "52.1", "longitude": "21.1"}}}]
        }
    }
    lat, lng = extract_geo(product)
    assert lat == 52.1
    assert lng == 21.1

def test_extract_geo_no_offers():
    lat, lng = extract_geo({})
    assert lat is None and lng is None

def test_extract_geo_invalid_values():
    product = {
        "offers": {
            "offers": [{"itemOffered": {"geo": {"latitude": "N/A", "longitude": "N/A"}}}]
        }
    }
    lat, lng = extract_geo(product)
    assert lat is None and lng is None


# ---------------------------------------------------------------------------
# extract_to_api_token
# ---------------------------------------------------------------------------

def test_extract_to_api_token_found():
    html = '<script src="/_next/static/chunks/main-app-c1661a4a02.js"></script>'
    token = extract_to_api_token(html)
    assert token == "vc1661a4a02"

def test_extract_to_api_token_not_found():
    assert extract_to_api_token("<html></html>") is None


# ---------------------------------------------------------------------------
# fetch_to_api_gallery
# ---------------------------------------------------------------------------

def test_fetch_to_api_gallery(fetcher):
    fetcher.fetch_json.return_value = {
        "data": {
            "images": [
                {"url": "https://content.tabelaofert.pl/img1.webp"},
                {"url": "https://content.tabelaofert.pl/img2.webp"},
            ]
        }
    }
    urls = fetch_to_api_gallery("12345", "vc1661a4a02", fetcher)
    assert len(urls) == 2
    assert "https://content.tabelaofert.pl/img1.webp" in urls

def test_fetch_to_api_gallery_empty_response(fetcher):
    fetcher.fetch_json.return_value = None
    assert fetch_to_api_gallery("12345", "vc1661a4a02", fetcher) == []

def test_fetch_to_api_gallery_calls_correct_url(fetcher):
    fetcher.fetch_json.return_value = {"data": {"images": []}}
    fetch_to_api_gallery("99999", "vdeadbeef01", fetcher)
    called_url = fetcher.fetch_json.call_args[0][0]
    assert "99999" in called_url
    assert "vdeadbeef01" in called_url
    assert "galeria" in called_url


# ---------------------------------------------------------------------------
# extract_gallery_urls (HTML fallback)
# ---------------------------------------------------------------------------

def test_extract_gallery_urls_from_html():
    html = """
    <a href="https://content.tabelaofert.pl/img1.jpg"></a>
    <img src="https://content.tabelaofert.pl/img2.webp">
    """
    urls = extract_gallery_urls(html)
    assert any("img1.jpg" in u for u in urls)
    assert any("img2.webp" in u for u in urls)

def test_extract_gallery_urls_skips_thumbnails():
    html = '<img src="https://content.tabelaofert.pl/thumb_200x200_photo.jpg">'
    urls = extract_gallery_urls(html)
    assert urls == []

def test_extract_gallery_urls_stops_at_other_investments():
    html = """
    <img src="https://content.tabelaofert.pl/our-photo.jpg">
    Inne inwestycje
    <img src="https://content.tabelaofert.pl/other-photo.jpg">
    """
    urls = extract_gallery_urls(html)
    assert any("our-photo.jpg" in u for u in urls)
    assert not any("other-photo.jpg" in u for u in urls)


# ---------------------------------------------------------------------------
# extract_to_data — central extraction
# ---------------------------------------------------------------------------

_PRODUCT_JSON = json.dumps({
    "@type": "Product",
    "name": "Osiedle z JSON",
    "brand": {"name": "DevCo"},
    "offers": {
        "offers": [{
            "itemOffered": {
                "geo": {"latitude": "52.0", "longitude": "21.0"},
                "address": {"streetAddress": "ul. Testowa 1", "addressLocality": "Warszawa", "addressRegion": "mazowieckie"}
            }
        }]
    }
})

_TOKEN_SCRIPT = '/_next/static/chunks/main-app-aabbcc1122.js'

_API_HTML = f"""
<html>
<script src="{_TOKEN_SCRIPT}"></script>
<script type="application/ld+json">{_PRODUCT_JSON}</script>
</html>
"""


def test_extract_to_data_uses_api_gallery_when_available(fetcher):
    fetcher.fetch_json.return_value = {
        "data": {"images": [{"url": "https://content.tabelaofert.pl/api-img.webp"}]}
    }
    data = extract_to_data(_API_HTML, TO_URL, fetcher=fetcher)
    assert "https://content.tabelaofert.pl/api-img.webp" in data["_raw_gallery_urls"]


def test_extract_to_data_falls_back_to_html_gallery(fetcher):
    fetcher.fetch_json.return_value = None
    html = _API_HTML + '<img src="https://content.tabelaofert.pl/html-img.jpg">'
    data = extract_to_data(html, TO_URL, fetcher=fetcher)
    assert any("html-img.jpg" in u for u in data["_raw_gallery_urls"])


def test_extract_to_data_extracts_geo(fetcher):
    fetcher.fetch_json.return_value = {"data": {"images": []}}
    data = extract_to_data(_API_HTML, TO_URL, fetcher=fetcher)
    assert data["_extracted_location"]["latitude"] == 52.0
    assert data["_extracted_location"]["longitude"] == 21.0


def test_extract_to_data_no_fetcher_skips_api():
    data = extract_to_data(_API_HTML, TO_URL, fetcher=None)
    # Without fetcher the API gallery is skipped; HTML fallback runs
    assert "_raw_gallery_urls" in data


# ---------------------------------------------------------------------------
# filter_investment_images
# ---------------------------------------------------------------------------

def test_filter_investment_images_excludes_maps():
    product = {"image": "https://content.tabelaofert.pl/osiedle-abc-01.jpg"}
    urls = [
        "https://content.tabelaofert.pl/osiedle-abc-01.jpg",
        "https://content.tabelaofert.pl/mapa-location.jpg",
    ]
    filtered = filter_investment_images(urls, product)
    assert any("osiedle-abc-01" in u for u in filtered)
    assert not any("mapa-location" in u for u in filtered)


def test_filter_investment_images_deduplicates_by_scale():
    # _cdn_filename strips the comma-prefix so both URLs share the same key
    product = {"image": "https://content.tabelaofert.pl/zdjecia/quality_70,scale_425x283,osiedle-abc-01.jpg"}
    urls = [
        "https://content.tabelaofert.pl/zdjecia/quality_70,scale_300x200,osiedle-abc-01.jpg",
        "https://content.tabelaofert.pl/zdjecia/quality_70,scale_1200x800,osiedle-abc-01.jpg",
    ]
    filtered = filter_investment_images(urls, product)
    assert len(filtered) == 1
    assert "scale_1200" in filtered[0]


def test_filter_investment_images_fallback_when_empty(fetcher):
    product = {"image": None}
    urls = [
        "https://content.tabelaofert.pl/photo-a.jpg",
        "https://content.tabelaofert.pl/mapa-x.jpg",
    ]
    filtered = filter_investment_images(urls, product)
    assert any("photo-a" in u for u in filtered)
    assert not any("mapa-x" in u for u in filtered)


# ---------------------------------------------------------------------------
# discover_to_listing
# ---------------------------------------------------------------------------

_LISTING_HTML_PAGE1 = """
<html>
<a href="/inwestycja/osiedle-zielone,i11111">Osiedle</a>
<img data-developer="DevCo" src="https://content.tabelaofert.pl/photo.jpg">
<a rel="next" href="?page=2">Next</a>
</html>
"""

_LISTING_HTML_PAGE2 = """
<html>
<a href="/inwestycja/osiedle-czerwone,i22222">Osiedle 2</a>
</html>
"""


def test_discover_to_listing_single_page(fetcher, config):
    fetcher.fetch.return_value = _LISTING_HTML_PAGE1.replace('<a rel="next"', '<span>')
    offers = discover_to_listing(config, fetcher, identifier="https://tabelaofert.pl/lista")
    assert len(offers) == 1
    assert offers[0]["id"] == "11111"
    assert offers[0]["url"] == "https://tabelaofert.pl/inwestycja/osiedle-zielone,i11111"


def test_discover_to_listing_pagination(fetcher, config):
    fetcher.fetch.side_effect = [_LISTING_HTML_PAGE1, _LISTING_HTML_PAGE2]
    offers = discover_to_listing(config, fetcher, identifier="https://tabelaofert.pl/lista")
    assert len(offers) == 2
    ids = {o["id"] for o in offers}
    assert ids == {"11111", "22222"}


def test_discover_to_listing_deduplicates(fetcher, config):
    # Page 2 returns same item — should be deduplicated. Page 3 is empty to end pagination.
    fetcher.fetch.side_effect = [_LISTING_HTML_PAGE1, _LISTING_HTML_PAGE1, "<html></html>"]
    offers = discover_to_listing(config, fetcher, identifier="https://tabelaofert.pl/lista")
    assert len([o for o in offers if o["id"] == "11111"]) == 1


def test_discover_to_listing_limit(fetcher, config):
    html = """<html>
    <a href="/inwestycja/inv-a,i1">A</a>
    <a href="/inwestycja/inv-b,i2">B</a>
    <a href="/inwestycja/inv-c,i3">C</a>
    </html>"""
    fetcher.fetch.return_value = html
    offers = discover_to_listing(config, fetcher, identifier="https://tabelaofert.pl/lista", limit=2)
    assert len(offers) == 2


def test_discover_to_listing_no_offers(fetcher, config):
    fetcher.fetch.return_value = "<html><p>Brak wyników</p></html>"
    offers = discover_to_listing(config, fetcher, identifier="https://tabelaofert.pl/lista")
    assert offers == []


# ---------------------------------------------------------------------------
# scrape_tabelaofert — end-to-end
# ---------------------------------------------------------------------------

_SCRAPE_HTML = f"""
<html>
<h1><span>Osiedle Testowe<span>DevCo</span></span></h1>
<script src="{_TOKEN_SCRIPT}"></script>
<script type="application/ld+json">{_PRODUCT_JSON}</script>
</html>
"""


def test_scrape_tabelaofert_success(fetcher):
    fetcher.fetch.return_value = _SCRAPE_HTML
    fetcher.fetch_json.return_value = {"data": {"images": [{"url": "https://content.tabelaofert.pl/img.webp"}]}}

    result = scrape_tabelaofert(TO_URL, fetcher)

    assert result["source"] == "tabelaofert.pl"
    assert result["to_id"] == "12345"
    assert result["latitude"] == 52.0
    assert result["longitude"] == 21.0
    assert "raw_details" in result


def test_scrape_tabelaofert_images_in_result(fetcher):
    fetcher.fetch.return_value = _SCRAPE_HTML
    fetcher.fetch_json.return_value = {
        "data": {
            "images": [
                {"url": "https://content.tabelaofert.pl/osiedle-z-json-01.webp"},
                {"url": "https://content.tabelaofert.pl/osiedle-z-json-02.webp"},
            ]
        }
    }
    result = scrape_tabelaofert(TO_URL, fetcher)
    assert len(result["image_urls"]) > 0


def test_scrape_tabelaofert_fetch_failure(fetcher):
    fetcher.fetch.return_value = None
    result = scrape_tabelaofert(TO_URL, fetcher)
    assert "error" in result
