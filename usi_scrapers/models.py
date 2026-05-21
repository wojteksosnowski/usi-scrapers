from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List

from .utils.portals import default_fetch_delays

# Called with a progress dict after each item is processed.
# Keys: total, current_index, progress_percent, status, investment, message, error_details
ProgressCallback = Callable[[Dict[str, Any]], None]


@dataclass
class DeveloperPage:
    """Wynik pobrania jednej strony listy deweloperów z portalu."""
    developers: List[Dict[str, Any]]
    total_pages: int
    page: int

@dataclass
class ScraperConfig:
    """
    Konfiguracja główna pakietu usi-scrapers.
    Aplikacja matka powinna zainicjalizować ten obiekt i przekazać go do logiki scrapującej.
    """
    # Główny katalog Public (np. /Volumes/Public), wewnątrz którego znajdują się USI/ i USIdata/
    public_dir: Path
    
    # Ustawienia sieciowe i fallback do ScraperAPI
    scraperapi_key: Optional[str] = None

    # Adresy URL do globalnego skanowania portali (Discovery)
    rp_discovery_urls: List[str] = field(default_factory=list)
    otodom_discovery_urls: List[str] = field(default_factory=list)
    to_discovery_urls: List[str] = field(default_factory=list)
    
    # Limity odpytywania (rate limiting) per domena (w sekundach)
    fetch_delays: Dict[str, float] = field(default_factory=default_fetch_delays)
    
    # Wymuś ponowne pobieranie obrazów pomimo tego, że już istnieją
    force_image_download: bool = False
