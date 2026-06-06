# Changelog

## Wersja 1.1.2 — Kamień 10 (Dynamiczne pobieranie obrazów w Otodom) — 2026-06-06

* Usprawniono funkcję `clean_filename` w `utils/images.py` w celu obcinania wszelkich parametrów modyfikujących (takich jak skale, powiększenia i średniki) z Otodom CDN i TabelaOfert, co zapobiega zniekształceniom rozszerzeń na dysku.
* Wdrożono dynamiczne pobieranie obrazków (I/O) w fazie scrapowania potoku `scraper_otodom.py`. Funkcja zwraca listę ustandaryzowanych, pobranych nazw lokalnych z powrotem do docelowego schematu w polu `image_urls`.

## Wersja 1.1.1 — Kamień 09 (Hardening API & Walidacja URL) — 2026-06-06

* Usunięto lokalne importy (I/O pollution) z metod publicznych w `api.py` na rzecz importów globalnych.
* Wprowadzono twardą walidację na warstwie Discovery w API: 
  - Rozszerzono `url_parser.py` o obsługę adresów URL wyników wyszukiwania (tzw. listing URLs, np. `/pl/wyniki/` w Otodom).
  - Wymuszono, aby ciągi rozpoczynające się od `http` były zawsze sprawdzane za pomocą `parse_url`. Jeżeli parser zwróci nieznany format (`{"type": "unknown"}`), API natychmiastowo podnosi błąd `ValueError`.
  - Załatano lukę umożliwiającą przekazywanie tekstowych slugów do portali wymagających numerycznego ID (jak Otodom w procesie Discovery).
* Zmigrowano główną dokumentację systemową z `CLAUDE.md` na `GEMINI.md`.

## Wersja 1.0.0 — Kamień 08 (load_raw i has_local_raw w publicznym API) — 2026-06-06

* Dodano `load_raw(config, portal, portal_id) -> Optional[dict]` — opisowy alias `get_raw_data` z docstringiem dla klientów.
* Dodano `has_local_raw(config, portal, portal_id) -> bool` — lekkie sprawdzenie bool istnienia pliku bez wczytywania treści.
* Funkcja `has_local_raw` używa `StorageResolver` + `file_path.exists()` — brak I/O poza sprawdzeniem indeksu.
* 4 testy jednostkowe pokrywające oba nowe endpointy i przypadki brzegowe.

### Wnioski ze zmian
* Publiczne API `api.py` zyskuje spójną konwencję nazewnictwa: `has_*` do sprawdzania stanu lokalnego, `load_*` do odczytu, `extract_*` do transformacji — klienci mogą przewidywalnie nawigować po API bez zaglądania do kodu źródłowego.
* Oddzielenie lekkiego sprawdzenia (bool) od pełnego odczytu (dict) pozwala klientom minimalizować I/O w scenariuszach walidacji przed scrapowaniem.

## Wersja 0.9.9 — Kamień 07 (Publiczne API ekstrakcji danych dewelopera) — 2026-06-06

* Dodano `extract_developer_meta(raw_data, portal) -> dict` — publiczny punkt ekstrakcji unified danych dewelopera (id, slug, name).
* Funkcja deleguje do istniejącego silnika `transform_to_unified` + `portal_data_mapping.json`, eliminując ręczne parsowanie JSON po stronie klientów.
* Bezpieczna obsługa błędów: nieznany portal lub puste dane zwracają `{}`.
* Dodano import `transform_to_unified` do nagłówka `api.py`.
* 4 testy jednostkowe pokrywające portale `rp`, `otodom`, `tabelaofert` oraz przypadki brzegowe.

### Wnioski ze zmian
* Publiczne API `api.py` zyskuje warstwę semantycznych metod — klienci przestają zależeć od wewnętrznych szczegółów (`resolve_path`, struktura katalogów).
* Wiązanie nowej funkcjonalności z istniejącym mapping engine zamiast powielania kodu to wzór wart stosowania przy kolejnych metodach `extract_*`.

## Wersja 0.9.8 — Kamień 06 (Naprawa ścieżek obrazów) — 2026-06-04

* Dodano metodę `find_image_path` w `StorageResolver` (opartą na `rglob`), pozwalającą na dynamiczne lokalizowanie plików obrazów w drzewie katalogów.
* Zdefiniowano nowy, publiczny endpoint `resolve_image_path` w głównym module `api.py`.
* Zintegrowano proces wyszukiwania ze `StorageResolver`, aby zachować jedno źródło prawdy dla operacji dyskowych.
* Dodano testy jednostkowe weryfikujące poprawność zwracanych ścieżek w symulowanym środowisku `USIdata/USIdev`.

### Wnioski ze zmian
* Wzbogacenie instancji `StorageResolver` o mechanizmy wyszukiwania zwiększa spójność API odpowiedzialnego za operacje IO na systemie plików.
* Przeniesienie logiki rozwiązywania ścieżek na backend (do dedykowanego endpointu) odciąża klientów (np. `usi-tracker`) i wspiera lepszą separację odpowiedzialności.

## [Unreleased] - 2026-06-04
- **Dodano** in-memory indeks dla danych `USIdata` i `USIdev` (`StorageResolver`), skracający czas rozwiązywania ścieżek przez brak ciągłego skanowania systemu plików.
- **Usunięto** wymagany argument `target_dir` z funkcji pobierających i zapisujących dane (takich jak `download_raw`, `download_raw_dev`, `save_raw`).
- **Zmieniono** metody w `manager.py`, by w połączeniu ze `StorageResolver` automatycznie determinowały miejsca zapisu na dysku przy użyciu ID portalu i slugów.
- **Zmodyfikowano** zwracany typ dla głównego API pobierania - teraz zwraca strukturę ze zmapowanymi slugami oraz UID zapytania, pozwalając klientowi pozostać niezależnym od systemu operacyjnego i fizycznych ścieżek plików.
- **Dodano** dedykowane testy jednostkowe w `tests/test_storage.py` obejmujące logikę nowego indeksowania plików.
* **Dodano** nowe metody API `get_raw_data` i `get_raw_dev_data`, które z pomocą `StorageResolvera` wczytują odpowiednie pliki raw.json po ID, zwalniając tym samym klienta z konieczności znajomości docelowych ścieżek fizycznych w systemie plików.
* **Zmodyfikowano** logikę metody `process_batch` i reszty mechanizmów (I/O Isolation), by same budowały ścieżki do zdjęć oraz plików wykorzystując zdekodowane slug'i.
* **Poprawiono** architekturę z pełnym pokryciem testami jednostkowymi, realizując bezstanowe podejście wymiany danych za pomocą UID.
## [0.9.6] - 2026-06-04
- **Schema Alignment (USI Unified)**: Wyeliminowano konflikty nazewnictwa i formatowania danych pomiędzy wyjściem scraperów a ostatecznym schematem `usi_unified.schema.json`.
- **Bugfix (Listing Status)**: Zmieniono kolidujące pole `status` w mapowaniu Otodom na `listing_status`, upewniając się, że wartości "active"/"archive" nie naruszają struktury wewnętrznego cyklu życia rekordu USI.
- **Bugfix (Delivery Dates)**: Poprawiono funkcję transformującą `delivery_date_to_quarter`, wymuszając format kompatybilny ze schematem końcowym (`"Q kw. YYYY"` zamiast `"YYYYQ#"`).
- **Feature (Transaction Type)**: Rozszerzono `usi_unified.schema.json` o wcześniej pominięty, a obsługiwany przez scrapery wektor `"transaction_type"` z enumem `["sale", "rent"]`.
## [0.9.5] - 2026-06-04
- **Feature (Transformers)**: Wdrożono 3 nowe dedykowane transformatory: `delivery_date_to_quarter` (normalizujący różne formaty dat oddania do postaci "YYYYQ#"), `price_to_numeric` (wyciągający liczby zmiennoprzecinkowe z ciągów walutowych) oraz `transaction_status_parser` (wyliczający poprawny status np. rent/sale).
- **Refactoring (Thin-Adapters)**: Znacznie odciążono logikę adapterów w kliencie `usi-tracker`, przenosząc mapowania dat, cen i statusów bezpośrednio na barki silnika transformacji i nowej konfiguracji `portal_data_mapping.json`.
- **Mapping (JSON)**: Przypisano nowe transformatory do odpowiednich pól (`delivery_date`, `price_min`, `price_max`, `price_m2_min`, `price_m2_max`, `status`) w konfiguracjach dla portali RynekPierwotny, Otodom oraz TabelaOfert.
- **Architecture (ID-only Policy)**: Przebudowano rdzeń zarządzania danymi I/O (moduł `TechnicalDataManager`, `utils/io.py`, `utils/images.py` oraz `api.py`). Całkowicie wyeliminowano poleganie na nieprzewidywalnych `dev_slug` i `inv_slug` podczas zapisywania i czytania plików.
- **API Refactoring**: Zmieniono sygnatury kluczowych funkcji API (`process_batch`, `download_raw`) oraz zapisujących (np. `save_raw_data`), wymuszając wstrzykiwanie deterministycznych instancji `Path` (`target_dir`, `images_dir`) bezpośrednio przez kod klienta (usunięto zjawisko *Path-Drift*).
- **Scraper Alignment**: Dostosowano funkcje skrapujące (RP, Otodom, TO) do działania z nowymi, jawnymi ścieżkami katalogów.
## [0.9.4] - 2026-06-03
- **Feature/Compatibility**: Standardized identifier keys across all portals. Added `vendor_id` and `investment_slug` to `portal_data_mapping.json` schema and scraper outputs to eliminate the need for `if/elif` blocks in downstream clients.
- **Deprecation**: Maintained old keys (`developer_id`, `slug`, `agency_id`) in outputs for backwards compatibility, but marked them for future deprecation.

## [0.9.3] - 2026-06-03
- **Bugfix**: Corrected `ceiling_height_min` and `ceiling_height_max` configuration blocks in `portal_data_mapping.json` for RynekPierwotny. They are now correctly formatted as dictionaries (`{"path": "...", "transform": "cm_to_m"}`) rather than raw path strings, successfully restoring metric conversion for ceiling heights.

## [0.9.2] - 2026-06-03
- **Feature**: Implemented `transform_to_unified(portal_prefix, raw_data)` in `mapping.py` to directly return a fully resolved, unified dictionary representing the final data structure. This effectively shifts all JSON-to-Dict transformation burden completely away from the tracker/app layer, confirming `portal_data_mapping.json` as the exclusive source of truth.
- **Documentation**: Augmented `CLAUDE.md` and `README.md` to clarify how `portal_data_mapping.json` generates unified structures, addressing visibility and pipeline clarity concerns.

## [0.9.1] - 2026-06-03
- **Feature**: Added new dedicated transformers (`rp_extract_amenities`, `oto_extract_delivery`, `to_extract_amenities`) for fully declarative amenity and delivery date extraction.
- **Mapping**: Updated `portal_data_mapping.json` for all 3 portals to expose `amenities` and `delivery_date` using the new transformers, removing the need for manual loops in downstream apps.

## [0.9.0] - 2026-06-03
- **Architectural Overhaul**: Introduced the `transformers.py` module to parse, clean, and convert raw JSON data deterministically. Replaced hardcoded mapping paths with a declarative configuration format (`{"path": "...", "transform": "...", "unit": "..."}`).
- **Data Normalization**: Added transformers for ceiling heights (`cm_to_m`), date-to-quarter conversion, and advanced geospatial/address extractions across all 3 portals (`city`, `street`, `region`). Added an automatic deduplicating gallery flattener.
- **Segment Evaluation**: Implemented an `"evaluate_signals"` directive in the mapping engine, substituting the older flat `signals` structure. This enables virtual keys like `segment` (`apartments`, `houses`, `commercial`) and `transaction_type` (`rent`, `sale`) to compute dynamic aggregations out-of-the-box.
- **TabelaOfert Scraper**: Expanded `scraper_to.py` to also record `street` directly in `_extracted_location`.

## [0.8.6] - 2026-06-02
- **Feature**: Added discrete `latitude` and `longitude` mapping keys for all 3 portals to unify geospatial queries and eliminate array-unpacking complexity on the caller side.
- **Feature**: Extended `scraper_to.py` to extract `latitude` and `longitude` directly from TabelaOfert's hidden `/mapa` JSON API endpoint, appending the data to the raw JSON document under `_raw_mapa`.
- **Investigation Note**: Verified that Otodom does not provide explicit `segment` classification natively in structured data (relying only on unstructured descriptions and advertisement tags).
## [0.8.5] - 2026-06-02
- **Feature**: Added `save_raw_html` IO utility to save raw, cleaned HTML files for Time-Travel Scraping on TabelaOfert.
- **Feature**: `portal_data_mapping.json` now supports regex extraction directly from `raw_to_*.html` through the `_raw_html` key, which is dynamically injected during scraping.
- **Mapping Improvements**: Fixed and expanded extraction mapping paths for RynekPierwotny (`geo_point`, `gallery`), Otodom (`url`, `owner_name`, `hash_id`), and TabelaOfert (`ceiling_height_min/max` with alternative property name).
- **Data Cleanup**: Added `clean_to_html` to strip external scripts, inline styles, and SVGs, reducing HTML archive size while preserving crucial structured data blocks.
## [0.8.1] - 2026-05-24
- **Feature**: Added `list_available_keys` to mapping engine and public API to allow dynamic inspection of available schema fields.
- **Documentation**: Updated `API.md` with documentation for `list_available_keys`.

## [0.8.0] - 2026-05-24
- **Unified Geo Mapping**: Introduced `geo_point` key in `portal_data_mapping.json` for all portals to standardize geographic data access, while preserving legacy fields for backward compatibility.
- **Project Rationalization**: Moved integration tests from `scripts/` to `tests/`, removed obsolete `archive/` directory.
- **Documentation**: Updated `API.md` and `project-structure.md` with mapping methods and standardized logging usage.

## [0.7.9] - 2026-05-21

### Added
- **MAX-reuse Principle**: Established a mandate to prioritize existing functions and APIs over creating new logic, ensuring architectural consistency.
- **PURE-RAW Enforcement**: Guaranteed that `raw_*.json` files are "virgin" structural mirrors of portal responses. Removed all data injection, including `_usi_meta`.
- **Intelligent Developer Resolution**: Scrapers now automatically resolve and create missing developer records by fetching canonical profiles from portals when local ID-lookups fail.

### Changed
- **Unified Developer API**: Refactored all scrapers to use a standardized `download_raw_*_dev_json` flow for identity resolution, eliminating code duplication.
- **Fast Lookups**: Identity lookup functions now rely exclusively on ID-based filenames, aligning with the "ID-only" policy and improving performance.
- **Error Messaging**: Improved clarity of developer resolution error messages.
- **RP Mapping**: Fixed structural mapping for RynekPierwotny to ensure data consistency.

### Fixed
- **'unknown' Directory Viral Infection**: Fixed a bug where a single `unknown/` directory could "poison" multiple developers. The system now strictly rejects `unknown` as a valid slug and enforces Fail-fast resolution.

## [0.7.8] — 2026-05-23

### Fixed
- **Otodom Developer Resolution**: Implemented support for search-results style agency pages (e.g., `?sellerId=...`). The scraper now correctly extracts canonical slugs and logos from nested search result items.
- **Resilient Slugification**: Added a fallback to locally generate a slug from the agency name when canonical extraction fails, preventing resolution aborts while maintaining strict ID-based tracking.

## [0.6.0] — 2026-05-21

### Added
- **Public Mapping API**: Exposed `get_mapping`, `resolve_path`, and `load_mapping` in `usi_scrapers/__init__.py`.
- **Regex Mapping Support**: Enhanced `resolve_path` to process dictionary definitions containing `"path"` and `"regex"` keys.

### Changed
- **Portal Data Mapping**: Adjusted `portal_data_mapping.json` paths for TabelaOfert (fixed `to_url` to `url`) and RynekPierwotny (fixed `vendor.id` to `vendor.value.id` and updated `stats` paths).

## [0.5.8] — 2026-05-19

### Changed
- **Asset Naming Consistency**: Updated `download_developer_logo` and all scrapers to use portal IDs for logo filenames (`logo_{portal}_{id}.{ext}`), fully aligning with the ID-only identification principle.
- **Documentation**: Updated `canonical.md` to strictly follow `{id}` naming for all file types (raw JSON, meta JSON, archives, and logos) and clearly defined portal ID extraction rules.

## [0.5.7] — 2026-05-19

### Added
- **ID-Based Investment Identification**: Implemented `lookup_investment_by_id(public_dir, dev_slug, portal, portal_id)` to resolve investment directories using portal IDs instead of slugs.
- **Improved Scraper Stability**: All scrapers (Otodom, RynekPierwotny, TabelaOfert) now use portal-sourced IDs as primary keys to prevent directory duplication when marketing names change.

### Changed
- **File Naming Convention**: Raw data files for both developers and investments now follow the `raw_{portal}_{id}.json` pattern for faster lookups and better data integrity.
- **Optimized Lookups**: `lookup_developer_by_id` now performs a fast filename-based check before falling back to internal JSON metadata scanning.
- **Documentation**: Updated `canonical.md` to reflect the new ID-only identification architecture.

## [0.5.6] — 2026-05-19

### Fixed
- **Strict Developer Resolution**: Implemented a "fail-fast" mechanism across all scrapers (RynekPierwotny, Otodom, TabelaOfert) to prevent the creation of `unknown/` developer folders. 
- **API-Based Fallbacks**: If the initial investment JSON lacks vendor data, the system now proactively fetches the developer profile from the portal's internal API to resolve the authoritative slug (mirroring the robust logic from the Coda.io prototype).
- **Data Integrity**: Scrapers now return an explicit error and abort I/O operations if either the `developer_slug` or `investment_slug` cannot be structurally determined from API data.

## [0.5.5] — 2026-05-17

### Fixed
- **Otodom Scraper**: Added a safeguard to prevent processing inactive, archived, or removed listings. This protects local data and images from being overwritten by empty data when a listing is taken down on the portal.

## [0.5.4] — 2026-05-17

### Fixed
- **Logging**: Updated `__version__` in `usi_scrapers/__init__.py` to match the current release. Previously, logs were still showing `v0.4.8` despite package upgrades.

## [0.5.3] — 2026-05-17

### Fixed
- **Packaging**: Updated `pyproject.toml` to include `portals.json` and `schemas/*.json` in the distributed package. Previously, these data files were omitted by `pip install`, leading to `FileNotFoundError`.

## [0.5.2] — 2026-05-17

### Fixed
- Added missing `usi_scrapers/utils/portals.py` and `usi_scrapers/portals.json` to git tracking. These files were accidentally omitted in previous v0.5.x releases, causing `ModuleNotFoundError`.

## [0.5.1] — 2026-05-17

### Fixed
- **TabelaOfert Scraper**: Improved developer slug extraction to avoid matching city city/filter links (e.g. `wroclaw`, `warszawa`) in breadcrumbs/sidebars.
- **TabelaOfert Scraper**: Fixed developer logo extraction to exclude portal logo and correctly handle relative URLs.

## [0.5.0] — 2026-05-17

### Added
- `lookup_developer_by_id(public_dir, portal, portal_id)` — new lookup mechanism in `utils/io.py` that maps portal IDs to internal `developer_slug`.
- `tests/test_developer_lookup.py` — new tests verifying ID-based lookup across all three portals, including scenarios with changing URL slugs.

### Changed
- Refactored `scrape_otodom`, `scrape_rynek_pierwotny`, and `scrape_tabelaofert` to prioritize ID-based developer identification over URL-based slugs.
- System now strictly uses portal IDs (`agency_id`, `vendor_id`, etc.) as primary keys to maintain data consistency and prevent directory duplication.

## [0.4.8] — 2026-05-14

### Added
- Developer logo download as side-effect of `download_raw_dev()` for all three portals
- `extract_rp_dev_logo(profile)` — wyciąga URL logo z odpowiedzi API RP (pola: `logo`, `logo_url`, `image`)
- `extract_otodom_dev_logo(page_props)` — wyciąga URL logo z `__NEXT_DATA__` pageProps Otodom (szuka w `advertiser`, `agency`, shallow scan)
- `extract_to_dev_logo(html)` — wyciąga URL logo ze strony dewelopera TO (priorytet: `og:image`, fallback: `<img class/alt="logo">`)
- `extract_to_dev_data(html, url)` — dedykowana ekstrakcja danych ze strony dewelopera TO (zastąpiła błędne użycie `extract_to_data`)
- `download_developer_logo(url, dev_slug, config)` w `utils/images.py` — pobiera logo do `{public_dir}/USIdev/{dev_slug}/logo.{ext}`
- `tests/test_developer_logo.py` — 30 testów jednostkowych

### Fixed
- `download_raw_to_dev_json` wywoływał `extract_to_data()` (funkcję dla inwestycji, szuka JSON-LD `@type: Product`) na stronach deweloperów — zastąpione przez `extract_to_dev_data()`

## [0.4.7] — 2026-05-14

### Changed
- `ProgressCallback` type updated from `Callable[[int, int], None]` to `Callable[[Dict[str, Any]], None]` — dict keys: `total`, `current_index`, `progress_percent`, `status`, `investment`, `message`, `error_details`
- `fetch_many()` now passes a full progress dict to `on_progress` (previously only called with current/total ints)

### Fixed
- Removed unused dependencies: `pydantic`, `beautifulsoup4`, `python-slugify`
- Removed dead `here_api_key` field from `ScraperConfig`
- Removed dead `on_progress` parameter from `list_investments()`
- Added `logger.warning` in `resolve_rp_vendor_id()` when all vendor-ID patterns fail (was a silent `return None`)
- Added `logger.debug` in `extract_to_api_token()` when Next.js hash token not found in HTML
- Added `logger.debug` in `fetch_to_api_gallery()` when API returns no data
- Added `logger.warning` in `discover_otodom_listing()` when `items` is empty mid-pagination

### Tests
- Added `tests/conftest.py` with shared `config` and `fetcher` fixtures
- Added `tests/test_api.py` — 22 tests for `process_batch` and `fetch_investment`
- Added `tests/test_stage_detector.py` — 17 tests for all `stage_detector` functions
- Extended `tests/test_health_check.py` from 3 to 24 tests
- Rewrote `tests/test_scraper_rp.py`, `test_scraper_otodom.py`, `test_scraper_to.py` to match current API signatures

## [0.4.6] — 2026-05-11

### Changed
- All log messages now prefixed with `[usi-scrapers vX.Y.Z]` via `USILoggerAdapter`

## [0.4.5] — 2026-05-08

### Added
- Developer discovery and auto-download integrated into scrapers

## [0.4.4] — 2026-05-07

### Added
- `on_progress` callback to `fetch_investment`

## [0.4.3] — 2026-05-06

### Added
- `process_batch` with progress reporting, throttling and retry logic
