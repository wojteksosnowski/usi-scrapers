import sys
import json
from pathlib import Path
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig
from usi_scrapers.scraper_to import extract_to_data

config = ScraperConfig(public_dir=Path("./temp"))
fetcher = Fetcher(config)

url = "https://tabelaofert.pl/nowe-mieszkania/warszawa/bemowo/osiedle-lazurowa-koncepcja,i834460"
html = fetcher.fetch(url)

if not html:
    print("Fetch failed")
    sys.exit(1)

data = extract_to_data(html, url, fetcher)
print(f"Extracted data keys: {list(data.keys()) if data else 'Empty'}")
if 'to_id' in data:
    print(f"TO ID: {data['to_id']}")
else:
    print("No TO ID")

