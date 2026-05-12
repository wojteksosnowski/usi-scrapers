import logging
import json
import re
from pathlib import Path
from typing import Optional
from usi_scrapers.scraper_to import scrape_tabelaofert
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher

# Setup logging
logging.basicConfig(level=logging.INFO)

class MockFetcher(Fetcher):
    def __init__(self, config, mock_responses):
        super().__init__(config)
        self.mock_responses = mock_responses

    def fetch(self, url: str, **kwargs) -> Optional[str]:
        return self.mock_responses.get(url)

    def fetch_json(self, url: str, **kwargs) -> Optional[dict]:
        res = self.mock_responses.get(url)
        if isinstance(res, str):
            return json.loads(res)
        return res

def patched_discover_to_listing(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None) -> list[dict]:
    if not identifier: return []
    url = identifier
    all_offers = []
    seen_ids = set()
    base_url = url
    current_page = 1
    
    while True:
        page_url = base_url
        if "page=" in page_url:
            page_url = re.sub(r'page=\d+', f'page={current_page}', page_url)
        else:
            connector = "&" if "?" in page_url else "?"
            page_url += f"{connector}page={current_page}"

        html = fetcher.fetch(page_url)
        if not html: break
        
        matches = list(re.finditer(r'href="(/inwestycja/([^",]+),i(\d+))"', html))
        if not matches: break

        for m in matches:
            full_path, slug_part, to_id = m.groups()
            if to_id in seen_ids: continue
            seen_ids.add(to_id)
            
            full_url = f"https://tabelaofert.pl{full_path}"
            name = slug_part.replace("-", " ").title()
            
            start_search = max(0, m.start() - 2000)
            end_search = min(len(html), m.end() + 1000)
            window = html[start_search:end_search]
            
            img_matches = list(re.finditer(r'src="(https?://content\.tabelaofert\.pl/[^"]+\.(?:webp|jpg|png|jpeg))"', window))
            
            # --- FIX START ---
            image_url = None
            if img_matches:
                # 1. Try to find a non-generic image
                for im in img_matches:
                    u = im.group(1)
                    if not any(p in u.lower() for p in ["logo-", "icon-", "avatar-", "spacer-", "mapa-"]):
                        image_url = u
                        break
                # 2. If all are generic, take the last one (original behavior)
                if not image_url:
                    image_url = img_matches[-1].group(1)
            # --- FIX END ---

            dev_name = None
            dev_match = re.search(r'data-developer="([^"]+)"', window)
            if not dev_match:
                dev_match = re.search(r'<span>([^<]+)</span>', window)
            
            if dev_match:
                dev_name = dev_match.group(1).strip()

            all_offers.append({
                "id": to_id, "url": full_url, "name": name, "slug": slug_part,
                "image": image_url, "developer": dev_name
            })
            if limit and len(all_offers) >= limit: return all_offers

        if 'class="next"' not in html and 'rel="next"' not in html: break
        current_page += 1
    return all_offers

LISTING_HTML = """
<html>
<body>
    <div class="investment-card">
        <img src="https://content.tabelaofert.pl/img/investment_main.jpg" alt="Main">
        <div class="info" data-developer="Great Developer S.A.">
            <span>Great Developer</span>
            <a href="/inwestycja/super-osiedle,i12345">Super Osiedle</a>
        </div>
        <img src="https://content.tabelaofert.pl/img/logo-developer.png" alt="Logo">
    </div>
</body>
</html>
"""

def run_mock_test():
    config = ScraperConfig(public_dir=Path("/tmp/usi-test"))
    mock_responses = {"https://tabelaofert.pl/search?page=1": LISTING_HTML}
    fetcher = MockFetcher(config, mock_responses)
    
    print("\n--- PATCHED DISCOVERY ---")
    discovered = patched_discover_to_listing(config, fetcher, identifier="https://tabelaofert.pl/search")
    for item in discovered:
        print(f"Discovered ID: {item['id']}")
        print(f"Discovered URL: {item['url']}")

if __name__ == "__main__":
    run_mock_test()
