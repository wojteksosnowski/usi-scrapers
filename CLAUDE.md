# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Create and activate venv (required — Public/ symlink confuses global pip)
python3.13 -m venv venv
source venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
venv/bin/pytest

# Run a single test file or test
venv/bin/pytest tests/test_scraper_otodom.py
venv/bin/pytest tests/test_scraper_rp.py::test_parse_rp_results_stage_flattening
```

## Purpose

This repo is **fetch-only**: it downloads raw JSON and images from three Polish real estate portals and saves them to disk using a strict slug-based directory convention. All transformation, merging, and schema normalization happens in the importing application (`usi-tracker`). Do not add adapter or processing logic here.

## Architecture

Pipeline: **Fetch → Scrape → Save**

1. **`fetcher.py`** — All HTTP goes through `Fetcher`. Uses `curl_cffi` Chrome impersonation to bypass bot detection; falls back to ScraperAPI when blocked (checks live credit balance via `GET api.scraperapi.com/account` — no local counter). Per-domain rate limiting via `config.fetch_delays`.

2. **`scraper_rp.py`** — RynekPierwotny via REST API v2. Key detail: RP groups investment stages under one parent; `_parse_rp_results()` flattens them into individual offers. `utils/stage_detector.py` extracts sibling stage metadata from the `groups.stages` structure.

3. **`scraper_otodom.py`** — Otodom via `__NEXT_DATA__` JSON embedded in HTML (`props.pageProps.ad`). Each stage is a separate offer on Otodom — no flattening needed. Helper `_parse_otodom_item()` normalises slug/image/agency extraction shared by both discovery functions.

4. **`scraper_to.py`** — TabelaOfert via HTML + JSON-LD (`@type: Product`). Gallery uses a hidden Next.js API (`/api/{token}/oferty/inwestycja/{id}/galeria`) with token extracted from script hashes; falls back to HTML regex. `filter_investment_images()` deduplicates by scale and removes maps/logos.

5. **`manager.py` + `utils/`** — `utils/io.py` resolves all save paths; `utils/images.py` downloads images. Always use `clean_filename()` — it strips CDN parameters, cache-busters (`_e94b5737`), and normalises extensions.

6. **`api.py`** — Public interface for `usi-tracker`. All external calls go through here.

## Config (`models.py` → `ScraperConfig`)

- `public_dir` — root output directory; `Public/` in the repo root is a **debug symlink** only
- `scraperapi_key` — ScraperAPI key; credit balance checked live, no local counter
- `here_api_key` — unused in this repo (geocoding is usi-tracker's responsibility)
- `rp/otodom/to_discovery_urls` — discovery endpoints per portal
- `fetch_delays` — per-domain rate limit in seconds

## Output structure

```
{public_dir}/USIdata/{dev_slug}/{inv_slug}/
    raw_rp_{inv_slug}.json      # RynekPierwotny raw
    raw_oto_{inv_slug}.json     # Otodom raw
    raw_to_{inv_slug}.json      # TabelaOfert raw

{public_dir}/USI/{dev_slug}/{inv_slug}/
    *.webp / *.jpg              # downloaded images
```

## Key conventions

- **Type hints** required on all public functions.
- **Logging**: `logger = logging.getLogger(__name__)` per module.
- `stage_detector.py` (157 lines) is intentionally duplicated in `usi-tracker` — both copies are kept in sync manually.
- Otodom investment URLs use `/pl/oferta/{slug}` (not `/pl/inwestycja/`) — confirmed against 2300+ production records.
- RP API returns coordinates as `[lng, lat]` — index 0 is longitude, index 1 is latitude.
- RP page_size max is 30 (despite older docs saying 100).
- When bumping version: update both `pyproject.toml` and `usi_scrapers/__init__.py`, then create a matching git tag (`git tag vX.Y.Z && git push origin vX.Y.Z`).
