# GEMINI.md - USI Scrapers

Ten plik zawiera wytyczne architektoniczne, instrukcje deweloperskie oraz konwencje stosowane w projekcie `usi-scrapers`.

## Przegląd Projektu

`usi-scrapers` to wyspecjalizowany pakiet Python służący do scrapowania danych o inwestycjach mieszkaniowych z głównych polskich portali nieruchomości (Otodom, RynekPierwotny, TabelaOfert) oraz ich transformacji do ustandaryzowanego formatu USI (Unified Schema for Investments).

### Kluczowe Technologie:
- **Python 3.13+** (wykorzystuje najnowsze funkcje języka).
- **curl_cffi**: Używany do impersonacji przeglądarki (Chrome) w celu ominięcia zabezpieczeń anty-botowych (np. JA3 fingerprinting).
- **ScraperAPI**: Fallback dla zapytań blokowanych przez standardowe metody.
- **Pydantic / JSON Schema**: Walidacja struktur danych.
- **Pytest**: Infrastruktura testowa.

## Architektura Systemu

System opiera się na przepływie: **Fetch -> Scrape -> Adapt -> Merge**.

1.  **Fetcher (`fetcher.py`)**: Centralny punkt obsługi zapytań HTTP z obsługą rate-limitingu i rotacji strategii (impersonate vs scraperapi).
2.  **Scrapers (`scraper_*.py`)**: Logika specyficzna dla portalu, wyciągająca surowe dane (Raw JSON) z HTML lub ukrytych API.
3.  **Manager (`manager.py`)**: Klasa `TechnicalDataManager` odpowiedzialna za techniczne operacje I/O: zarządzanie ścieżkami katalogów, zapis surowych plików JSON oraz pobieranie i synchronizację obrazów w strukturze `Public`. Semantyczne scalanie danych jest delegowane do nadrzędnego trackera.
4.  **Agnostyczne Sygnały (Signals)**: System ujednoliconych wskaźników (`apartments`, `houses`, `commercial`, `investment`, `rental`) wyciąganych przez mapping, służący do automatycznej klasyfikacji inwestycji.
5.  **Modele i Schematy (`models.py`, `schemas/`)**: `models.py` przechowuje główne struktury konfiguracyjne (`ScraperConfig`), natomiast katalog `schemas/` dostarcza pliki JSON Schema używane do walidacji spójności pobranych danych (np. `usi_unified.schema.json`).

## Instrukcje Deweloperskie

### Instalacja i Konfiguracja:
```bash
# Instalacja w trybie edytowalnym z zależnościami dev
pip install -e ".[dev]"
```

### Uruchamianie Testów:
```bash
# Wszystkie testy
pytest

# Testy konkretnego portalu
pytest tests/test_scraper_otodom.py
```

### Główne Komendy i Przepływy:
- **Inicjalizacja**: Zawsze wymagany jest `ScraperConfig` przekazany do `Fetcher` lub `TechnicalDataManager`.
- **Health Check**: Funkcja `health_check()` posiada mechanizm auto-inicjalizacji (używa `/tmp` w razie braku parametrów), co ułatwia monitoring systemu.
- **Kompatybilność**: Alias `verify_consistency` jest zachowany dla wstecznej kompatybilności, ale jest oznaczony jako przestarzały (`DeprecationWarning`).
- **Publiczne API**: Główne funkcje interakcji znajdują się w `api.py`. Pełna dokumentacja dostępna w [docs/API.md](docs/API.md).

## Konwencje i Standardy

### Struktura Plików w `Public`:
- `USI/{dev_slug}/{inv_slug}/usi_{inv_slug}.json`: Główny plik zintegrowany.
- `USI/{dev_slug}/{inv_slug}/raw_{portal}_{timestamp}.json`: Surowe dane źródłowe.
- `USI/{dev_slug}/{inv_slug}/*.webp`: Pobrane i zoptymalizowane obrazy.

### Zasady Kodowania:
- **Identyfikacja Deweloperów**: KRYTYCZNA ZASADA: Zawsze priorytetyzuj identyfikację dewelopera po twardym ID z portalu (`agency_id`, `vendor_id`), a nie po "slugu" z URL. Używaj funkcji `lookup_developer_by_id()` przed stworzeniem nowego rekordu, aby uniknąć duplikacji folderów przy zmianach nazw marketingowych na portalach.
- **Typowanie**: Obowiązkowe użycie Type Hints dla wszystkich funkcji publicznych.
- **Discovery**: Funkcje odkrywające inwestycje muszą posiadać ujednoliconą sygnaturę `discover_*(config, fetcher, identifier=None, limit=None)`. Przy `identifier=None` funkcja powinna wykonywać skanowanie globalne na podstawie URL-i z konfiguracji.
- **Logowanie**: Używaj dedykowanych loggerów per moduł (np. `logger = logging.getLogger(__name__)`).
- **Bezpieczeństwo**: Nigdy nie hardkoduj kluczy API. Używaj `ScraperConfig`.
- **Surgical Updates**: Przy modyfikacji logiki scrapowania, zawsze sprawdzaj wpływ na adaptery i wykonuj testy regresyjne.

## TODO / Przyszły Rozwój
- [ ] Implementacja pełnej walidacji schematów Pydantic przy transformacji.
- [ ] Rozszerzenie `geocoder.py` o pełną integrację z danymi POI z HERE Maps.
- [ ] Automatyzacja wykrywania zmian w strukturze HTML portali (monitoring błędów parsowania).
