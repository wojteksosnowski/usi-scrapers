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
from .scraper_rp import discover_rp_investments, scrape_rynek_pierwotny, download_raw_rp_json, download_raw_rp_dev_json, discover_rp_developers
from .scraper_otodom import discover_otodom_investments, discover_otodom_listing, scrape_otodom, download_raw_otodom_json, download_raw_otodom_dev_json, fetch_otodom_agency_name, discover_otodom_developers
from .scraper_to import discover_to_investments, discover_to_listing, scrape_tabelaofert, download_raw_to_json, download_raw_to_dev_json, fetch_to_agency_name, discover_to_developers
from .utils.io import save_raw_json, save_dev_raw_json

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
    portal_prefix = {"rp": "rp", "oto": "oto", "otodom": "oto", "to": "to", "tabelaofert": "to"}.get(portal.lower(), "raw")

    for i, identifier in enumerate(identifiers):
        current_index = i + 1
        progress_percent = int((current_index / total) * 100)
        
        data = None
        error_msg = None
        status = "failed"
        
        for attempt in range(max_retries):
            try:
                if portal.lower() == "rp":
                    data = scrape_rynek_pierwotny(identifier, fetcher)
                elif portal.lower() in ("oto", "otodom"):
                    data = scrape_otodom(identifier, fetcher)
                else:
                    data = scrape_tabelaofert(identifier, fetcher)
                
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
            dev_slug = data.get("developer_slug", "unknown")
            inv_slug = data.get("investment_slug", "unknown")
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
                items = discover_rp_investments(config, fetcher, None, limit=1)
            elif p in ("oto", "otodom"):
                items = discover_otodom_investments(config, fetcher, _OTO_PROBE_AGENCY_ID, limit=1)
            elif p in ("to", "tabelaofert"):
                items = discover_to_listing(config, fetcher, _TO_PROBE_URL, limit=1)
            else:
                raise ValueError(f"Nieznany portal: {portal}")

            entry["discovery_count"] = len(items)

            if not items:
                entry["error"] = "discovery zwróciło 0 wyników"
                results[portal] = entry
                continue

            inv = items[0]
            url = inv["url"]
            entry["scrape_url"] = url

            if p == "rp":
                data = scrape_rynek_pierwotny(inv["id"], fetcher)
            elif p in ("oto", "otodom"):
                data = scrape_otodom(url, fetcher)
            else:
                data = scrape_tabelaofert(url, fetcher)

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
        return discover_rp_investments(config, fetcher, identifier)
    elif p in ("oto", "otodom"):
        if identifier and not identifier.startswith("http"):
            return discover_otodom_investments(config, fetcher, identifier)
        elif identifier:
            return discover_otodom_listing(config, fetcher, identifier)

        # Global discovery for Otodom is now handled internally
        return discover_otodom_investments(config, fetcher)

    elif p in ("to", "tabelaofert"):
        return discover_to_investments(config, fetcher, identifier)
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

    Każdy element investments musi zawierać klucz: "identifier".
    Zwraca listę wyników w tej samej kolejności co investments.
    """
    total = len(investments)
    results = []
    for i, inv in enumerate(investments):
        result = fetch_investment(config, fetcher, portal, inv["identifier"])
        results.append(result)
        if on_progress:
            on_progress(i + 1, total)
    return results

def fetch_investment(
    config: ScraperConfig, 
    fetcher: Fetcher, 
    portal: str, 
    identifier: str,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """Pobiera szczegóły konkretnej inwestycji ze wskazanego portalu (Scrape)."""
    p = portal.lower()
    data = {}
    error_msg = None
    status = "failed"

    try:
        if p == "rp":
            data = scrape_rynek_pierwotny(identifier, fetcher)
        elif p in ("oto", "otodom"):
            data = scrape_otodom(identifier, fetcher)
        elif p in ("to", "tabelaofert"):
            data = scrape_tabelaofert(identifier, fetcher)
        else:
            raise ValueError(f"Unsupported portal for fetching: {portal}")

        if data and data.get("error"):
            error_msg = str(data["error"])
        else:
            status = "success"
    except Exception as e:
        error_msg = str(e)
        data = {"error": error_msg}

    if on_progress:
        msg = "Pobrano pomyślnie." if status == "success" else f"Pobranie nieudane: {error_msg}"
        dev_slug = data.get("developer_slug", "unknown") if status == "success" else None
        inv_slug = data.get("investment_slug", "unknown") if status == "success" else None

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

def list_developers(
    config: ScraperConfig,
    fetcher: Fetcher,
    portal: str,
    page: int = 1,
    base_url: Optional[str] = None,
) -> DeveloperPage:
    """Pobiera jedną stronę katalogu deweloperów ze wskazanego portalu."""
    p = portal.lower()
    if p == "rp":
        return discover_rp_developers(fetcher, page=page, base_url=base_url)
    elif p in ("oto", "otodom"):
        return discover_otodom_developers(fetcher, page=page, base_url=base_url)
    elif p in ("to", "tabelaofert"):
        return discover_to_developers(fetcher, page=page, base_url=base_url)
    else:
        raise ValueError(f"Unsupported portal for developer listing: {portal}")


def identify_developer(fetcher: Fetcher, portal: str, url: str) -> Optional[str]:
    """Próbuje zidentyfikować nazwę dewelopera na podstawie URL oferty."""
    p = portal.lower()
    if p in ("oto", "otodom"):
        return fetch_otodom_agency_name(url, fetcher)
    elif p in ("to", "tabelaofert"):
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
