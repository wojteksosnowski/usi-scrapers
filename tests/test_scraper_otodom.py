import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock
from usi_scrapers.scraper_otodom import extract_next_data, scrape_otodom
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig

@pytest.fixture
def fetcher():
    config = ScraperConfig(public_dir=Path("/tmp/public"), scraperapi_key="test_key")
    f = Fetcher(config)
    f.fetch = MagicMock()
    return f

@pytest.fixture
def scraper_config():
    return ScraperConfig(public_dir=Path("/tmp/public"))

def test_extract_next_data():
    html = """
    <html>
        <body>
            <script id="__NEXT_DATA__" type="application/json">
            {"props": {"pageProps": {"ad": {"title": "Test Ad", "id": 123}}}}
            </script>
        </body>
    </html>
    """
    data = extract_next_data(html)
    assert data["ad"]["title"] == "Test Ad"
    assert data["ad"]["id"] == 123

_MOCK_OTODOM_HTML = """
<html><body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "ad": {
        "title": "Testowa Inwestycja",
        "agency": {"id": 99, "name": "TestDev"},
        "location": {
          "coordinates": {"latitude": 52.2, "longitude": 21.0}
        },
        "topInformation": [
          {"label": "project_finish_date", "values": ["2027-09-30"]}
        ],
        "images": [
          {"large": "https://example.com/1.jpg"},
          {"large": "https://example.com/2.jpg"}
        ]
      }
    }
  }
}
</script>
</body></html>
"""

def test_scrape_otodom_success(fetcher, scraper_config):
    url = "https://www.otodom.pl/pl/inwestycja/test-ID123"
    fetcher.fetch.return_value = _MOCK_OTODOM_HTML
    
    result = scrape_otodom(url, "test-dev", "test-inv", fetcher)
    
    assert "error" not in result
    assert result["title"] == "Testowa Inwestycja"
    assert result["latitude"] == 52.2
    assert result["longitude"] == 21.0
    assert result["delivery_quarter"] == 3
    assert result["delivery_year"] == 2027
    assert len(result["image_urls"]) == 2
