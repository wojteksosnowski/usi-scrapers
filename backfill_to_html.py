import os
import json
import logging
from pathlib import Path
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig
from usi_scrapers.scraper_to import clean_to_html, fetch_to_html
from usi_scrapers.utils.io import save_raw_html

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    config = ScraperConfig(public_dir=Path("./public")) # Assuming public_dir is ./public
    fetcher = Fetcher(config)
    
    # Path where JSON files are stored
    usi_dir = config.public_dir / "USI"
    
    if not usi_dir.exists():
        logger.error(f"Directory {usi_dir} does not exist.")
        return
        
    for dev_dir in usi_dir.iterdir():
        if not dev_dir.is_dir():
            continue
            
        dev_slug = dev_dir.name
        
        for inv_dir in dev_dir.iterdir():
            if not inv_dir.is_dir():
                continue
                
            inv_slug = inv_dir.name
            
            # Find the raw TO JSON file
            for file_path in inv_dir.glob("raw_to_*.json"):
                portal_id = file_path.stem.replace("raw_to_", "")
                html_path = inv_dir / f"raw_to_{portal_id}.html"
                
                if html_path.exists():
                    logger.info(f"Skipping {dev_slug}/{inv_slug}, HTML already exists.")
                    continue
                    
                logger.info(f"Processing {dev_slug}/{inv_slug} ({portal_id})...")
                
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in {file_path}")
                        continue
                
                # Extract URL
                url = data.get("url")
                if not url:
                    # check _usi_meta
                    meta = data.get("_usi_meta", {})
                    url = meta.get("source_url")
                    
                if not url:
                    logger.warning(f"No URL found in {file_path}, skipping.")
                    continue
                    
                html = fetch_to_html(url, fetcher)
                if not html:
                    logger.error(f"Failed to fetch HTML for {url}")
                    continue
                    
                cleaned_html = clean_to_html(html)
                
                # Save HTML file
                save_raw_html(cleaned_html, config.public_dir, dev_slug, inv_slug, "to", portal_id=portal_id)
                
                # Update JSON with _raw_html
                data["_raw_html"] = cleaned_html
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Updated {file_path} with _raw_html")

if __name__ == "__main__":
    main()
