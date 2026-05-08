import re
from urllib.parse import urlparse, parse_qs

def parse_url(url: str) -> dict:
    """
    Parses RynekPierwotny.pl or Otodom.pl URL to extract necessary identifiers.
    """
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path
    
    # RynekPierwotny Developer/Vendor
    if "rynekpierwotny.pl" in domain:
        # Match /oferty/dev-slug/inv-slug-id/
        match = re.search(r'/oferty/([^/]+)/([^/]+)-(\d+)/', path)
        if match:
            query = parse_qs(parsed.query)
            return {
                "type": "rynekpierwotny",
                "kind": "investment",
                "developer_slug": match.group(1),
                "investment_slug": match.group(2),
                "offer_id": match.group(3),
                "stage_id": query.get("stage", [None])[0],
                "url": url,
            }
        
        # Match /deweloperzy/slug/
        match = re.search(r'/deweloperzy/([^/]+)/', path)
        if match:
            return {
                "type": "rynekpierwotny",
                "kind": "developer",
                "developer_slug": match.group(1),
                "url": url
            }
        
    # 2. Otodom.pl
    if "otodom.pl" in domain:
        # Agency profile: /pl/firmy/deweloperzy/slug-ID{id}
        match = re.search(r'/firmy/deweloperzy/.*-ID(\d+)', path)
        if match:
            return {
                "type": "otodom",
                "kind": "developer",
                "agency_id": match.group(1),
                "url": url
            }

        # Individual offer/investment: /pl/inwestycja/[slug] or /pl/oferta/[slug]
        match = re.search(r'/(inwestycja|oferta)/([^/]+)', path)
        if match:
            return {
                "type": "otodom",
                "kind": "investment",
                "investment_slug": match.group(2),
                "url": url
            }

    # 3. Tabelaofert.pl
    if "tabelaofert.pl" in domain:
        # Developer profile: /katalog-firm/deweloperzy/[slug]
        match = re.search(r'/katalog-firm/deweloperzy/([^/]+)', path)
        if match:
            return {
                "type": "tabelaofert",
                "kind": "developer",
                "developer_slug": match.group(1),
                "url": url
            }

        # Investment: /inwestycja/{slug},i{id}
        match = re.search(r'/inwestycja/([^,]+),i(\d+)', path)
        if match:
            return {
                "type": "tabelaofert",
                "kind": "investment",
                "investment_slug": match.group(1),
                "to_id": match.group(2),
                "url": url,
            }

    return {"type": "unknown", "kind": "unknown", "url": url}
