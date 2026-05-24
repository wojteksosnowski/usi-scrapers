# Struktura Projektu usi-scrapers

Dokument opisuje podział projektu na moduły oraz odpowiedzialność poszczególnych plików. Projekt jest zorganizowany w sposób modularny, oddzielając warstwę komunikacji sieciowej, silnik ekstrakcji danych oraz logikę specyficzną dla poszczególnych portali.

---

## 1. Główne Pakiety i Moduły (`usi_scrapers/`)

Jest to serce pakietu, zawierające całą logikę biznesową i techniczną.

| Plik | Odpowiedzialność |
| :--- | :--- |
| `__init__.py` | Punkt wejścia pakietu. Eksportuje publiczne API (`get_mapping`, `classify_segment`, `get_logger`) oraz wersję pakietu. |
| `api.py` | Wysokopoziomowe funkcje dla użytkownika (np. `fetch_investment`, `process_batch`, `health_check`). Główne interface komunikacyjny dla aplikacji zewnętrznych. |
| `fetcher.py` | Warstwa transportowa HTTP. Obsługuje rotację strategii (Impersonate Chrome vs ScraperAPI), retry i rate-limiting. |
| `manager.py` | `TechnicalDataManager` — zarządza technicznymi operacjami I/O: wyznaczaniem ścieżek, zapisem surowych plików JSON oraz synchronizacją obrazów. |
| `mapping.py` | Silnik ekstrakcji danych. Udostępnia metody `load_mapping`, `get_mapping` oraz `resolve_path` do wydobywania informacji z JSON przy użyciu ścieżek z `portal_data_mapping.json`. |
| `models.py` | Definicje klas danych (Dataclasses), w tym konfiguracji `ScraperConfig`. |
| `portals.json` | Deklaratywna konfiguracja portali: wzorce URL, endpointy API, limity odpytywania. |
| `scraper_otodom.py` | Logika specyficzna dla Otodom (parsowanie HTML `__NEXT_DATA__`). |
| `scraper_rp.py` | Logika specyficzna dla RynekPierwotny (komunikacja z wewnętrznym API portalu). |
| `scraper_to.py` | Logika specyficzna dla TabelaOfert (JSON-LD + ekstrakcja z HTML). |
| `import_usimaster_csv.py` | Importer danych redakcyjnych (ocen, komentarzy) z plików CSV do struktury `USIdata/`. |
| `import_competitors_csv.py` | Importer mapowań deweloperów z plików CSV do struktury `USIdev/`. |

### Podkatalogi wewnątrz `usi_scrapers/`

*   **`utils/`**: Współdzielone narzędzia pomocnicze:
    *   `classifier.py`: Agnostyczna klasyfikacja inwestycji na segmenty (USI Signals).
    *   `images.py`: Pobieranie zdjęć, czyszczenie nazw plików, obsługa logotypów.
    *   `io.py`: Operacje na systemie plików (zapis raw/meta, lookupy po ID).
    *   `portals.py`: Helpery do obsługi `portals.json`.
    *   `scrapers.py`: Generyczna logika scrapowania (shared discovery, dev profile).
    *   `string.py`: Autorski `slugify` z obsługą polskich znaków.
    *   `url_parser.py`: Rozbijanie URLi portalowych na strukturalne identyfikatory.
    *   `stage_detector.py`: Detekcja etapów inwestycji (współdzielone z usi-tracker).
*   **`schemas/`**: Definicje struktur danych:
    *   `portal_data_mapping.json`: Kluczowy plik mapujący pola portali na agnostyczne klucze USI.
    *   `usi_unified.schema.json`: Schemat JSON dla zunifikowanych danych inwestycji.
    *   Pozostałe schematy `.schema.json` służą do walidacji danych surowych.
*   **`docs/`**: Dokumentacja techniczna API oraz instrukcje integracji z Coda.

---

## 2. Katalogi Pomocnicze i Dane

| Katalog | Zawartość |
| :--- | :--- |
| `reference/` | Dane referencyjne, pliki CSV z listą konkurentów i bazą USImaster. |
| `scripts/` | Skrypty administracyjne, narzędzia do czyszczenia danych i testy typu "dry-run". |
| `tests/` | Kompletna suita testowa (Pytest). Zawiera testy jednostkowe, integracyjne i testy mappingu na rzeczywistych danych. |
| `archive/` | Skrypty historyczne, jednorazowe narzędzia do migracji danych. |

---

## 3. Pliki Konfiguracyjne Projektu

| Plik | Rola |
| :--- | :--- |
| `pyproject.toml` | Konfiguracja budowania pakietu, zależności (pip) i metadane wersji. |
| `CHANGELOG.md` | Rejestr zmian w pakiecie. |
| `CLAUDE.md` | Przewodnik dla agentów LLM (konwencje kodowania, technologia, komendy). |
| `canonical-*.md` | "Źródło prawdy" dla konwencji nazewnictwa i interakcji między modułami. |
| `README.md` | Ogólny opis pakietu i instrukcja instalacji. |

---

## Przepływ Danych (Data Flow)

1.  **Fetch**: `fetcher.py` pobiera dane (HTML/JSON) z portalu.
2.  **Scrape**: `scraper_*.py` wyciąga istotne fragmenty i identyfikuje dewelopera/inwestycję.
3.  **Map**: `mapping.py` używa `portal_data_mapping.json` do wyciągnięcia Agnostycznych Sygnałów (`signals`).
4.  **Classify**: `utils/classifier.py` nadaje inwestycji segment na podstawie sygnałów.
5.  **Store**: `TechnicalDataManager` (`manager.py`) zapisuje pliki surowe w ustandaryzowanej strukturze folderów.
