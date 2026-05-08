import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from usi_scrapers.scraper_rp import fetch_rp_details, fetch_rp_gallery
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig

@pytest.fixture
def fetcher():
    config = ScraperConfig(public_dir=Path("/tmp/public"), scraperapi_key="test_key")
    f = Fetcher(config)
    # Mock the internal fetch_json to avoid actual network/curl calls
    f.fetch_json = MagicMock()
    return f

def test_fetch_rp_details(fetcher):
    offer_id = "123"
    mock_response = {"id": 123, "name": "Test Investment"}
    fetcher.fetch_json.return_value = mock_response
    
    details = fetch_rp_details(offer_id, fetcher)
    
    assert details == mock_response
    fetcher.fetch_json.assert_called_once()
    args, kwargs = fetcher.fetch_json.call_args
    assert "123" in args[0]

def test_fetch_rp_gallery(fetcher):
    offer_id = "123"
    mock_response = {
        "gallery": [
            {"image": {"g_img_1500": "https://example.com/1.jpg"}},
            {"image": {"g_img_1500": "https://example.com/2.jpg"}}
        ]
    }
    fetcher.fetch_json.return_value = mock_response
    
    gallery = fetch_rp_gallery(offer_id, fetcher)
    
    assert len(gallery) == 2
    assert "https://example.com/1.jpg" in gallery
    assert "https://example.com/2.jpg" in gallery
