import json
import logging
import sys
import shutil
from pathlib import Path
from usi_scrapers.models import ScraperConfig
from usi_scrapers.utils.images import clean_filename, save_images
from usi_scrapers.scraper_to import filter_investment_images

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
from . import get_logger

logger = get_logger(__name__)

def re_download_investment_images(public_dir: Path, dev_slug: str, inv_slug: str, portal: str, force_clean: bool = False):
    """
    Cleans up the image folder and re-downloads images based on the newest raw JSON.
    """
    usi_data_dir = public_dir / "USIdata" / dev_slug / inv_slug
    usi_root_dir = public_dir / "USI" / dev_slug / inv_slug
    
    print(f"\n--- Re-downloading Images for: {inv_slug} ({portal}) ---")
    
    # 1. Find raw JSON
    raw_files = list(usi_data_dir.glob(f"raw_{portal}_*.json"))
    if not raw_files:
        print(f"ERROR: No raw JSON found for {portal} in {usi_data_dir}")
        return
    
    raw_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    raw_path = raw_files[0]
    
    with open(raw_path, 'r') as f:
        raw_data = json.load(f)
        
    # 2. Extract expected URLs
    expected_urls = []
    if portal == "rp":
        gallery = raw_data.get("_raw_gallery", {}).get("gallery", [])
        expected_urls = [item.get("image", {}).get("g_img_1500") for item in gallery]
    elif portal in ("oto", "otodom"):
        ad_data = raw_data.get("ad") or raw_data.get("value", {}).get("ad", {})
        images_raw = ad_data.get("images", [])
        expected_urls = [img.get("large") for img in images_raw if img.get("large")]
    elif portal == "to":
        raw_gallery = raw_data.get("_raw_gallery_urls", [])
        expected_urls = filter_investment_images(raw_gallery, raw_data)
        
    expected_urls = [u for u in expected_urls if u]
    expected_fnames = {clean_filename(u) for u in expected_urls}
    
    # 3. Optional: Clean folder
    if force_clean and usi_root_dir.exists():
        print(f"Cleaning directory: {usi_root_dir}")
        for f in usi_root_dir.glob("*"):
            if f.is_file(): f.unlink()
    elif usi_root_dir.exists():
        # Remove extra files only
        actual_files = list(usi_root_dir.glob("*"))
        for f in actual_files:
            if f.is_file() and not f.name.startswith(".") and f.name not in expected_fnames:
                print(f"Removing extra file: {f.name}")
                f.unlink()

    # 4. Sync images
    config = ScraperConfig(public_dir=public_dir)
    print(f"Syncing {len(expected_urls)} images...")
    saved = save_images(expected_urls, dev_slug, inv_slug, config)
    print(f"Successfully synced {len(saved)} images.")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python re_download_images.py <public_dir> <dev_slug> <inv_slug> <portal> [--clean]")
        sys.exit(1)
        
    p_dir = Path(sys.argv[1])
    d_slug = sys.argv[2]
    i_slug = sys.argv[3]
    ptal = sys.argv[4]
    do_clean = "--clean" in sys.argv
    
    re_download_investment_images(p_dir, d_slug, i_slug, ptal, force_clean=do_clean)
