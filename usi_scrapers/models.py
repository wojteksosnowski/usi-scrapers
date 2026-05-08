from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

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
    scraperapi_limit: int = 1000
    
    # Ścieżka do pliku ze statystykami użycia ScraperAPI (np. gdzieś w USIdata/)
    usage_stats_path: Optional[Path] = None
    
    # Limity odpytywania (rate limiting) per domena (w sekundach)
    fetch_delays: Dict[str, float] = field(default_factory=lambda: {
        "rynekpierwotny.pl": 0.5,
        "otodom.pl": 1.0,
        "tabelaofert.pl": 0.5,
        "default": 0.5
    })

