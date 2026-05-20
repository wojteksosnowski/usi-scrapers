"""
Public API dla usi-scrapers.
Zbiór metod służących do interakcji z pakietem.
"""
import time
import random
from datetime import datetime, timezone
import warnings
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

from .fetcher import Fetcher
from .models import ScraperConfig, ProgressCallback, DeveloperPage
from .manager import TechnicalDataManager
from .utils.io import save_raw_json, save_dev_raw_json
from .utils.portals import resolve_prefix, get_portal

# Scraper imports
from .scraper_rp import (
    discover_rp_investments, 
    scrape_rynek_pierwotny, 
    download_raw_rp_json, 
    download_raw_rp_dev_json, 
    discover_rp_developers,
    discover_rp_listing
)
from .scraper_otodom import (
    discover_otodom_investments, 
    discover_otodom_listing, 
    scrape_otodom, 
    download_raw_otodom_json, 
    download_raw_otodom_dev_json, 
    discover_otodom_developers,
    fetch_otodom_agency_name
)
from .scraper_to import (
    discover_to_investments, 
    discover_to_listing, 
    scrape_tabelaofert, 
    download_raw_to_json, 
    download_raw_to_dev_json, 
    discover_to_developers,
    fetch_to_agency_name
)

def get_scraper_func(portal_prefix: str, func_name: str) -> Optional[Callable]:
    """
    Returns the requested function for a given portal prefix.
    Uses local names to ensure compatibility with unit test mocks.
    """
    registry = {
        "rp": {
            "scrape": scrape_rynek_pierwotny,
            "discover": discover_rp_investments,
            "discover_listing": discover_rp_listing,
            "download_raw": download_raw_rp_json,
            "download_raw_dev": download_raw_rp_dev_json,
            "discover_devs": discover_rp_developers,
        },
        "oto": {
            "scrape": scrape_otodom,
            "discover": discover_otodom_investments,
            "discover_listing": discover_otodom_listing,
            "download_raw": download_raw_otodom_json,
            "download_raw_dev": download_raw_otodom_dev_json,
            "discover_devs": discover_otodom_developers,
        },
        "to": {
            "scrape": scrape_tabelaofert,
            "discover": discover_to_investments,
            "discover_listing": discover_to_listing,
            "download_raw": download_raw_to_json,
            "download_raw_dev": download_raw_to_dev_json,
            "discover_devs": discover_to_developers,
        }
    }
    portal_data = registry.get(portal_prefix)
    if not portal_data:
        return None
    return portal_data.get(func_name)

# ... (keep DEVELIA and other constants)
# ... (keep _check_fields and health_check)

def process_batch(
    config: ScraperConfig,
    fetcher: Fetcher,
    portal: str,
    identifiers: List[str],
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    delay_range: tuple[float, float] = (0.5, 2.0),
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """
    Sekwencyjnie pobiera listę inwestycji z obsługą throttling, retry i raportowaniem postępu.
    Zapisuje dane surowe i zdjęcia natychmiast po pobraniu każdej inwestycji (I/O Isolation).
    """
    total = len(identifiers)
    results = []
    manager = TechnicalDataManager(config)
    try:
        portal_prefix = resolve_prefix(portal.lower())
    except ValueError:
        portal_prefix = "raw"

    for i, identifier in enumerate(identifiers):
        current_index = i + 1
        progress_percent = int((current_index / total) * 100)
        
        data = None
        error_msg = None
        status = "failed"
        
        for attempt in range(max_retries):
            try:
                scrape_func = get_scraper_func(portal_prefix, "scrape")
                if not scrape_func:
                    raise ValueError(f"No scrape function found for portal: {portal_prefix}")
                
                data = scrape_func(identifier, fetcher)
                
                if data and "error" in data:
                    error_msg = str(data["error"])
                    if "429" in error_msg or "timeout" in error_msg.lower():
                        if on_progress:
                            on_progress({
                                "total": total,
                                "current_index": current_index,
                                "progress_percent": progress_percent,
                                "status": "retrying",
                                "investment": {"identifier": identifier},
                                "message": f"Próba {attempt + 1}/{max_retries}: {error_msg}. Czekam 10s...",
                                "error_details": error_msg
                            })
                        time.sleep(10)
                        continue
                    else:
                        break # Inny błąd - nie ponawiamy
                
                status = "success"
                error_msg = None
                break
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    time.sleep(10)
                    continue
                break

        # I/O Isolation & Reporting
        msg = ""
        inv_info = {"identifier": identifier, "dev_slug": None, "inv_slug": None}
        
        if status == "success" and data:
            dev_slug = data.get("developer_slug")
            inv_slug = data.get("investment_slug")
            
            if not dev_slug or not inv_slug:
                status = "failed"
                error_msg = f"Incomplete data: missing developer_slug ({dev_slug}) or investment_slug ({inv_slug})"
                msg = f"Pobranie nieudane: {error_msg}"
            else:
                inv_info["dev_slug"] = dev_slug
                inv_info["inv_slug"] = inv_slug
                
                # Zapis danych surowych
                manager.save_raw_data(data, dev_slug, inv_slug, portal_prefix)
                
                # Synchronizacja zdjęć
                image_urls = data.get("image_urls", [])
                saved_images = manager.sync_images(image_urls, dev_slug, inv_slug)
                msg = f"Pobrano pomyślnie i zapisano {len(saved_images)} zdjęć."
        else:
            msg = f"Pobranie nieudane: {error_msg}"

        if on_progress:
            on_progress({
                "total": total,
                "current_index": current_index,
                "progress_percent": progress_percent,
                "status": status,
                "investment": inv_info,
                "message": msg,
                "error_details": error_msg if status == "failed" else None
            })

        results.append(data)

        # Throttling
        if i < total - 1:
            time.sleep(random.uniform(*delay_range))

    return results

def _check_fields(data: Dict[str, Any], portal: str) -> tuple[list[str], list[str]]:
    try:
        prefix = resolve_prefix(portal)
        required = get_portal(prefix).get("required_fields", [])
    except ValueError:
        required = []
    ok, missing = [], []
    for f in required:
        val = data.get(f)
        if val is None or val == [] or val == "":
            missing.append(f)
        else:
            ok.append(f)
    return ok, missing


def health_check(
    config: Optional[ScraperConfig] = None,
    fetcher: Optional[Fetcher] = None,
    portals: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Smoke-test: sprawdza discovery i scrape dla każdego portalu.
    Zwraca słownik z wynikami per portal i globalnym 'ok'.

    Jeśli config lub fetcher nie zostaną podane, zostaną zainicjowane
    automatycznie z domyślnymi ustawieniami i ścieżką /tmp.

    Domyślnie testuje wszystkie trzy portale. Można ograniczyć listą:
    portals=["rp"], portals=["otodom", "tabelaofert"] itp.
    """
    if config is None:
        from .models import ScraperConfig
        import tempfile
        config = ScraperConfig(public_dir=Path(tempfile.gettempdir()))

    if fetcher is None:
        from .fetcher import Fetcher
        fetcher = Fetcher(config)

    if portals is None:
        portals = ["rp", "otodom", "tabelaofert"]

    results: Dict[str, Any] = {}

    for portal in portals:
        try:
            p = resolve_prefix(portal.lower())
        except ValueError:
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
            discover_func = get_scraper_func(p, "discover")
            scrape_func = get_scraper_func(p, "scrape")
            
            if not discover_func or not scrape_func:
                raise ValueError(f"Nieznany portal: {portal}")

            if p == "oto":
                items = discover_func(config, fetcher, get_portal("oto")["health_check"]["probe_id"], limit=1)
            elif p == "to":
                discover_listing = get_scraper_func(p, "discover_listing")
                items = discover_listing(config, fetcher, get_portal("to")["health_check"]["probe_url"], limit=1)
            else:
                items = discover_func(config, fetcher, None, limit=1)

            entry["discovery_count"] = len(items)

            if not items:
                entry["error"] = "discovery zwróciło 0 wyników"
                results[portal] = entry
                continue

            inv = items[0]
            url = inv["url"]
            entry["scrape_url"] = url

            data = scrape_func(inv["id"] if p == "rp" else url, fetcher)

            if data.get("error"):
                entry["error"] = f"scrape: {data['error']}"
                results[portal] = entry
                continue

            ok_fields, missing_fields = _check_fields(data, p)
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
) -> List[Dict[str, Any]]:
    """Pobiera listę inwestycji dewelopera ze wskazanego portalu (Discovery)."""
    p = resolve_prefix(portal)
    discover_func = get_scraper_func(p, "discover")
    if not discover_func:
        raise ValueError(f"Unsupported portal for discovery: {portal}")

    if p == "oto":
        if identifier and identifier.startswith("http"):
            discover_listing = get_scraper_func(p, "discover_listing")
            return discover_listing(config, fetcher, identifier)
        return discover_func(config, fetcher, identifier)
    
    return discover_func(config, fetcher, identifier)


def fetch_many(
    config: ScraperConfig,
    fetcher: Fetcher,
    portal: str,
    investments: List[Dict[str, Any]],
    on_progress: Optional[ProgressCallback] = None,
) -> List[Dict[str, Any]]:
    """
    Pobiera szczegóły listy inwestycji z opcjonalnym raportowaniem postępu.

    Każdy element investments musi zawierać klucz: "identifier".
    Zwraca listę wyników w tej samej kolejności co investments.
    """
    total = len(investments)
    results = []
    for i, inv in enumerate(investments):
        result = fetch_investment(config, fetcher, portal, inv["identifier"])
        results.append(result)
        if on_progress:
            current_index = i + 1
            on_progress({
                "total": total,
                "current_index": current_index,
                "progress_percent": int((current_index / total) * 100) if total else 100,
                "status": "failed" if result.get("error") else "success",
                "investment": {"identifier": inv["identifier"]},
                "message": "",
                "error_details": str(result["error"]) if result.get("error") else None,
            })
    return results

def fetch_investment(
    config: ScraperConfig, 
    fetcher: Fetcher, 
    portal: str, 
    identifier: str,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """Pobiera szczegóły konkretnej inwestycji ze wskazanego portalu (Scrape)."""
    data = {}
    error_msg = None
    status = "failed"

    try:
        p = resolve_prefix(portal)
        scrape_func = get_scraper_func(p, "scrape")
        if not scrape_func:
            raise ValueError(f"Unsupported portal for fetching: {portal}")

        data = scrape_func(identifier, fetcher)
        if data and data.get("error"):
            error_msg = str(data["error"])
        else:
            status = "success"
    except Exception as e:
        error_msg = str(e)
        data = {"error": error_msg}

    if on_progress:
        msg = "Pobrano pomyślnie." if status == "success" else f"Pobranie nieudane: {error_msg}"
        dev_slug = data.get("developer_slug") if status == "success" else None
        inv_slug = data.get("investment_slug") if status == "success" else None

        on_progress({
            "total": 1,
            "current_index": 1,
            "progress_percent": 100,
            "status": status,
            "investment": {
                "identifier": identifier,
                "dev_slug": dev_slug,
                "inv_slug": inv_slug
            },
            "message": msg,
            "error_details": error_msg if status == "failed" else None
        })

    return data

def download_raw(config: ScraperConfig, fetcher: Fetcher, portal: str, identifier: str, dev_slug: str, inv_slug: str) -> Optional[Path]:
    """Pobiera i zapisuje surowy JSON inwestycji."""
    p = resolve_prefix(portal)
    func = get_scraper_func(p, "download_raw")
    if func:
        return func(identifier, dev_slug, inv_slug, fetcher, config)
    return None

def download_raw_dev(config: ScraperConfig, fetcher: Fetcher, portal: str, identifier: str, dev_slug: str) -> Optional[Path]:
    """Pobiera i zapisuje surowy JSON profilu dewelopera."""
    p = resolve_prefix(portal)
    func = get_scraper_func(p, "download_raw_dev")
    if func:
        return func(identifier, dev_slug, fetcher, config)
    return None

def save_raw(config: ScraperConfig, data: Dict[str, Any], dev_slug: str, inv_slug: str, portal_prefix: str, portal_id: str) -> Path:
    """Zapisuje gotowy słownik jako surowy JSON inwestycji. portal_id jest wymagane."""
    return save_raw_json(data, config.public_dir, dev_slug, inv_slug, portal_prefix, portal_id=portal_id)

def save_raw_developer(config: ScraperConfig, data: Dict[str, Any], dev_slug: str, portal_prefix: str, portal_id: str) -> Path:
    """Zapisuje gotowy słownik jako surowy JSON dewelopera. portal_id jest wymagane."""
    return save_dev_raw_json(data, config.public_dir, dev_slug, portal_prefix, portal_id=portal_id)

def list_developers(
    config: ScraperConfig,
    fetcher: Fetcher,
    portal: str,
    page: int = 1,
    base_url: Optional[str] = None,
) -> DeveloperPage:
    """Pobiera jedną stronę katalogu deweloperów ze wskazanego portalu."""
    p = resolve_prefix(portal)
    func = get_scraper_func(p, "discover_devs")
    if func:
        return func(fetcher, page=page, base_url=base_url)
    raise ValueError(f"Unsupported portal for developer listing: {portal}")


def identify_developer(fetcher: Fetcher, portal: str, url: str) -> Optional[str]:
    """Próbuje zidentyfikować nazwę dewelopera na podstawie URL oferty."""
    p = resolve_prefix(portal)
    # This one is a bit specific as it's not in the main SCRAPER_REGISTRY yet
    # but we can add it or handle it separately.
    if p == "oto":
        from .scraper_otodom import fetch_otodom_agency_name
        return fetch_otodom_agency_name(url, fetcher)
    elif p == "to":
        from .scraper_to import fetch_to_agency_name
        return fetch_to_agency_name(url, fetcher)
    return None

def verify_consistency(
    config: Optional[ScraperConfig] = None,
    fetcher: Optional[Fetcher] = None,
    portals: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Alias dla health_check. Zapewnia wsteczną kompatybilność.
    @deprecated: Używaj health_check() zamiast tej funkcji.
    """
    warnings.warn(
        "verify_consistency() jest przestarzałe i zostanie usunięte w przyszłości. "
        "Użyj health_check() zamiast tego.",
        DeprecationWarning,
        stacklevel=2
    )
    return health_check(config, fetcher, portals)
