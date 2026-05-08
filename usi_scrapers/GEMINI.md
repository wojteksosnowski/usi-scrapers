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
3.  **Adapters (`adapters/`)**: Mapowanie surowych danych na wspólny schemat.
    - `BaseAdapter`: Interfejs bazowy.
    - `Merger`: Logika scalania danych z wielu źródeł z uwzględnieniem priorytetów i historii zmian (audit log).
4.  **Manager (`manager.py`)**: Zarządzanie zapisem plików JSON i obrazów w strukturze katalogowej `Public`.

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
- **Publiczne API**: Główne funkcje interakcji znajdują się w `api.py`.

## Konwencje i Standardy

### Struktura Plików w `Public`:
- `USI/{dev_slug}/{inv_slug}/usi_{inv_slug}.json`: Główny plik zintegrowany.
- `USI/{dev_slug}/{inv_slug}/raw_{portal}_{timestamp}.json`: Surowe dane źródłowe.
- `USI/{dev_slug}/{inv_slug}/*.webp`: Pobrane i zoptymalizowane obrazy.

### Zasady Kodowania:
- **Typowanie**: Obowiązkowe użycie Type Hints dla wszystkich funkcji publicznych.
- **Logowanie**: Używaj dedykowanych loggerów per moduł (np. `logger = logging.getLogger(__name__)`).
- **Bezpieczeństwo**: Nigdy nie hardkoduj kluczy API. Używaj `ScraperConfig`.
- **Surgical Updates**: Przy modyfikacji logiki scrapowania, zawsze sprawdzaj wpływ na adaptery i wykonuj testy regresyjne.

## TODO / Przyszły Rozwój
- [ ] Implementacja pełnej walidacji schematów Pydantic przy transformacji.
- [ ] Rozszerzenie `geocoder.py` o pełną integrację z danymi POI z HERE Maps.
- [ ] Automatyzacja wykrywania zmian w strukturze HTML portali (monitoring błędów parsowania).
