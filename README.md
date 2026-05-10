# USI Scrapers

Pakiet do pobierania surowych danych z polskich portali nieruchomości: **RynekPierwotny**, **Otodom**, **TabelaOfert**. Zapis na dysk w konwencji slug-based. Transformacja i normalizacja danych odbywa się w aplikacji importującej (`usi-tracker`).

## Instalacja

```bash
pip install -e .
# z zależnościami deweloperskimi
pip install -e ".[dev]"
```

## Publiczne API (`usi_scrapers/api.py`)

Pełna dokumentacja API dostępna jest w pliku [docs/API.md](usi_scrapers/docs/API.md).

### Health Check & Monitoring

```python
from usi_scrapers.api import health_check

# Szybki smoke-test wszystkich portali
results = health_check()
print(results["ok"]) # True jeśli wszystko działa
```

### Discovery

```python
from usi_scrapers.api import list_investments
from usi_scrapers.models import ProgressCallback

# Globalne discovery (używa linków z konfiguracji)
investments = list_investments(config, fetcher, portal="otodom")

# Discovery dla konkretnego dewelopera
investments = list_investments(config, fetcher, portal="rp", identifier="dom-development-sa-955")
```

### Scraping pojedynczej inwestycji

```python
from usi_scrapers.api import fetch_investment

data = fetch_investment(config, fetcher, portal="rp", identifier="123", dev_slug="deweloper", inv_slug="inwestycja")
```

## Struktura wyjściowa

```
{public_dir}/USIdata/{dev_slug}/{inv_slug}/
    raw_rp_{inv_slug}.json
    raw_oto_{inv_slug}.json
    raw_to_{inv_slug}.json

{public_dir}/USI/{dev_slug}/{inv_slug}/
    *.webp / *.jpg
```

## Testy

```bash
venv/bin/pytest
venv/bin/pytest tests/test_scraper_otodom.py
```
