# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run tests for a specific portal or module
pytest tests/test_scraper_otodom.py
pytest tests/test_adapters.py
```

## Architecture

The system implements a strict **Fetch → Scrape → Adapt → Merge** pipeline for scraping Polish real estate portals (RynekPierwotny, Otodom, TabelaOfert) and unifying the data into the USI (Unified Schema for Investments) format.

### Layer overview

1. **`fetcher.py`** — Centralized HTTP layer. Uses `curl_cffi` for browser impersonation (Chrome JA3 fingerprinting to bypass bot detection), with ScraperAPI as a fallback. Handles per-domain rate limiting and usage tracking via a JSON stats file. All scrapers receive a `Fetcher` instance; never make raw HTTP calls elsewhere.

2. **`scraper_*.py`** — One file per portal. Each implements:
   - `discover_*_investments()` — list investments for a developer
   - `scrape_*()` — fetch full details for one investment
   - `download_raw_*_json()` — save raw portal JSON to disk
   - `fetch_*_agency_name()` — identify developer from URL

3. **`adapters/`** — Transform raw portal JSON → unified USI schema. Each portal has its own adapter (`rp.py`, `otodom.py`, `to.py`) extending `BaseAdapter`. `AdapterFactory` selects the right adapter at runtime. `merger.py` merges data from multiple portals with priority order **RP > Otodom > TabelaOfert**, filling missing fields from secondary sources and maintaining an audit trail.

4. **`manager.py` + `utils/`** — File I/O orchestration. `utils/io.py` handles path resolution; `utils/images.py` handles image downloading and filename normalization. Always use `clean_filename()` when writing images to avoid duplicate cached files.

5. **`api.py`** — Public interface consumed by the parent `usi-tracker` project. All external callers go through `api.py` functions.

### Config

All scraper behaviour is driven by `ScraperConfig` (see `models.py`):
- `public_dir` — root output directory (e.g. `/Volumes/Public`)
- `scraperapi_key` / `scraperapi_limit` — ScraperAPI credentials and monthly cap
- `here_api_key` — HERE Maps key for geocoding
- `rp/otodom/to_discovery_urls` — discovery endpoints per portal
- `fetch_delays` — per-domain rate limit delays

### Output structure

```
{public_dir}/USI/{dev_slug}/{inv_slug}/
    usi_{inv_slug}.json         # merged unified output
    raw_rp_{inv_slug}.json      # RynekPierwotny raw
    raw_oto_{inv_slug}.json     # Otodom raw
    raw_to_{inv_slug}.json      # TabelaOfert raw
    *.webp / *.jpg              # downloaded images
```

## Key conventions

- **Type hints** are required on all public functions.
- **Logging**: use `logger = logging.getLogger(__name__)` per module; never use `print`.
- **Surgical updates**: when changing scraper parsing logic, always trace the impact through to adapters and run regression tests. Adapter changes must not alter USI output for existing raw data snapshots.
- **ScraperConfig** is the single source for all API keys and configuration — never hardcode them.
- The `stage_detector.py` utility (`utils/`) is unusually large (~5300 lines); it handles Polish-language delivery quarter/year detection from free-text fields.
