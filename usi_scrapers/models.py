from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List

# Called with (current, total) after each item is processed.
ProgressCallback = Callable[[int, int], None]


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

    # HERE Maps API Key dla geokodowania i wzbogacania danych POI
    here_api_key: Optional[str] = None
    
    # Adresy URL do globalnego skanowania portali (Discovery)
    rp_discovery_urls: List[str] = field(default_factory=list)
    otodom_discovery_urls: List[str] = field(default_factory=list)
    to_discovery_urls: List[str] = field(default_factory=list)
    
    # Limity odpytywania (rate limiting) per domena (w sekundach)
    fetch_delays: Dict[str, float] = field(default_factory=lambda: {
        "rynekpierwotny.pl": 0.5,
        "otodom.pl": 1.0,
        "tabelaofert.pl": 0.5,
        "default": 0.5
    })
