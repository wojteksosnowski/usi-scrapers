import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from usi_scrapers.utils.io import lookup_developer_by_id, save_dev_raw_json
from usi_scrapers.scraper_otodom import scrape_otodom
from usi_scrapers.models import ScraperConfig

@pytest.fixture
def temp_public_dir(tmp_path):
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    return public_dir

def test_lookup_developer_by_id(temp_public_dir):
    # Setup mock USIdev structure
    dev_slug = "existing-dev"
    portal_id = "99"
    
    # Use save_dev_raw_json to create the structure correctly
    save_dev_raw_json(
        data={"name": "Existing Developer"},
        public_dir=temp_public_dir,
        dev_slug=dev_slug,
        portal_prefix="oto",
        portal_id=portal_id
    )
    
    # Test lookup
    found_slug = lookup_developer_by_id(temp_public_dir, "oto", portal_id)
    assert found_slug == dev_slug
    
    # Test non-existent
    assert lookup_developer_by_id(temp_public_dir, "oto", "88") is None

@patch("usi_scrapers.scraper_otodom.download_raw_otodom_dev_json")
def test_scrape_otodom_uses_existing_slug_from_id(mock_dl, temp_public_dir):
    # Setup existing developer with ID 99 mapped to slug "my-slug"
    save_dev_raw_json(
        data={"name": "My Developer"},
        public_dir=temp_public_dir,
        dev_slug="my-slug",
        portal_prefix="oto",
        portal_id="99"
    )
    
    # Mock HTML with a DIFFERENT slug in the URL (new-slug-ID99) but same ID (99)
    ad = {
        "id": 1,
        "title": "Inv",
        "agency": {"id": 99, "name": "TestDev", "url": "https://www.otodom.pl/pl/firmy/deweloperzy/new-slug-ID99"},
        "location": {"coordinates": {"latitude": 0, "longitude": 0}},
        "images": [],
    }
    payload = {"props": {"pageProps": {"ad": ad}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'
    
    config = ScraperConfig(public_dir=temp_public_dir)
    fetcher = MagicMock()
    fetcher.config = config
    fetcher.fetch.return_value = html
    
    # Run scraper
    result = scrape_otodom("https://www.otodom.pl/pl/oferta/test-ID123", fetcher)
    
    # Should use "my-slug" instead of "new-slug"
    assert result["developer_slug"] == "my-slug"
    mock_dl.assert_called_once()
    # Check that it called download with the correct slug
    args, _ = mock_dl.call_args
    assert args[1] == "my-slug"

@patch("usi_scrapers.scraper_rp.download_raw_rp_dev_json")
@patch("usi_scrapers.scraper_rp.fetch_rp_details")
def test_scrape_rp_uses_existing_slug_from_id(mock_details, mock_dl, temp_public_dir):
    # Setup existing developer with ID 123 mapped to slug "rp-slug"
    save_dev_raw_json(
        data={"name": "RP Dev"},
        public_dir=temp_public_dir,
        dev_slug="rp-slug",
        portal_prefix="rp",
        portal_id="123"
    )
    
    # Mock RP details with DIFFERENT slug but same ID
    mock_details.return_value = {
        "id": 1,
        "slug": "inv",
        "vendor": {"id": 123, "slug": "new-rp-slug"},
        "main_image": {"m_img_500": "http://img.com/1.jpg"}
    }
    
    config = ScraperConfig(public_dir=temp_public_dir)
    fetcher = MagicMock()
    fetcher.config = config
    fetcher.fetch_json.return_value = {} # Mock gallery
    
    # Run scraper
    from usi_scrapers.scraper_rp import scrape_rynek_pierwotny
    result = scrape_rynek_pierwotny("1", fetcher)
    
    # Should use "rp-slug"
    assert result["developer_slug"] == "rp-slug"
    mock_dl.assert_called_once()
    args, _ = mock_dl.call_args
    assert args[1] == "rp-slug"

@patch("usi_scrapers.scraper_to.download_raw_to_dev_json")
def test_scrape_to_uses_existing_slug_from_id(mock_dl, temp_public_dir):
    # Setup existing developer with ID "12345" mapped to slug "to-slug"
    save_dev_raw_json(
        data={"name": "TO Dev"},
        public_dir=temp_public_dir,
        dev_slug="to-slug",
        portal_prefix="to",
        portal_id="12345"
    )

    # Mock TO HTML with DIFFERENT slug but same portal-ID (in our case slug is ID)
    html = '<html><head><meta name="klient-id" content="12345"></head><body><a href="/katalog-firm/deweloperzy/other-slug">Dev</a></body></html>'    
    config = ScraperConfig(public_dir=temp_public_dir)
    fetcher = MagicMock()
    fetcher.config = config
    fetcher.fetch.return_value = html
    
    # Mock extract_to_data to not fail
    with patch("usi_scrapers.scraper_to.extract_to_data") as mock_extract:
        mock_extract.return_value = {"brand": {"name": "TO Dev"}}
        
        from usi_scrapers.scraper_to import scrape_tabelaofert
        result = scrape_tabelaofert("https://tabelaofert.pl/inwestycja/test,i1", fetcher)
        
        # Should use "to-slug"
        assert result["developer_slug"] == "to-slug"
        mock_dl.assert_called_once()
        args, _ = mock_dl.call_args
        assert args[1] == "to-slug"
