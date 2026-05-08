import pytest
import requests_mock
from pathlib import Path
from unittest.mock import MagicMock
from usi_scrapers.scraper_to import (
    parse_to_product,
    extract_geo,
    extract_gallery_urls,
    _extract_to_id,
    scrape_tabelaofert
)
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig

TO_URL = "https://tabelaofert.pl/inwestycja/test-inv,i12345"

@pytest.fixture
def fetcher():
    config = ScraperConfig(public_dir=Path("/tmp/public"), scraperapi_key="test_key")
    f = Fetcher(config)
    f.fetch = MagicMock()
    return f

@pytest.fixture
def scraper_config():
    return ScraperConfig(public_dir=Path("/tmp/public"))

def test_parse_to_product():
    html = """
    <html>
    <script type="application/ld+json">
    {
        "@type": "Product",
        "name": "Test Investment",
        "brand": {"name": "Test Dev"}
    }
    </script>
    </html>
    """
    product = parse_to_product(html)
    assert product["name"] == "Test Investment"
    assert product["brand"]["name"] == "Test Dev"

def test_extract_geo():
    product = {
        "offers": {
            "offers": [{
                "itemOffered": {
                    "geo": {"latitude": "52.1", "longitude": "21.1"}
                }
            }]
        }
    }
    lat, lng = extract_geo(product)
    assert lat == 52.1
    assert lng == 21.1

def test_extract_gallery_urls():
    html = """
    <div class="gallery">
        <a href="https://content.tabelaofert.pl/img1.jpg"></a>
        <img src="https://content.tabelaofert.pl/img2.jpg">
    </div>
    """
    urls = extract_gallery_urls(html)
    assert "https://content.tabelaofert.pl/img1.jpg" in urls
    assert "https://content.tabelaofert.pl/img2.jpg" in urls

def test_extract_to_id():
    assert _extract_to_id(TO_URL) == "12345"
    assert _extract_to_id("https://tabelaofert.pl/inwestycja/abc,i67890/") == "67890"

def test_scrape_tabelaofert_success(fetcher, scraper_config):
    html = """
    <script type="application/ld+json">
    {
        "@type": "Product",
        "name": "Test Investment",
        "brand": {"name": "Test Dev"},
        "offers": {"offerCount": 10}
    }
    </script>
    """
    fetcher.fetch.return_value = html
    
    result = scrape_tabelaofert(TO_URL, "test-dev", "test-inv", fetcher)
    
    assert result["source"] == "tabelaofert.pl"
    assert result["to_id"] == "12345"
    assert result["name"] == "Test Investment"
    assert result["properties_count"] == 10
    assert "raw_details" in result
