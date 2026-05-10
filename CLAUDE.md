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

6. **`api.py`** — Public interface for `usi-tracker`. All external calls go through here. Includes `health_check(config, fetcher, portals=None)` which smoke-tests discovery + scrape for all three portals and returns `{"ok": bool, "portals": {...}, "checked_at": ISO}`. Optional `portals` list limits which portals are tested. Includes `list_developers(config, fetcher, portal, page, base_url)` which returns one page of a portal's developer catalogue as a `DeveloperPage`.

## Config (`models.py` → `ScraperConfig`)

- `public_dir` — root output directory; `Public/` in the repo root is a **debug symlink** only
- `scraperapi_key` — ScraperAPI key; credit balance checked live, no local counter
- `here_api_key` — unused in this repo (geocoding is usi-tracker's responsibility)
- `rp/otodom/to_discovery_urls` — discovery endpoints per portal
- `fetch_delays` — per-domain rate limit in seconds

## Output structure

```
{public_dir}/USIdata/{dev_slug}/{inv_slug}/
    raw_rp_{inv_slug}.json      # RynekPierwotny raw (investment)
    raw_oto_{inv_slug}.json     # Otodom raw (investment)
    raw_to_{inv_slug}.json      # TabelaOfert raw (investment)

{public_dir}/USIdev/raw/
    raw_rp_{dev_slug}.json      # RynekPierwotny raw (developer profile)
    raw_oto_{dev_slug}.json     # Otodom raw (developer profile)
    raw_to_{dev_slug}.json      # TabelaOfert raw (developer profile)

{public_dir}/USI/{dev_slug}/{inv_slug}/
    *.webp / *.jpg              # downloaded images
```

Existing raw files are archived with a timestamp suffix before being overwritten (`raw_rp_{slug}_20250511_120000.json`).

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
# → {public_dir}/USIdata/{dev_slug}/raw_rp_{dev_slug}.json
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
    dev_slug="unidevelopment",
    inv_slug="idea-ogrody-3-...",
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

### 6. Smoke-test all portals (health check)

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

# 2. Save developer profile to disk
download_raw_dev(config, fetcher, "rp", "unidevelopment", "unidevelopment")

# 3. Scrape each investment
for inv in investments:
    data = fetch_investment(config, fetcher, "rp", inv["id"], "unidevelopment", inv["slug"])
    # ... persist to database
```

### What is NOT in this package

Developer profile parsing (logo, description, contact) beyond raw JSON is not implemented — only `identify_developer` extracts the name. Full developer profile structuring is usi-tracker's responsibility.

## Key conventions

- **Type hints** required on all public functions.
- **Logging**: `logger = logging.getLogger(__name__)` per module.
- `stage_detector.py` (157 lines) is intentionally duplicated in `usi-tracker` — both copies are kept in sync manually.
- Otodom investment URLs use `/pl/oferta/{slug}` (not `/pl/inwestycja/`) — confirmed against 2300+ production records.
- RP API returns coordinates as `[lng, lat]` — index 0 is longitude, index 1 is latitude.
- RP page_size max is 30 (despite older docs saying 100).
- Discovery functions share the signature `discover_*(config, fetcher, identifier=None, limit=None)`; `identifier=None` triggers a global scan using `config.*_discovery_urls`.
- `discover_*_developers(fetcher, page, base_url)` functions do **not** take `config` — they don't write files.
- When bumping version: update both `pyproject.toml` and `usi_scrapers/__init__.py`, then create a matching git tag (`git tag vX.Y.Z && git push origin vX.Y.Z`).

## Additional utilities

- **`utils/url_parser.py`** — `parse_url(url)` parses RynekPierwotny, Otodom, and TabelaOfert URLs and returns a dict with `type`, `kind`, and the relevant identifiers (e.g. `developer_slug`, `agency_id`, `to_id`). Use this to extract the `identifier` value needed for API calls from a raw portal URL.
- **`utils/string.py`** — custom `slugify()` with explicit Polish character transliteration. Prefer this over the `python-slugify` dependency when generating internal slugs; `clean_filename()` in `utils/images.py` strips CDN cache-buster suffixes.
- **`schemas/`** — JSON Schema files (`usi_unified.schema.json`, `rp_details.schema.json`, etc.) for validating scraped payloads. Used for cross-checking, not enforced at runtime.
- **`ProgressCallback`** — `from usi_scrapers.models import ProgressCallback`; a `Callable[[int, int], None]` that receives `(current, total)`. Supported by discovery and scrape functions as an optional `progress_cb` kwarg.
