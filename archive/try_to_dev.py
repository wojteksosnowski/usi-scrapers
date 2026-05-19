#!/usr/bin/env python3
"""Live test: discover + scrape investments from a TabelaOfert developer page."""
import json
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.scraper_to import discover_to_investments, scrape_tabelaofert

config = ScraperConfig(public_dir="/tmp/usi-test")
fetcher = Fetcher(config)

results = discover_to_investments("unidevelopment", fetcher, config)
print(f"\nFound {len(results)} investments:")
for inv in results:
    print(f"  [{inv['id']}] {inv['url']}")

# Full scrape of the example investment from the user's message
test_inv = next((r for r in results if r["id"] == "8982461"), results[0])
print(f"\n--- Scraping: {test_inv['url']} ---")
data = scrape_tabelaofert(test_inv["url"], "unidevelopment", test_inv["slug"], fetcher)

keys = ["name", "developer_name", "address", "city", "region",
        "latitude", "longitude", "price_min", "price_max",
        "properties_count", "construction_date_upper"]
for k in keys:
    print(f"  {k}: {data.get(k)}")
print(f"  amenities ({len(data.get('amenities', []))}): {data.get('amenities', [])[:3]}")
print(f"  image_urls ({len(data.get('image_urls', []))}): {data.get('image_urls', [])[:2]}")
print(f"  error: {data.get('error')}")
