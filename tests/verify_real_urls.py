import sys
import json
import os
from pathlib import Path
from usi_scrapers.api import download_raw_dev, ingest_investment_by_url
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig

def main():
    print("Starting real URL verification...")
    scraper_api_key = os.getenv("SCRAPERAPI_API_KEY")
    config = ScraperConfig(
        public_dir=Path("./tmp_verify_public"),
        scraperapi_key=scraper_api_key
    )
    fetcher = Fetcher(config)
    
    # Test 1: RP Developer
    print("Downloading RP developer: 1084...")
    res_rp = download_raw_dev(config, fetcher, "rp", "1084")
    print(f"RP Result: {json.dumps(res_rp, indent=2)}")

    # Test 2: Otodom Investment (Fresh URL)
    print("Downloading Otodom investment (Develia)...")
    # Using an active listing from search results
    oto_url = "https://www.otodom.pl/pl/oferta/2-pokoje-z-balkonem-vilda-arte-ID4vVwq"
    res_oto = ingest_investment_by_url(config, fetcher, "oto", oto_url)
    if "error" in res_oto:
         print(f"Oto Error: {res_oto['error']}")
    else:
         print(f"Oto Success: {res_oto.get('investment_slug')}")
         # Inspect the saved file
         p_id = res_oto.get('id') or res_oto.get('oto_url_id')
         dev_slug = res_oto.get('developer_slug')
         inv_slug = res_oto.get('investment_slug')
         if dev_slug and inv_slug and p_id:
             path = Path("./tmp_verify_public") / "USIdata" / dev_slug / inv_slug / f"raw_oto_{p_id}.json"
             if path.exists():
                 with open(path, 'r') as f:
                     content = json.load(f)
                     print(f"Verified saved file keys: {list(content.keys())[:5]}")

    # Test 3: TO Developer
    print("Downloading TO developer...")
    res_to = download_raw_dev(config, fetcher, "to", "https://tabelaofert.pl/katalog-firm/deweloperzy/murapol")
    print(f"TO Result: {json.dumps(res_to, indent=2)}")
            
    print("Done.")

if __name__ == "__main__":
    main()
