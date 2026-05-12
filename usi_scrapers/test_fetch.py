import os
import json
from pathlib import Path
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher

def run():
    config = ScraperConfig(public_dir=Path("/tmp/usi-test"))
    fetcher = Fetcher(config)
    
    # Fetch listing
    listing_url = "https://tabelaofert.pl/katalog-firm/deweloperzy/unidevelopment"
    print(f"Fetching {listing_url}...")
    listing_html = fetcher.fetch(listing_url)
    if listing_html:
        with open("/tmp/to_listing.html", "w", encoding="utf-8") as f:
            f.write(listing_html)
        print("Saved listing HTML to /tmp/to_listing.html")
        
        # Try to find an investment URL to fetch
        import re
        m = re.search(r'href="(/inwestycja/([^",]+),i(\d+))"', listing_html)
        if m:
            inv_url = f"https://tabelaofert.pl{m.group(1)}"
            print(f"Fetching {inv_url}...")
            inv_html = fetcher.fetch(inv_url)
            if inv_html:
                with open("/tmp/to_inv.html", "w", encoding="utf-8") as f:
                    f.write(inv_html)
                print("Saved investment HTML to /tmp/to_inv.html")

if __name__ == "__main__":
    run()
