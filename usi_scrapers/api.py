from .manager import TechnicalDataManager
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
from .mapping import get_mapping, resolve_path, load_mapping, list_available_keys, transform_to_unified

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

def process_batch_ingest(
    config: "ScraperConfig",
    fetcher: "Fetcher",
    portal: str,
    urls: List[str],
    on_progress: "Optional[Callable[[Dict[str, Any]], None]]" = None,
    delay_range: tuple[float, float] = (0.5, 2.0),
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """
    Sekwencyjnie pobiera listę inwestycji po ich URL-ach.
    """
    total = len(urls)
    results = []
    
    for i, url in enumerate(urls):
        current_index = i + 1
        progress_percent = int((current_index / total) * 100)
        
        data = None
        error_msg = None
        status = "failed"
        
        for attempt in range(max_retries):
            try:
                data = ingest_investment_by_url(config, fetcher, portal, url)
                if data and "error" in data:
                    error_msg = str(data["error"])
                    if "429" in error_msg or "timeout" in error_msg.lower():
                        if on_progress:
                            on_progress({
                                "total": total,
                                "current_index": current_index,
                                "progress_percent": progress_percent,
                                "status": "retrying",
                                "investment": {"url": url},
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

        msg = ""
        inv_info = {"url": url}
        
        if status == "success" and data:
            dev_slug = data.get("developer_slug")
            inv_slug = data.get("investment_slug")
            if not dev_slug or not inv_slug:
                status = "failed"
                error_msg = "Invalid or incomplete data: missing dev_slug or inv_slug in data"
                msg = f"Pobranie nieudane: {error_msg}"
            else:
                # Synchronizacja zdjęć
                from .utils.io import get_image_dir
                target_image_dir = get_image_dir(dev_slug, inv_slug, config.public_dir)
                image_urls = data.get("image_urls", [])
                manager = TechnicalDataManager(config)
                saved_images = manager.sync_images(image_urls, target_image_dir)
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

        if i < total - 1:
            time.sleep(random.uniform(*delay_range))

    return results

def process_batch_refresh(
    config: "ScraperConfig",
    fetcher: "Fetcher",
    portal: str,
    portal_ids: List[str],
    on_progress: "Optional[Callable[[Dict[str, Any]], None]]" = None,
    delay_range: tuple[float, float] = (0.5, 2.0),
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """
    Sekwencyjnie pobiera listę inwestycji po ich zapisanych ID.
    """
    total = len(portal_ids)
    results = []
    
    for i, portal_id in enumerate(portal_ids):
        current_index = i + 1
        progress_percent = int((current_index / total) * 100)
        
        data = None
        error_msg = None
        status = "failed"
        
        for attempt in range(max_retries):
            try:
                data = refresh_investment_by_id(config, fetcher, portal, portal_id)
                if data and "error" in data:
                    error_msg = str(data["error"])
                    if "429" in error_msg or "timeout" in error_msg.lower():
                        if on_progress:
                            on_progress({
                                "total": total,
                                "current_index": current_index,
                                "progress_percent": progress_percent,
                                "status": "retrying",
                                "investment": {"portal_id": portal_id},
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

        msg = ""
        inv_info = {"portal_id": portal_id}
        
        if status == "success" and data:
            dev_slug = data.get("developer_slug")
            inv_slug = data.get("investment_slug")
            if not dev_slug or not inv_slug:
                status = "failed"
                error_msg = "Invalid or incomplete data: missing dev_slug or inv_slug in data"
                msg = f"Pobranie nieudane: {error_msg}"
            else:
                # Synchronizacja zdjęć
                from .utils.io import get_image_dir
                target_image_dir = get_image_dir(dev_slug, inv_slug, config.public_dir)
                image_urls = data.get("image_urls", [])
                manager = TechnicalDataManager(config)
                saved_images = manager.sync_images(image_urls, target_image_dir)
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



def _validate_and_register_id(data: dict, portal_prefix: str, url: str, config: "ScraperConfig"):
    if data and not data.get("error"):
        manager = TechnicalDataManager(config)
        manager.save_raw_data(data, portal_prefix)

def ingest_investment_by_url(
    config: "ScraperConfig", 
    fetcher: "Fetcher", 
    portal: str, 
    url: str,
    on_progress: "Optional[Callable[[Dict[str, Any]], None]]" = None
) -> dict:
    """
    PIERWSZY PUNKT WEJŚCIA: Pobiera inwestycję po surowym adresie URL.
    Wyciąga ID, inicjalizuje strukturę i zapisuje dane na dysk.
    """
    data = {}
    error_msg = None
    status = "failed"
    
    try:
        portal_prefix = resolve_prefix(portal)
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Metoda ingest_by_url wymaga pełnego adresu URL, przekazano: {url}")
            
        scrape_func = get_scraper_func(portal_prefix, "scrape")
        if not scrape_func:
            raise ValueError(f"Unsupported portal for fetching: {portal}")
            
        scrape_arg = url
        if portal_prefix == "rp":
            from .utils.url_parser import parse_url
            parsed = parse_url(url)
            if parsed and parsed.get("offer_id"):
                scrape_arg = parsed["offer_id"]
            else:
                raise ValueError(f"Nie można wyekstrahować ID z URL: {url}")

        data = scrape_func(scrape_arg, fetcher)
        if data and data.get("error"):
            error_msg = str(data["error"])
        else:
            status = "success"
            _validate_and_register_id(data, portal_prefix, url, config)
    except Exception as e:
        error_msg = str(e)
        data = {"error": error_msg}

    if on_progress:
        msg = "Pobrano pomyślnie." if status == "success" else f"Pobranie nieudane: {error_msg}"
        on_progress({
            "total": 1,
            "current_index": 1,
            "progress_percent": 100,
            "status": status,
            "investment": {
                "url": url,
                "dev_slug": data.get("developer_slug") if status == "success" else None,
                "inv_slug": data.get("investment_slug") if status == "success" else None
            },
            "message": msg,
            "error_details": error_msg if status == "failed" else None
        })

    return data

def refresh_investment_by_id(
    config: "ScraperConfig", 
    fetcher: "Fetcher", 
    portal: str, 
    portal_id: str,
    on_progress: "Optional[Callable[[Dict[str, Any]], None]]" = None
) -> dict:
    """
    KOLEJNE URUCHOMIENIA: Odświeża dane na podstawie wyekstrahowanego ID.
    Jeśli scraper potrzebuje URL do odświeżenia, API pobiera go z lokalnego indeksu/pliku.
    """
    data = {}
    error_msg = None
    status = "failed"

    try:
        portal_prefix = resolve_prefix(portal)
        
        if portal_prefix == "rp" and not str(portal_id).isdigit():
            raise ValueError(f"Portal RP wymaga numerycznego ID: {portal_id}")

        from .storage import get_resolver
        resolver = get_resolver(config)
        
        saved_meta = resolver.get_investment_metadata(portal_prefix, str(portal_id))
        if not saved_meta:
            raise FileNotFoundError(f"Inwestycja o ID {portal_id} nie istnieje lokalnie na dysku.")
            
        url_reference = saved_meta.get("source_url")
        
        scrape_func = get_scraper_func(portal_prefix, "scrape")
        if not scrape_func:
            raise ValueError(f"Unsupported portal for fetching: {portal}")

        scrape_arg = url_reference if portal_prefix in ("oto", "to") else portal_id
        if portal_prefix in ("oto", "to") and not scrape_arg:
            raise ValueError(f"Brak zapisanego URL dla inwestycji {portal_id} w portalu {portal_prefix}")

        data = scrape_func(scrape_arg, fetcher)
        if data and data.get("error"):
            error_msg = str(data["error"])
        else:
            status = "success"
            _validate_and_register_id(data, portal_prefix, url_reference or portal_id, config)
    except Exception as e:
        error_msg = str(e)
        data = {"error": error_msg}

    if on_progress:
        msg = "Pobrano pomyślnie." if status == "success" else f"Pobranie nieudane: {error_msg}"
        on_progress({
            "total": 1,
            "current_index": 1,
            "progress_percent": 100,
            "status": status,
            "investment": {
                "portal_id": portal_id,
                "dev_slug": data.get("developer_slug") if status == "success" else None,
                "inv_slug": data.get("investment_slug") if status == "success" else None
            },
            "message": msg,
            "error_details": error_msg if status == "failed" else None
        })

    return data


def download_raw(config: ScraperConfig, fetcher: Fetcher, portal: str, identifier: str) -> Dict[str, Any]:
    """Pobiera i zapisuje surowy JSON inwestycji. Zwraca status i metadane."""
    p = resolve_prefix(portal)
    scrape_func = get_scraper_func(p, "scrape")
    if not scrape_func:
        return {"status": "error", "message": f"Unsupported portal for downloading: {portal}"}
    
    data = scrape_func(identifier, fetcher)
    if data and "error" not in data:
        manager = TechnicalDataManager(config)
        path = manager.save_raw_data(data, p)
        if path:
            portal_id = data.get("id") or data.get("oto_url_id") or data.get("to_id")
            return {
                "status": "success",
                "portal_id": str(portal_id),
                "dev_slug": data.get("developer_slug"),
                "inv_slug": data.get("investment_slug")
            }
        else:
            return {"status": "error", "message": "Failed to save raw data"}
    else:
        return {"status": "error", "message": data.get("error", "Unknown error")}

def download_raw_dev(config: ScraperConfig, fetcher: Fetcher, portal: str, portal_id: str) -> Dict[str, Any]:
    """Pobiera i zapisuje surowy JSON profilu dewelopera po jego ID."""
    p = resolve_prefix(portal)
    func = get_scraper_func(p, "download_raw_dev")
    if not func:
        return {"status": "error", "message": f"No dev scraper found for {portal}"}
        
    from .storage import get_resolver
    resolver = get_resolver(config)
    dev_slug = resolver.lookup_developer(p, str(portal_id))
    if not dev_slug:
        dev_slug = f"unknown_{p}_{portal_id}"
        
    target_dir = Path(config.public_dir) / "USIdev" / dev_slug
    result_slug = func(portal_id, target_dir, fetcher, config)
    if result_slug:
        return {"status": "success", "dev_slug": result_slug}
    return {"status": "error", "message": "Failed to download developer data"}

def get_raw_data(config: ScraperConfig, portal: str, portal_id: str) -> Optional[Dict[str, Any]]:
    """Pobiera surowy JSON inwestycji używając StorageResolvera do znalezienia ścieżki."""
    from .storage import get_resolver
    import json
    p = resolve_prefix(portal)
    resolver = get_resolver(config)
    result = resolver.lookup_investment(p, portal_id)
    if not result:
        return None
    
    dev_slug, inv_slug = result
    from .utils.io import get_investment_dir
    target_dir = get_investment_dir(dev_slug, inv_slug, config.public_dir)
    file_path = target_dir / f"raw_{p}_{portal_id}.json"
    
    if not file_path.exists():
        return None
        
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_raw_dev_data(config: ScraperConfig, portal: str, portal_id: str) -> Optional[Dict[str, Any]]:
    """Pobiera surowy JSON dewelopera używając StorageResolvera do znalezienia ścieżki."""
    from .storage import get_resolver
    import json
    p = resolve_prefix(portal)
    resolver = get_resolver(config)
    dev_slug = resolver.lookup_developer(p, portal_id)
    if not dev_slug:
        return None
    
    target_dir = Path(config.public_dir) / "USIdev" / dev_slug
    file_path = target_dir / f"raw_{p}_{portal_id}.json"
    
    if not file_path.exists():
        return None
        
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_raw(config: ScraperConfig, data: Dict[str, Any], portal_prefix: str, portal_id: str) -> Path:
    """
    Zapisuje gotowy słownik jako surowy JSON inwestycji.
    ID-ONLY: Jeśli inwestycja już istnieje, ścieżka wyznaczana jest z indeksu na podstawie portal_id.
    Dla nowych inwestycji wymagane są 'developer_slug' i 'investment_slug' w envelope (data).
    """
    from .storage import get_resolver
    resolver = get_resolver(config)
    
    # 1. Próba rezolucji z indeksu (Ruthless ID-only)
    result = resolver.lookup_investment(portal_prefix, portal_id)
    if result:
        dev_slug, inv_slug = result
    else:
        # 2. Fallback do danych (tylko dla nowych inwestycji)
        dev_slug = data.get("developer_slug")
        inv_slug = data.get("investment_slug")
        
    if not dev_slug or not inv_slug:
        raise ValueError(f"save_raw: Nie można wyznaczyć ścieżki dla {portal_prefix}/{portal_id}. Brak slugów w indeksie i danych.")

    # 3. Wyodrębnienie czystych danych (Pure-Raw)
    # Jeśli data zawiera envelope (np. z fetch_investment), wyciągamy tylko raw_details
    raw_to_save = data.get("raw_details", data)

    from .utils.io import save_raw_json, get_investment_dir
    target_dir = get_investment_dir(dev_slug, inv_slug, config.public_dir)
    file_path = save_raw_json(raw_to_save, target_dir, portal_prefix, portal_id=portal_id)
    
    # Aktualizacja indeksu (niezbędne dla nowych lub przy zmianie slugów)
    resolver.update_investment_index(portal_prefix, portal_id, dev_slug, inv_slug)
    return file_path

def save_raw_developer(config: ScraperConfig, data: Dict[str, Any], portal_prefix: str, portal_id: str) -> Path:
    """
    Zapisuje gotowy słownik jako surowy JSON dewelopera.
    ID-ONLY: Ścieżka wyznaczana jest z indeksu lub envelope.
    """
    from .storage import get_resolver
    resolver = get_resolver(config)
    
    dev_slug = resolver.lookup_developer(portal_prefix, portal_id)
    if not dev_slug:
        dev_slug = data.get("developer_slug")
        
    if not dev_slug:
        raise ValueError(f"save_raw_developer: Brak 'developer_slug' dla {portal_prefix}/{portal_id}.")

    raw_to_save = data.get("raw_details", data)

    from .utils.io import save_dev_raw_json
    target_dir = Path(config.public_dir) / "USIdev" / dev_slug
    file_path = save_dev_raw_json(raw_to_save, target_dir, portal_prefix, portal_id=portal_id)
    resolver.update_developer_index(portal_prefix, portal_id, dev_slug)
    return file_path

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

def resolve_image_path(filename: str, config: ScraperConfig) -> Optional[str]:
    """
    Wyszukuje pełną ścieżkę do pliku obrazu w public_dir na podstawie nazwy pliku.
    """
    from .storage import get_resolver
    resolver = get_resolver(config)
    return resolver.find_image_path(filename)

def extract_developer_meta(raw_data: dict, portal: str) -> dict:
    """
    Zwraca zunifikowany słownik z danymi dewelopera: {"id": ..., "slug": ..., "name": ...}.
    Używa portal_data_mapping.json (entity_type='developer') do ekstrakcji.
    Zwraca {} jeśli portal jest nieznany lub raw_data jest puste.
    """
    if not raw_data:
        return {}
    try:
        portal_prefix = resolve_prefix(portal)
    except ValueError:
        return {}
    result = transform_to_unified(portal_prefix, raw_data, entity_type="developer")
    return result if result else {}

def load_raw(config: ScraperConfig, portal: str, portal_id: str) -> Optional[Dict[str, Any]]:
    """
    Wczytuje surowy JSON inwestycji z lokalnego dysku.
    Publiczny, czytelny punkt wejścia dla klientów (np. usi-tracker) do odczytu
    pobranych danych bez znajomości wewnętrznej struktury katalogów.
    Zwraca None jeśli inwestycja nie istnieje lokalnie.
    """
    return get_raw_data(config, portal, portal_id)

def has_local_raw(config: ScraperConfig, portal: str, portal_id: str) -> bool:
    """
    Sprawdza czy surowy JSON inwestycji istnieje lokalnie (bez wczytywania zawartości).
    Lekkie sprawdzenie bool — idealne do walidacji przed uruchomieniem scrapera.
    Zwraca False jeśli portal jest nieznany lub inwestycja nie jest w indeksie.
    """
    try:
        p = resolve_prefix(portal)
    except ValueError:
        return False
    from .storage import get_resolver
    from .utils.io import get_investment_dir
    resolver = get_resolver(config)
    result = resolver.lookup_investment(p, portal_id)
    if not result:
        return False
    dev_slug, inv_slug = result
    file_path = get_investment_dir(dev_slug, inv_slug, config.public_dir) / f"raw_{p}_{portal_id}.json"
    return file_path.exists()
