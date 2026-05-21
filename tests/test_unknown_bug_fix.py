import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import json

from usi_scrapers.utils.scrapers import generic_download_dev_json
from usi_scrapers.api import process_batch
from usi_scrapers.models import ScraperConfig

@pytest.fixture
def mock_fetcher():
    f = MagicMock()
    f.config = MagicMock()
    return f

def test_generic_download_dev_json_resolves_slug_from_mapping(mock_fetcher, tmp_path):
    config = ScraperConfig(public_dir=tmp_path)
    mock_fetcher.config = config
    
    # Mock data that contains a valid slug and ID
    # For Otodom, the mapping for 'slug' is:
    # "path": "url", "regex": "deweloperzy/([^/]+)-ID\\d+"
    profile_data = {
        "url": "https://www.otodom.pl/pl/firmy/deweloperzy/atal-ID123",
        "owner": {"id": "123"}
    }
    
    def mock_fetch(url, f):
        return profile_data
        
    def extract_id(d):
        return "123"
        
    def extract_logo(d):
        return None

    resolved_slug = generic_download_dev_json(
        mock_fetcher, config, "https://dummy-url", None, "oto",
        fetch_func=mock_fetch,
        extract_id_func=extract_id,
        extract_logo_func=extract_logo
    )
    
    assert resolved_slug == "atal"
    # Verify file was created in correct folder
    assert (tmp_path / "USIdev" / "atal" / "raw_oto_123.json").exists()

def test_generic_download_dev_json_rejects_unknown_slug(mock_fetcher, tmp_path):
    config = ScraperConfig(public_dir=tmp_path)
    mock_fetcher.config = config
    
    # Mock data that contains 'unknown' in URL
    profile_data = {
        "url": "https://www.otodom.pl/pl/firmy/deweloperzy/unknown-ID123",
        "owner": {"id": "123"}
    }
    
    def mock_fetch(url, f):
        return profile_data
        
    def extract_id(d):
        return "123"

    resolved_slug = generic_download_dev_json(
        mock_fetcher, config, "https://dummy-url", None, "oto",
        fetch_func=mock_fetch,
        extract_id_func=extract_id,
        extract_logo_func=lambda x: None
    )
    
    assert resolved_slug is None
    # Verify folder was NOT created
    assert not (tmp_path / "USIdev" / "unknown").exists()

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_otodom")
def test_process_batch_fail_fast_on_unknown_slug(mock_scrape, mock_mgr_cls, mock_fetcher, tmp_path):
    config = ScraperConfig(public_dir=tmp_path)
    mock_mgr = MagicMock()
    mock_mgr_cls.return_value = mock_mgr
    
    # Scraper returns 'unknown' slug
    mock_scrape.return_value = {
        "developer_slug": "unknown",
        "investment_slug": "inv-1",
        "image_urls": []
    }
    
    results = process_batch(config, mock_fetcher, "otodom", ["url-1"], delay_range=(0,0))
    
    # Verify it failed
    assert mock_mgr.save_raw_data.call_count == 0
    assert mock_mgr.sync_images.call_count == 0
