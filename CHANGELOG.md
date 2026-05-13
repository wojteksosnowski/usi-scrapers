# Changelog

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
