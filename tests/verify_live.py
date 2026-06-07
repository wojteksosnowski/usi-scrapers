import os
import json
import logging
from pathlib import Path
from usi_scrapers.api import list_investments, process_batch_ingest
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher

def main():
    print("Starting LIVE URL verification...")
    # Load API key
    api_key = os.getenv("SCRAPERAPI_API_KEY")
    if not api_key:
        print("ERROR: SCRAPERAPI_API_KEY not found.")
        return

    # Initialize Config
    public_dir = Path("./tmp_live_public")
    if not public_dir.exists():
        public_dir.mkdir()

    config = ScraperConfig(
        public_dir=public_dir,
        scraperapi_key=api_key,
        otodom_discovery_urls=["https://www.otodom.pl/pl/wyniki/sprzedaz/inwestycja/cala-polska"],
        to_discovery_urls=["https://tabelaofert.pl/nowe-mieszkania"]
    )
    fetcher = Fetcher(config)

    # Resolve prefix to handle 'otodom' as 'oto' etc internally if needed, 
    # but api functions usually handle full names too.
    portals = ["rp", "otodom", "tabelaofert"]
    
    for portal in portals:
        print(f"\n--- Testing Portal: {portal} ---")
        try:
            # 1. Discover fresh URL
            print(f"Discovering fresh {portal} URL...")
            items = list_investments(config, fetcher, portal, identifier=None)
            if not items:
                print(f"FAILED: No investments found for {portal}")
                continue
            
            fresh_url = items[0]["url"]
            print(f"Found fresh URL: {fresh_url}")

            # 2. Ingest via batch process (simulating real pipeline)
            # ingest_mode=True is default for process_batch_ingest conceptually, 
            # and it should trigger developer download.
            print(f"Ingesting via process_batch_ingest...")
            results = process_batch_ingest(config, fetcher, portal, [fresh_url])
            
            # Clean up results for print (remove potentially huge data)
            display_results = []
            for r in results:
                if r:
                    display_results.append({k: v for k, v in r.items() if k != 'raw_data'})
            print(f"Batch Result: {json.dumps(display_results, indent=2)}")

            # 3. Verify Otodom JSON structure
            if portal == "otodom" or portal == "oto":
                # Find the saved raw file
                raw_files = list(public_dir.rglob("raw_oto_*.json"))
                if not raw_files:
                    print("FAILED: No raw Otodom file found on disk.")
                    continue
                
                latest_file = max(raw_files, key=os.path.getmtime)
                print(f"Verifying structure of: {latest_file}")
                with open(latest_file, "r") as f:
                    data = json.load(f)
                    if "props" in data and "pageProps" in data["props"]:
                        print(f"SUCCESS: {latest_file.name} contains full __NEXT_DATA__ structure.")
                    else:
                        print(f"FAILED: {latest_file.name} does NOT contain full structure. Keys: {list(data.keys())}")

        except Exception as e:
            print(f"ERROR during {portal} test: {e}")
            import traceback
            traceback.print_exc()

    print("\nLive verification finished.")

if __name__ == "__main__":
    main()
