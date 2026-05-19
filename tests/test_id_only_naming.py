import pytest
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
from usi_scrapers.utils.io import save_raw_json, save_dev_raw_json, save_meta_json
from usi_scrapers.scraper_rp import download_raw_rp_dev_json
from usi_scrapers.models import ScraperConfig

def test_archiving_uses_portal_id(tmp_path):
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    
    dev_slug = "dev-slug"
    inv_slug = "inv-slug"
    portal_id = "12345"
    
    # 1. Test save_raw_json archiving
    # Save once
    save_raw_json(
        data={"v": 1},
        public_dir=public_dir,
        dev_slug=dev_slug,
        inv_slug=inv_slug,
        portal_prefix="rp",
        portal_id=portal_id
    )
    # Save again (should trigger archiving)
    save_raw_json(
        data={"v": 2},
        public_dir=public_dir,
        dev_slug=dev_slug,
        inv_slug=inv_slug,
        portal_prefix="rp",
        portal_id=portal_id
    )
    
    inv_dir = public_dir / "USIdata" / dev_slug / inv_slug
    # Check that archive exists with portal_id in its name
    archives = list(inv_dir.glob("raw_rp_12345_*.json"))
    assert len(archives) == 1
    
    # 2. Test save_dev_raw_json archiving
    save_dev_raw_json(
        data={"v": 1},
        public_dir=public_dir,
        dev_slug=dev_slug,
        portal_prefix="rp",
        portal_id=portal_id
    )
    save_dev_raw_json(
        data={"v": 2},
        public_dir=public_dir,
        dev_slug=dev_slug,
        portal_prefix="rp",
        portal_id=portal_id
    )
    dev_dir = public_dir / "USIdev" / dev_slug
    dev_archives = list(dev_dir.glob("raw_rp_12345_*.json"))
    assert len(dev_archives) == 1

    # 3. Test save_meta_json archiving
    save_meta_json(
        data={"v": 1},
        public_dir=public_dir,
        dev_slug=dev_slug,
        inv_slug=inv_slug,
        portal_prefix="rp",
        portal_id=portal_id
    )
    save_meta_json(
        data={"v": 2},
        public_dir=public_dir,
        dev_slug=dev_slug,
        inv_slug=inv_slug,
        portal_prefix="rp",
        portal_id=portal_id
    )
    meta_archives = list(inv_dir.glob("meta_rp_12345_*.json"))
    assert len(meta_archives) == 1

@patch("usi_scrapers.scraper_rp.fetch_rp_developer_profile")
@patch("usi_scrapers.utils.images.download_developer_logo")
def test_download_raw_rp_dev_json_resolves_portal_id(mock_logo, mock_fetch, tmp_path):
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    
    config = ScraperConfig(public_dir=public_dir)
    fetcher = MagicMock()
    
    # Mock profile response from RP API containing ID 9876
    mock_fetch.return_value = {
        "id": 9876,
        "slug": "some-dev-slug",
        "name": "Some Developer",
        "logo": "http://logo.com/logo.png"
    }
    
    download_raw_rp_dev_json(
        vendor_id_or_slug="some-dev-slug",
        dev_slug="dev-slug-folder",
        fetcher=fetcher,
        config=config
    )
    
    # 1. Verify download_developer_logo was called with portal_id="9876"
    mock_logo.assert_called_once_with(
        "http://logo.com/logo.png",
        "dev-slug-folder",
        config,
        portal_prefix="rp",
        portal_id="9876"
    )
    
    # 2. Verify that the raw JSON file was saved using "raw_rp_9876.json"
    dev_dir = public_dir / "USIdev" / "dev-slug-folder"
    saved_file = dev_dir / "raw_rp_9876.json"
    assert saved_file.exists()
    
    # Verify content has meta with portal_id
    with open(saved_file, "r") as f:
        content = json.load(f)
    assert content["_usi_meta"]["portal_id"] == "9876"
