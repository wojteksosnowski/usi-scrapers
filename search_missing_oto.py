"""
Search Otodom for missing OTO developers from missing_developers.csv.
Queries both /firmy/deweloperzy/ and /firmy/biura-nieruchomosci/ for each name.
Extracts links from company-item-title elements.
Saves results to reference/usimaster/oto_search_results.csv
"""
import csv
import re
import time
import urllib.parse
from pathlib import Path

from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig

REPO_ROOT = Path(__file__).parent
MISSING_CSV = REPO_ROOT / "reference" / "usimaster" / "missing_developers.csv"
OUTPUT_CSV  = REPO_ROOT / "reference" / "usimaster" / "oto_search_results.csv"

SEARCH_BASES = [
    "https://www.otodom.pl/firmy/deweloperzy/",
    "https://www.otodom.pl/firmy/biura-nieruchomosci/",
]

_LINK_PATTERN = re.compile(
    r'class="company-item-title"[^>]*>.*?href="(https?://[^"]+)"',
    re.DOTALL,
)


def search_name(fetcher: Fetcher, name: str) -> list[dict]:
    results = []
    q = urllib.parse.quote_plus(name)
    for base in SEARCH_BASES:
        url = f"{base}?sq={q}"
        try:
            html = fetcher.fetch(url) or ""
            links = _LINK_PATTERN.findall(html)
            for link in links:
                results.append({"search_url": url, "name": name, "link": link})
            time.sleep(1.5)
        except Exception as e:
            print(f"  ERROR {url}: {e}")
    return results


def main() -> None:
    config = ScraperConfig(public_dir=str(REPO_ROOT / "Public"))
    fetcher = Fetcher(config)

    rows: list[dict] = []
    with open(MISSING_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["portal"] != "oto":
                continue
            name = row["name"].strip()
            known_id = row["id"].strip()
            print(f"Searching: {name} (known id={known_id})")
            hits = search_name(fetcher, name)
            if hits:
                for h in hits:
                    h["known_id"] = known_id
                    h["known_slug"] = row["slug"].strip()
                rows.extend(hits)
                print(f"  → {len(hits)} result(s)")
            else:
                rows.append({
                    "search_url": "", "name": name, "link": "",
                    "known_id": known_id, "known_slug": row["slug"].strip(),
                })
                print(f"  → no results")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["name", "known_id", "known_slug", "search_url", "link"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
