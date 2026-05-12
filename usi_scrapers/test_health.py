import logging
from usi_scrapers.api import health_check

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("Running health check...")
    results = health_check(portals=["tabelaofert"])
    print("\n--- Health Check Results ---")
    print(f"Overall Status: {'OK' if results['ok'] else 'FAILED'}")
    
    for portal, details in results['portals'].items():
        print(f"\nPortal: {portal}")
        print(f"  Status: {'OK' if details['ok'] else 'FAILED'}")
        print(f"  Discovery Count: {details['discovery_count']}")
        print(f"  Scrape URL: {details['scrape_url']}")
        if details.get("error"):
            print(f"  Error: {details['error']}")
        if not details['ok']:
            print(f"  Missing Fields: {details.get('scrape_fields_missing', [])}")
            print(f"  OK Fields: {details.get('scrape_fields_ok', [])}")
