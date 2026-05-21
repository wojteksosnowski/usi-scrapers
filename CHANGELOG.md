# Changelog

## [0.7.0] — 2026-05-21

### Added
- **MAX-reuse Principle**: Established a mandate to prioritize existing functions and APIs over creating new logic, ensuring architectural consistency.
- **PURE-RAW Enforcement**: Guaranteed that `raw_*.json` files are "virgin" structural mirrors of portal responses. Removed all data injection, including `_usi_meta`.
- **Intelligent Developer Resolution**: Scrapers now automatically resolve and create missing developer records by fetching canonical profiles from portals when local ID-lookups fail.

### Changed
- **Unified Developer API**: Refactored all scrapers to use a standardized `download_raw_*_dev_json` flow for identity resolution, eliminating code duplication.
- **Fast Lookups**: Identity lookup functions now rely exclusively on ID-based filenames, aligning with the "ID-only" policy and improving performance.

### Fixed
- **'unknown' Directory Viral Infection**: Fixed a bug where a single `unknown/` directory could "poison" multiple developers. The system now strictly rejects `unknown` as a valid slug and enforces Fail-fast resolution.

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
