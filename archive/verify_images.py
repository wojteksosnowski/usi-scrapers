import json
import logging
import sys
from pathlib import Path
from usi_scrapers.utils.images import clean_filename
from usi_scrapers.scraper_to import filter_investment_images

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
from . import get_logger

logger = get_logger(__name__)

def verify_investment_images(public_dir: Path, dev_slug: str, inv_slug: str, portal: str):
    """
    Checks if images in USI/{dev}/{inv} match the URLs in raw_{portal}_*.json
    """
    usi_data_dir = public_dir / "USIdata" / dev_slug / inv_slug
    usi_root_dir = public_dir / "USI" / dev_slug / inv_slug
    
    print(f"\n--- Verifying Images for: {inv_slug} ({portal}) ---")
    
    # 1. Find raw JSON
    raw_files = list(usi_data_dir.glob(f"raw_{portal}_*.json"))
    if not raw_files:
        print(f"ERROR: No raw JSON found for {portal} in {usi_data_dir}")
        return
    
    # Sort by modification time to get the newest
    raw_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    raw_path = raw_files[0]
    print(f"Using raw data: {raw_path.name}")
    
    with open(raw_path, 'r') as f:
        raw_data = json.load(f)
        
    # 2. Extract expected URLs
    expected_urls = []
    if portal == "rp":
        gallery = raw_data.get("_raw_gallery", {}).get("gallery", [])
        expected_urls = [item.get("image", {}).get("g_img_1500") for item in gallery]
    elif portal in ("oto", "otodom"):
        # Otodom sometimes has 'ad' or 'value.ad'
        ad_data = raw_data.get("ad") or raw_data.get("value", {}).get("ad", {})
        images_raw = ad_data.get("images", [])
        expected_urls = [img.get("large") for img in images_raw if img.get("large")]
    elif portal == "to":
        raw_gallery = raw_data.get("_raw_gallery_urls", [])
        expected_urls = filter_investment_images(raw_gallery, raw_data)
        
    expected_fnames = {clean_filename(u) for u in expected_urls if u}
    print(f"Expected images from JSON: {len(expected_fnames)}")
    
    # 3. List actual files
    if not usi_root_dir.exists():
        print(f"ERROR: Image directory does not exist: {usi_root_dir}")
        return
        
    actual_files = {f.name for f in usi_root_dir.glob("*") if f.is_file() and not f.name.startswith(".")}
    print(f"Actual images on disk: {len(actual_files)}")
    
    # 4. Compare
    missing = expected_fnames - actual_files
    extra = actual_files - expected_fnames
    
    if not missing and not extra:
        print("SUCCESS: Image set is perfectly consistent.")
    else:
        if missing:
            print(f"MISSING on disk ({len(missing)}):")
            for m in sorted(missing): print(f"  - {m}")
        if extra:
            print(f"EXTRA on disk ({len(extra)}):")
            for e in sorted(extra): print(f"  - {e}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python verify_images.py <public_dir> <dev_slug> <inv_slug> <portal>")
        print("Example: python verify_images.py ../Public imperial-capital la-vie-house to")
        sys.exit(1)
        
    p_dir = Path(sys.argv[1])
    d_slug = sys.argv[2]
    i_slug = sys.argv[3]
    ptal = sys.argv[4]
    
    verify_investment_images(p_dir, d_slug, i_slug, ptal)
