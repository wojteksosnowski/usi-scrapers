import json
from pathlib import Path
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.scraper_to import fetch_to_html, parse_to_product

def run():
    config = ScraperConfig(public_dir=Path("/tmp/pub"))
    fetcher = Fetcher(config)
    url = "https://tabelaofert.pl/inwestycja/nowe-miasto-polesie-iv-pienista-lodz-polesie-mieszkania-na-sprzedaz,i8978722"
    html = fetch_to_html(url, fetcher)
    inv_json = parse_to_product(html)
    with open("/Volumes/Samsam/claude-py/usi-scrapers/inv_test.json", "w") as f:
        json.dump(inv_json, f, indent=2, ensure_ascii=False)
        
if __name__ == "__main__":
    run()
