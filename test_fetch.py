import os
from pathlib import Path
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig

def run():
    config = ScraperConfig(public_dir=Path("/tmp/pub"))
    fetcher = Fetcher(config)
    url = "https://tabelaofert.pl/katalog-firm/deweloperzy/atal"
    html = fetcher.fetch(url)
    with open("/Volumes/Samsam/claude-py/usi-scrapers/dev_page.html", "w") as f:
        f.write(html or "")

if __name__ == "__main__":
    run()
