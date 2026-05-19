import pytest
import json
from pathlib import Path
from usi_scrapers.utils.images import clean_filename
from usi_scrapers.scraper_rp import fetch_rp_gallery
from usi_scrapers.scraper_otodom import extract_next_data
from usi_scrapers.scraper_to import extract_to_data, filter_investment_images

# ─── clean_filename ─────────────────────────────────────────────────────────

def test_clean_filename_otodom_cdn():
    url = "https://ireland.apollo.olxcdn.com/v1/files/eyJpZCI6ImY1c2JyeTk0czUzei1BUEwifQ/image;s=1280x1024"
    assert clean_filename(url) == "eyJpZCI6ImY1c2JyeTk0czUzei1BUEwifQ.jpg"

def test_clean_filename_tabelaofert():
    url = "https://tabelaofert.pl/oferty/zdjecia/quality_70,scale_425x283,ID-32981-01_Budynek.jpg"
    assert clean_filename(url) == "32981-01_Budynek.jpg"

def test_clean_filename_standard():
    url = "https://example.com/images/building_123.png?v=123#hash"
    assert clean_filename(url) == "building_123.png"

def test_clean_filename_cachebuster():
    url = "https://example.com/assets/photo_e94b5737.webp"
    assert clean_filename(url) == "photo.webp"

def test_clean_filename_no_extension():
    # Fallback to .jpg
    url = "https://tabelaofert.pl/ID-123456"
    assert clean_filename(url) == "123456.jpg"

# ─── consistency checks ─────────────────────────────────────────────────────

def test_rp_image_consistency(tmp_path):
    # Mock RP raw data
    raw_data = {
        "name": "Test RP",
        "_raw_gallery": {
            "gallery": [
                {"image": {"g_img_1500": "https://example.com/rp1.jpg"}},
                {"image": {"g_img_1500": "https://example.com/rp2.jpg"}}
            ]
        }
    }
    
    # Extract URLs
    gallery = raw_data.get("_raw_gallery", {}).get("gallery", [])
    urls = [item.get("image", {}).get("g_img_1500") for item in gallery]
    
    # Expected filenames
    expected_fnames = {clean_filename(u) for u in urls}
    assert "rp1.jpg" in expected_fnames
    assert "rp2.jpg" in expected_fnames

def test_otodom_image_consistency():
    # Mock Otodom page props
    raw_data = {
        "ad": {
            "images": [
                {"large": "https://example.com/oto1.jpg"},
                {"large": "https://example.com/oto2.jpg"}
            ]
        }
    }
    
    images_raw = raw_data.get("ad", {}).get("images", [])
    urls = [img.get("large") for img in images_raw if img.get("large")]
    
    expected_fnames = {clean_filename(u) for u in urls}
    assert "oto1.jpg" in expected_fnames
    assert "oto2.jpg" in expected_fnames

def test_to_image_consistency():
    # Mock TabelaOfert data
    # In TO, extract_to_data finds URLs in HTML, but here we mock the result of extract_to_data
    product_data = {
        "name": "Test TO",
        "image": "https://content.tabelaofert.pl/test-to-1.webp",
        "_raw_gallery_urls": [
            "https://content.tabelaofert.pl/test-to-1.webp",
            "https://content.tabelaofert.pl/test-to-2.webp",
            "https://content.tabelaofert.pl/mapa-123.webp"
        ]
    }
    
    # Filter images
    filtered_urls = filter_investment_images(product_data["_raw_gallery_urls"], product_data)
    
    expected_fnames = {clean_filename(u) for u in filtered_urls}
    
    # Should contain the investment images
    assert "test-to-1.webp" in expected_fnames
    assert "test-to-2.webp" in expected_fnames
    # Should NOT contain the map
    assert "mapa-123.webp" not in expected_fnames


def validate_investment_images(public_dir: Path, dev_slug: str, inv_slug: str, portal_prefix: str):
    """
    Utility function to validate if images in folder match those in raw JSON.
    Can be used in integration tests.
    """
    usi_data_dir = public_dir / "USIdata" / dev_slug / inv_slug
    usi_root_dir = public_dir / "USI" / dev_slug / inv_slug
    
    # 1. Find raw JSON
    raw_files = list(usi_data_dir.glob(f"raw_{portal_prefix}_*.json"))
    if not raw_files:
        pytest.fail(f"No raw JSON found for {portal_prefix} in {usi_data_dir}")
    
    with open(raw_files[0], 'r') as f:
        raw_data = json.load(f)
        
    # 2. Extract expected URLs based on portal
    expected_urls = []
    if portal_prefix == "rp":
        gallery = raw_data.get("_raw_gallery", {}).get("gallery", [])
        expected_urls = [item.get("image", {}).get("g_img_1500") for item in gallery]
    elif portal_prefix == "oto":
        ad_data = raw_data.get("ad", {})
        images_raw = ad_data.get("images", [])
        expected_urls = [img.get("large") for img in images_raw if img.get("large")]
    elif portal_prefix == "to":
        # For TO we use the filtered list if it was saved in raw_details, 
        # or we re-run filtering on _raw_gallery_urls
        raw_gallery = raw_data.get("_raw_gallery_urls", [])
        expected_urls = filter_investment_images(raw_gallery, raw_data)
        
    expected_fnames = {clean_filename(u) for u in expected_urls if u}
    
    # 3. List actual files
    actual_files = {f.name for f in usi_root_dir.glob("*") if f.is_file() and not f.name.startswith(".")}
    
    # 4. Compare
    missing = expected_fnames - actual_files
    extra = actual_files - expected_fnames
    
    assert not missing, f"Images missing on disk: {missing}"
    # Note: we might have extra images if multiple portals are merged, 
    # but for a single portal check it should be clean.
    return True
