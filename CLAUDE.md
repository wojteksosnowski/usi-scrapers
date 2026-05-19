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

4. **`scraper_to.py`** — TabelaOfert via HTML + JSON-LD (`@type: Product`). Gallery uses a hidden Next.js API (`/api/{token}/oferty/inwestycja/{id}/galeria`) with token extracted from script hashes; falls back to HTML regex. `filter_investment_images()` deduplicates by scale and removes maps/logos. **Important:** `extract_to_data()` is for investment pages (looks for JSON-LD `Product`); developer pages use `extract_to_dev_data()` (looks for `Organization`/`LocalBusiness`) — do not mix them.

5. **`manager.py` + `utils/`** — `utils/io.py` resolves all save paths; `utils/images.py` downloads images. Always use `clean_filename()` — it strips CDN parameters, cache-busters (`_e94b5737`), and normalises extensions.

6. **`portals.json` + `utils/portals.py`** — Single source of truth for all portal constants (base URLs, API endpoint templates, URL patterns, rate limits, health-check probe targets, required fields). Never hardcode portal URLs or IDs in scraper code; use `portal_api_url()`, `portal_url()`, `get_portal()`, or `resolve_prefix()` from `utils/portals.py` instead.

7. **`api.py`** — Public interface for `usi-tracker`. All external calls go through here. Includes `health_check(config, fetcher, portals=None)` which smoke-tests discovery + scrape for all three portals and returns `{"ok": bool, "portals": {...}, "checked_at": ISO}`. Optional `portals` list limits which portals are tested. Includes `list_developers(config, fetcher, portal, page, base_url)` which returns one page of a portal's developer catalogue as a `DeveloperPage`.

## Config (`models.py` → `ScraperConfig`)

- `public_dir` — root output directory; `Public/` in the repo root is a **debug symlink** only
- `scraperapi_key` — ScraperAPI key; credit balance checked live, no local counter
- `rp/otodom/to_discovery_urls` — discovery endpoints per portal
- `fetch_delays` — per-domain rate limit in seconds; default values are read from `portals.json` via `utils/portals.py:default_fetch_delays()`

## Output files — types, naming and creation

### 1. Raw investment JSON

**Path:** `{public_dir}/USIdata/{dev_slug}/{inv_slug}/raw_{portal}_{portal_id}.json`

When `portal_id` is unavailable, falls back to `raw_{portal}_{inv_slug}.json`.

| Portal | `portal_id` format | Example filename |
|---|---|---|
| `rp` | numeric offer ID | `raw_rp_1234.json` |
| `oto` | `ID` + URL hash | `raw_oto_ID4lulo.json` |
| `to` | `i` + numeric TO id | `raw_to_i8982461.json` |

**Content:** full, unprocessed portal response — RP API JSON, Otodom `pageProps`, or TabelaOfert JSON-LD + extracted fields. No normalization.

**Created by:** `save_raw_json()` in `utils/io.py`, called from:
- `api.download_raw()` → per-portal `download_raw_*_json()`
- `TechnicalDataManager.save_raw_data()` inside `process_batch()` (immediately after each successful scrape — I/O isolation)

**Overwrite behaviour:** existing file is renamed to `raw_{portal}_{inv_slug}_{YYYYMMDD_HHMMSS}.json` in the same directory before the new file is written. The `_usi_meta` block inside each file records `portal`, `portal_url`, `portal_id`, `source_url`, and `saved_at`.

---

### 2. Raw developer JSON

**Path:** `{public_dir}/USIdev/{dev_slug}/raw_{portal}_{portal_id}.json`

When `portal_id` is unavailable, falls back to `raw_{portal}_{dev_slug}.json`.

**Content:** full developer profile from the portal — RP vendor API response, Otodom developer page `pageProps`, or TabelaOfert developer page data (JSON-LD `Organization`/`LocalBusiness` + `<h1>`).

**Created by:** `save_dev_raw_json()` in `utils/io.py`, called from `api.download_raw_dev()` → per-portal `download_raw_*_dev_json()`.

**Overwrite behaviour:** same timestamp-rename archiving as raw investment JSON (using `portal_id` if available).

> **TO note:** TabelaOfert developer pages do **not** contain JSON-LD `Product` data. `extract_to_dev_data()` is used (not `extract_to_data()`) — they are not interchangeable.

---

### 3. Developer logo

**Path:** `{public_dir}/USIdev/{dev_slug}/logo_{portal}_{portal_id}.{ext}`

When `portal_id` is unavailable, falls back to `logo_{portal}_{dev_slug}.{ext}`.

Example: `USIdev/unidevelopment/logo_rp_955.png`

**Extension:** taken from the URL path (`.jpg`, `.png`, `.webp`); falls back to `.jpg` if unrecognised.

**Created by:** `download_developer_logo()` in `utils/images.py`, called as a side-effect inside `download_raw_*_dev_json()` when a logo URL is found. No logo file is created if the portal returns no logo URL.

**Logo extraction per portal:**
- **RP** — `extract_rp_dev_logo()`: checks fields `logo`, `logo_url`, `image` (string or `{"url": ...}`)
- **Otodom** — `extract_otodom_dev_logo()`: checks `advertiser.logoUrl`, `agency.logo.url`, `agency.logoUrl`; falls back to shallow key scan for any `*logo*` field
- **TO** — `extract_to_dev_logo()`: priority `og:image` meta tag, fallback `<img class/alt="logo">`

**Skip condition:** if the file already exists and is larger than 1 KB, it is not re-downloaded.

---

### 4. Investment images

**Path:** `{public_dir}/USI/{dev_slug}/{inv_slug}/{filename}`

**Created by:** `save_images()` / `download_image()` in `utils/images.py`, called via `TechnicalDataManager.sync_images()` inside `process_batch()`.

**Filename derivation — `clean_filename(url)`:**

| Source | Pattern | Result |
|---|---|---|
| Otodom CDN | `.../files/{hash}/image;s=800x600` | `{hash}.jpg` |
| TabelaOfert CDN | `.../ID-photo-name.jpg` | `photo-name.jpg` |
| RP / other | standard URL basename | basename, with `_[a-f0-9]{8}` cache-buster suffix stripped |

**Skip condition:** file already exists and is larger than 1 KB.

---

### 5. Stage stub (`usi_stage_stub.json`)

**Path:** `{data_dir}/{dev_slug}/{stage_slug}/usi_stage_stub.json`  
(`data_dir` is passed by the calling application, typically `{public_dir}/USIdata/`)

**Content:** minimal placeholder for a sibling RP multi-stage investment not yet scraped. Fields: `source`, `status: "stub"`, `groups_id`, `groups_name`, `stage_id`, `stage_sort`, `offer_id`, `slug`, `url`, `developer_slug`, `investment_slug`, `sibling_stage_folders`, `created_at`.

**Created by:** `run_stage_detection()` in `utils/stage_detector.py` — called by usi-tracker, not by this package's public API. Only created when: (a) an existing `app_result_*.json` has RP multi-stage data, and (b) the sibling directory has no `app_result_*.json` yet.

---

### 6. `usi_{inv_slug}.json` (reference only)

`TechnicalDataManager.get_usi_json_path()` returns the path `{public_dir}/USIdata/{dev_slug}/{inv_slug}/usi_{inv_slug}.json`. This file is **written by usi-tracker**, not by usi-scrapers — it is the final normalised and merged investment record. This package only resolves its path.

## api.py — how usi-tracker calls this package

All calls go through `api.py`. Never import scraper modules directly.

### Developer identifier formats per portal

| Portal | `identifier` format | Example |
|--------|--------------------|---------| 
| `rp` | vendor slug or numeric ID | `"unidevelopment-955"` or `"955"` |
| `otodom` | agency numeric ID | `"10556359"` |
| `tabelaofert` | developer slug | `"unidevelopment"` |

### 1. List investments for a developer (Discovery)

```python
from usi_scrapers.api import list_investments

investments = list_investments(
    config=config,
    fetcher=fetcher,
    portal="rp",                  # "rp" | "otodom" | "tabelaofert"
    identifier="unidevelopment",  # developer slug/ID; None = global scan of config URLs
)
# → list[dict]: id, url, slug, name, image, developer
```

### 2. Save developer raw JSON to disk

```python
from usi_scrapers.api import download_raw_dev

path = download_raw_dev(
    config=config,
    fetcher=fetcher,
    portal="rp",
    identifier="unidevelopment",  # developer slug/ID
    dev_slug="unidevelopment",
)
# → {public_dir}/USIdev/raw/raw_rp_{dev_slug}.json
# → also downloads logo to {public_dir}/USIdev/{dev_slug}/logo.{ext} when found
# → returns Path | None
```

### 3. Scrape one investment (full details)

```python
from usi_scrapers.api import fetch_investment

data = fetch_investment(
    config=config,
    fetcher=fetcher,
    portal="tabelaofert",
    identifier="https://tabelaofert.pl/inwestycja/...,i8982461",  # full investment URL
)
# → dict: name/title, latitude, longitude, price_min/max, image_urls, amenities, ...
```

**Note:** for `rp`, pass `inv["id"]` (numeric string) as `identifier`, not the URL.

### 4. Identify developer name from an investment URL

```python
from usi_scrapers.api import identify_developer

name = identify_developer(fetcher=fetcher, portal="otodom", url="https://...")
# → "Unidevelopment S.A." | None
# Works for otodom and tabelaofert. Returns None for rp.
```

### 5. List developers from portal catalogue (one page at a time)

```python
from usi_scrapers.api import list_developers

page = list_developers(
    config=config,
    fetcher=fetcher,
    portal="rp",   # "rp" | "otodom" | "tabelaofert"
    page=1,        # 1-based page number
    base_url=None, # override default listing URL
)
# → DeveloperPage(developers=[{url, name, slug}, ...], total_pages=int, page=int)
#
# Caller iterates: for p in range(1, page.total_pages + 1): list_developers(..., page=p)
```

**Developer page URL formats (verified against live portals, 2026-05-11):**

| Portal | URL format | Example |
|--------|-----------|---------|
| `rp` | `https://rynekpierwotny.pl/deweloperzy/{slug}/` | `…/atal-sa-1084/` |
| `otodom` | `https://www.otodom.pl/pl/firmy/deweloperzy/{slug}-ID{id}` | `…/atal-ID10554231` |
| `tabelaofert` | `https://tabelaofert.pl/katalog-firm/deweloperzy/{slug}` | `…/atal` |

**Implementation notes (gotchas):**
- **RP** — uses REST API `GET /api/v2/vendors/vendor/?s=vendor-list&page={n}&page_size=30`; HTML fallback not needed in practice. `total_pages = ceil(count / 30)`.
- **Otodom** — `/firmy/deweloperzy/` is a **legacy PHP page** (no `__NEXT_DATA__`). Must parse HTML with regex. Developer links are absolute `https://www.otodom.pl/pl/firmy/deweloperzy/{slug}-ID{id}`; `total_pages` comes from `?page=N` links in paginator. Verified: 230 pages, ~20 developers per page.
- **TabelaOfert** — developer links in listing HTML are **absolute URLs** (`https://tabelaofert.pl/katalog-firm/deweloperzy/{slug}`); city/filter links are **relative** (`/katalog-firm/deweloperzy/wroclaw`) — regex must match absolute form only to avoid including city filters. `total_pages` from `?page=N` paginator links. Verified: 117 pages, ~20 developers per page.

### 6. Batch-scrape multiple investments

```python
from usi_scrapers.api import process_batch

results = process_batch(
    config=config,
    fetcher=fetcher,
    portal="rp",                          # "rp" | "otodom" | "tabelaofert"
    identifiers=["12345", "67890"],       # list of investment identifiers
    on_progress=lambda payload: ...,      # optional; receives rich dict per item
    delay_range=(0.5, 2.0),              # throttle between requests
    max_retries=3,
)
# → list[dict]: one entry per identifier; includes "error" key on failure
# Writes raw JSON + images to disk immediately after each item (I/O isolation).
# Auto-retries on HTTP 429 / timeout with 10s backoff.
```

The `on_progress` payload keys: `total`, `current_index`, `progress_percent`, `status` (`"success"` | `"failed"` | `"retrying"`), `investment`, `message`, `error_details`.

### 7. Smoke-test all portals (health check)

```python
from usi_scrapers.api import health_check

result = health_check(config, fetcher)
# result["ok"]  → True if all portals returned valid data
# result["portals"]["rp"]["ok"]  → per-portal status
# result["portals"]["rp"]["error"]  → error message or None
# result["checked_at"]  → ISO timestamp
#
# Optional: health_check(config, fetcher, portals=["rp", "otodom"])
# No-arg form auto-inits config with public_dir=/tmp (useful in CI/monitoring):
result = health_check()
```

### Typical usi-tracker flow — developer catalogue scan

```python
from usi_scrapers.api import list_developers

# Iterate all pages of a portal's developer catalogue
first = list_developers(config, fetcher, "rp", page=1)
for p in range(1, first.total_pages + 1):
    page = list_developers(config, fetcher, "rp", page=p)
    for dev in page.developers:
        # dev["url"]  → canonical developer page URL
        # dev["slug"] → identifier for list_investments()
        # dev["name"] → developer name (None for tabelaofert)
        investments = list_investments(config, fetcher, "rp", dev["slug"])
```

### Typical usi-tracker flow — investment scrape

```python
# 1. Discover investments
investments = list_investments(config, fetcher, "rp", "unidevelopment")

# 2. Save developer profile + logo to disk
download_raw_dev(config, fetcher, "rp", "unidevelopment", "unidevelopment")

# 3. Scrape each investment
for inv in investments:
    data = fetch_investment(config, fetcher, "rp", inv["id"])
    # ... persist to database
```

### Ad-hoc dev scripts (not part of the public API)

`usi_scrapers/` contains several loose scripts that are **not** part of the package API and are not run by pytest: `test_fetch.py`, `test_health.py`, `mock_to_test.py`, `re_download_images.py`, `verify_images.py`. These are one-off diagnostic tools; treat them as scratch files, not production code.

### What is NOT in this package

Developer profile parsing (description, contact) beyond raw JSON and logo is not implemented — only `identify_developer` extracts the name. Full developer profile structuring is usi-tracker's responsibility.

## Key conventions

- **Type hints** required on all public functions.
- **Logging**: `from . import get_logger` then `logger = get_logger(__name__)` per module — this wraps the standard logger with `USILoggerAdapter` to prepend `[usi-scrapers vX.Y.Z]` to every message. Do not use `logging.getLogger` directly.
- `stage_detector.py` (157 lines) is intentionally duplicated in `usi-tracker` — both copies are kept in sync manually.
- Otodom investment URLs use `/pl/oferta/{slug}` (not `/pl/inwestycja/`) — confirmed against 2300+ production records.
- RP API returns coordinates as `[lng, lat]` — index 0 is longitude, index 1 is latitude.
- RP page_size max is 30 (despite older docs saying 100).
- Discovery functions share the signature `discover_*(config, fetcher, identifier=None, limit=None)`; `identifier=None` triggers a global scan using `config.*_discovery_urls`.
- `discover_*_developers(fetcher, page, base_url)` functions do **not** take `config` — they don't write files.
- When bumping version: update both `pyproject.toml` and `usi_scrapers/__init__.py`, then create a matching git tag (`git tag vX.Y.Z && git push origin vX.Y.Z`).

## Additional utilities

- **`portals.json`** — Declarative config for all three portals. Keys per entry: `name`, `prefix`, `aliases`, `base_url`, `rate_limit_domain`, `default_rate_limit`, `api` (endpoint path templates), `url_patterns` (investment/developer/stage URL templates), `developer_list_url`, `health_check` (probe target), `required_fields`.
- **`utils/portals.py`** — Loader for `portals.json`. Key functions: `resolve_prefix(alias)` (`"otodom" → "oto"`), `get_portal(prefix)` (full config dict), `portal_base_url(prefix)`, `portal_api_url(prefix, endpoint, **kwargs)` (e.g. `portal_api_url("rp", "offer_detail", offer_id="123")`), `portal_url(prefix, pattern, **kwargs)` (e.g. `portal_url("rp", "investment", dev_slug=..., inv_slug=..., offer_id=...)`), `all_prefixes()`, `default_fetch_delays()`.
- **`utils/url_parser.py`** — `parse_url(url)` parses RynekPierwotny, Otodom, and TabelaOfert URLs and returns a dict with `type`, `kind`, and the relevant identifiers (e.g. `developer_slug`, `agency_id`, `to_id`). Use this to extract the `identifier` value needed for API calls from a raw portal URL.
- **`utils/string.py`** — custom `slugify()` with explicit Polish character transliteration. Prefer this over the `python-slugify` dependency when generating internal slugs; `clean_filename()` in `utils/images.py` strips CDN cache-buster suffixes.
- **`schemas/`** — JSON Schema files (`usi_unified.schema.json`, `rp_details.schema.json`, etc.) for validating scraped payloads. Used for cross-checking, not enforced at runtime.
- **`ProgressCallback`** — `from usi_scrapers.models import ProgressCallback`; a `Callable[[Dict[str, Any]], None]`. Payload keys: `total`, `current_index`, `progress_percent`, `status` (`"success"` | `"failed"` | `"retrying"`), `investment`, `message`, `error_details`. Used by `process_batch` and `fetch_investment`.
