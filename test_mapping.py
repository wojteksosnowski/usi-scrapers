import json
import logging
from pathlib import Path

from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.scraper_to import fetch_to_html, extract_to_dev_raw_json, parse_to_product
from usi_scrapers.utils.mapping import resolve_path, get_mapping

logging.basicConfig(level=logging.INFO)

def test_to_mapping():
    config = ScraperConfig(public_dir=Path("/tmp/pub"))
    fetcher = Fetcher(config)
    
    print("=== Testing TO Developer ===")
    dev_url = "https://tabelaofert.pl/katalog-firm/deweloperzy/atal"
    dev_html = fetch_to_html(dev_url, fetcher)
    dev_json = extract_to_dev_raw_json(dev_html) if dev_html else {}
    
    if not dev_json:
        print("Failed to extract dev json. Maybe cloudflare or no json found.")
    else:
        print(f"Extracted dev json keys: {list(dev_json.keys())}")
        dev_mapping = get_mapping("to", "developer")
        for key, path in dev_mapping.items():
            val = resolve_path(dev_json, path)
            print(f"  {key} ({path}) -> {val}")
            
    print("\n=== Testing TO Investment ===")
    # Find a real investment URL
    # Let's search from the developer's page
    inv_url = None
    import re
    if dev_html:
        m = re.search(r'href="(/inwestycja/[^"]+,i\d+)"', dev_html)
        if m:
            inv_url = "https://tabelaofert.pl" + m.group(1)
            
    if not inv_url:
        inv_url = "https://tabelaofert.pl/inwestycja/francuska-park,i4598" # fallback guess
        
    print(f"Fetching inv: {inv_url}")
    inv_html = fetch_to_html(inv_url, fetcher)
    inv_json = parse_to_product(inv_html) if inv_html else {}
    
    if not inv_json:
        print("Failed to extract inv json.")
    else:
        print(f"Extracted inv json keys: {list(inv_json.keys())}")
        inv_mapping = get_mapping("to", "investment")
        for key, path in inv_mapping.items():
            val = resolve_path(inv_json, path)
            print(f"  {key} ({path}) -> {val}")

if __name__ == "__main__":
    test_to_mapping()
