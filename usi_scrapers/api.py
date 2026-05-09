"""
Public API dla usi-scrapers.
Zbiór metod służących do interakcji z pakietem.
"""
from typing import Any, Dict, List, Optional
from pathlib import Path

from .fetcher import Fetcher
from .models import ScraperConfig, ProgressCallback
from .manager import TechnicalDataManager
from .scraper_rp import discover_rp_investments, scrape_rynek_pierwotny, download_raw_rp_json, download_raw_rp_dev_json
from .scraper_otodom import discover_otodom_investments, discover_otodom_listing, scrape_otodom, download_raw_otodom_json, download_raw_otodom_dev_json, fetch_otodom_agency_name
from .scraper_to import discover_to_investments, discover_to_listing, scrape_tabelaofert, download_raw_to_json, download_raw_to_dev_json, fetch_to_agency_name
from .utils.io import save_raw_json, save_dev_raw_json

def list_investments(
    config: ScraperConfig,
    fetcher: Fetcher,
    portal: str,
    identifier: Optional[str] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> List[Dict[str, Any]]:
    """Pobiera listę inwestycji dewelopera ze wskazanego portalu (Discovery)."""
    p = portal.lower()
    if p == "rp":
        return discover_rp_investments(fetcher, config, identifier)
    elif p in ("oto", "otodom"):
        if identifier and not identifier.startswith("http"):
            return discover_otodom_investments(identifier, fetcher)
        elif identifier:
            return discover_otodom_listing(identifier, fetcher)

        # Global discovery for Otodom
        all_results = []
        seen_ids = set()
        urls = config.otodom_discovery_urls
        total = len(urls)
        for i, url in enumerate(urls):
            batch = discover_otodom_listing(url, fetcher)
            for item in batch:
                if item["id"] not in seen_ids:
                    all_results.append(item)
                    seen_ids.add(item["id"])
            if on_progress:
                on_progress(i + 1, total)
        return all_results

    elif p in ("to", "tabelaofert"):
        return discover_to_investments(identifier, fetcher, config)
    else:
        raise ValueError(f"Unsupported portal for discovery: {portal}")


def fetch_many(
    config: ScraperConfig,
    fetcher: Fetcher,
    portal: str,
    investments: List[Dict[str, Any]],
    on_progress: Optional[ProgressCallback] = None,
) -> List[Dict[str, Any]]:
    """
    Pobiera szczegóły listy inwestycji, wołając on_progress(current, total) po każdej.

    Każdy element investments musi zawierać klucze: "identifier", "dev_slug", "inv_slug".
    Zwraca listę wyników w tej samej kolejności co investments.
    """
    total = len(investments)
    results = []
    for i, inv in enumerate(investments):
        result = fetch_investment(config, fetcher, portal, inv["identifier"], inv["dev_slug"], inv["inv_slug"])
        results.append(result)
        if on_progress:
            on_progress(i + 1, total)
    return results

def fetch_investment(config: ScraperConfig, fetcher: Fetcher, portal: str, identifier: str, dev_slug: str, inv_slug: str) -> Dict[str, Any]:
    """Pobiera szczegóły konkretnej inwestycji ze wskazanego portalu (Scrape)."""
    p = portal.lower()
    if p == "rp":
        return scrape_rynek_pierwotny(identifier, dev_slug, inv_slug, fetcher)
    elif p in ("oto", "otodom"):
        return scrape_otodom(identifier, dev_slug, inv_slug, fetcher)
    elif p in ("to", "tabelaofert"):
        return scrape_tabelaofert(identifier, dev_slug, inv_slug, fetcher)
    else:
        raise ValueError(f"Unsupported portal for fetching: {portal}")

def download_raw(config: ScraperConfig, fetcher: Fetcher, portal: str, identifier: str, dev_slug: str, inv_slug: str) -> Optional[Path]:
    """Pobiera i zapisuje surowy JSON inwestycji."""
    p = portal.lower()
    if p == "rp":
        return download_raw_rp_json(identifier, dev_slug, inv_slug, fetcher, config)
    elif p in ("oto", "otodom"):
        return download_raw_otodom_json(identifier, dev_slug, inv_slug, fetcher, config)
    elif p in ("to", "tabelaofert"):
        return download_raw_to_json(identifier, dev_slug, inv_slug, fetcher, config)
    return None

def download_raw_dev(config: ScraperConfig, fetcher: Fetcher, portal: str, identifier: str, dev_slug: str) -> Optional[Path]:
    """Pobiera i zapisuje surowy JSON profilu dewelopera."""
    p = portal.lower()
    if p == "rp":
        return download_raw_rp_dev_json(identifier, dev_slug, fetcher, config)
    elif p in ("oto", "otodom"):
        return download_raw_otodom_dev_json(identifier, dev_slug, fetcher, config)
    elif p in ("to", "tabelaofert"):
        return download_raw_to_dev_json(identifier, dev_slug, fetcher, config)
    return None

def save_raw(config: ScraperConfig, data: Dict[str, Any], dev_slug: str, inv_slug: str, portal_prefix: str) -> Path:
    """Zapisuje gotowy słownik jako surowy JSON inwestycji."""
    return save_raw_json(data, config.public_dir, dev_slug, inv_slug, portal_prefix)

def save_raw_developer(config: ScraperConfig, data: Dict[str, Any], dev_slug: str, portal_prefix: str) -> Path:
    """Zapisuje gotowy słownik jako surowy JSON dewelopera."""
    return save_dev_raw_json(data, config.public_dir, dev_slug, portal_prefix)

def identify_developer(fetcher: Fetcher, portal: str, url: str) -> Optional[str]:
    """Próbuje zidentyfikować nazwę dewelopera na podstawie URL oferty."""
    p = portal.lower()
    if p in ("oto", "otodom"):
        return fetch_otodom_agency_name(url, fetcher)
    elif p in ("to", "tabelaofert"):
        return fetch_to_agency_name(url, fetcher)
    return None
