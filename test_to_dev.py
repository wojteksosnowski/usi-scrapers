import sys
import re
from pathlib import Path
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig

config = ScraperConfig(public_dir=Path("./temp"))
fetcher = Fetcher(config)

url = "https://tabelaofert.pl/katalog-firm/deweloperzy/murapol"
html = fetcher.fetch(url)

m = re.search(r'\\?"klient\\?"\s*:\s*(\{.*?\})[,\]\}]', html)
if m:
    print(f"Match raw: {m.group(1)}")
else:
    print("No match")

