"""
Public API dla usi-scrapers.
Zbiór metod służących do interakcji z pakietem.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from .fetcher import Fetcher
from .models import ScraperConfig, ProgressCallback
from .manager import TechnicalDataManager
from .scraper_rp import discover_rp_investments, scrape_rynek_pierwotny, download_raw_rp_json, download_raw_rp_dev_json
from .scraper_otodom import discover_otodom_investments, discover_otodom_listing, scrape_otodom, download_raw_otodom_json, download_raw_otodom_dev_json, fetch_otodom_agency_name
from .scraper_to import discover_to_investments, discover_to_listing, scrape_tabelaofert, download_raw_to_json, download_raw_to_dev_json, fetch_to_agency_name
from .utils.io import save_raw_json, save_dev_raw_json

# DEVELIA agency ID on Otodom — large developer, stable probe target
_OTO_PROBE_AGENCY_ID = "10556359"
_TO_PROBE_URL = "https://tabelaofert.pl/katalog-firm/deweloperzy/unidevelopment"

_REQUIRED_FIELDS: Dict[str, list] = {
    "rp":          ["name", "latitude", "longitude", "image_urls"],
    "otodom":      ["title", "latitude", "longitude", "image_urls"],
    "tabelaofert": ["name", "latitude", "longitude", "image_urls"],
}


def _check_fields(data: Dict[str, Any], portal: str) -> tuple[list[str], list[str]]:
    ok, missing = [], []
    for f in _REQUIRED_FIELDS.get(portal, _REQUIRED_FIELDS["rp"]):
        val = data.get(f)
        if val is None or val == [] or val == "":
            missing.append(f)
        else:
            ok.append(f)
    return ok, missing


def health_check(
    config: ScraperConfig,
    fetcher: Fetcher,
    portals: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Smoke-test: sprawdza discovery i scrape dla każdego portalu.
    Zwraca słownik z wynikami per portal i globalnym 'ok'.

    Domyślnie testuje wszystkie trzy portale. Można ograniczyć listą:
    portals=["rp"], portals=["otodom", "tabelaofert"] itp.

    Każdy wpis w 'portals' zawiera:
      ok                  – bool: discovery dał ≥1 wynik i scrape zwrócił wymagane pola
      discovery_count     – int | None
      scrape_url          – str | None: URL który był scrapowany
      scrape_fields_ok    – list[str]
      scrape_fields_missing – list[str]
      error               – str | None: pierwszy napotkany błąd
    """
    if portals is None:
        portals = ["rp", "otodom", "tabelaofert"]

    results: Dict[str, Any] = {}

    for portal in portals:
        p = portal.lower()
        entry: Dict[str, Any] = {
            "ok": False,
            "discovery_count": None,
            "scrape_url": None,
            "scrape_fields_ok": [],
            "scrape_fields_missing": [],
            "error": None,
        }

        try:
            if p == "rp":
                items = discover_rp_investments(fetcher, config, None, limit=1)
            elif p in ("oto", "otodom"):
                items = discover_otodom_investments(_OTO_PROBE_AGENCY_ID, fetcher, limit=1)
            elif p in ("to", "tabelaofert"):
                items = discover_to_listing(_TO_PROBE_URL, fetcher, limit=1)
            else:
                raise ValueError(f"Nieznany portal: {portal}")

            entry["discovery_count"] = len(items)

            if not items:
                entry["error"] = "discovery zwróciło 0 wyników"
                results[portal] = entry
                continue

            inv = items[0]
            url = inv["url"]
            slug = inv.get("slug", "unknown")
            entry["scrape_url"] = url

            if p == "rp":
                data = scrape_rynek_pierwotny(inv["id"], "unknown", slug, fetcher)
            elif p in ("oto", "otodom"):
                data = scrape_otodom(url, "unknown", slug, fetcher)
            else:
                data = scrape_tabelaofert(url, "unknown", slug, fetcher)

            if data.get("error"):
                entry["error"] = f"scrape: {data['error']}"
                results[portal] = entry
                continue

            ok_fields, missing_fields = _check_fields(data, p if p != "oto" else "otodom")
            entry["scrape_fields_ok"] = ok_fields
            entry["scrape_fields_missing"] = missing_fields
            entry["ok"] = len(missing_fields) == 0

        except Exception as exc:
            entry["error"] = str(exc)

        results[portal] = entry

    return {
        "ok": all(r["ok"] for r in results.values()),
        "portals": results,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

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
