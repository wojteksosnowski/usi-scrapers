# USI Scrapers

Pakiet do pobierania surowych danych z polskich portali nieruchomości: **RynekPierwotny**, **Otodom**, **TabelaOfert**. Zapis na dysk w konwencji slug-based. Transformacja i normalizacja danych odbywa się w aplikacji importującej (`usi-tracker`).

## Instalacja

```bash
pip install -e .
# z zależnościami deweloperskimi
pip install -e ".[dev]"
```

## Publiczne API (`usi_scrapers/api.py`)

### Discovery

```python
from usi_scrapers.api import list_investments
from usi_scrapers.models import ProgressCallback

investments = list_investments(config, fetcher, portal="rp")
investments = list_investments(config, fetcher, portal="otodom", identifier="12345")

# ze śledzeniem postępu (przydatne przy globalnym discovery Otodom)
def on_progress(current: int, total: int) -> None:
    print(f"[{current}/{total}]")

investments = list_investments(config, fetcher, portal="otodom", on_progress=on_progress)
```

### Scraping pojedynczej inwestycji

```python
from usi_scrapers.api import fetch_investment

data = fetch_investment(config, fetcher, portal="rp", identifier="123", dev_slug="deweloper", inv_slug="inwestycja")
```

### Scraping wsadowy z callbackiem postępu

```python
from usi_scrapers.api import fetch_many

investments = [
    {"identifier": "123", "dev_slug": "deweloper-a", "inv_slug": "inwestycja-1"},
    {"identifier": "456", "dev_slug": "deweloper-b", "inv_slug": "inwestycja-2"},
]

results = fetch_many(config, fetcher, portal="rp", investments=investments, on_progress=on_progress)
```

`ProgressCallback = Callable[[int, int], None]` — argumenty: `(current, total)`.

### Pozostałe funkcje

| Funkcja | Opis |
|---|---|
| `download_raw(...)` | Pobiera i zapisuje surowy JSON inwestycji |
| `download_raw_dev(...)` | Pobiera i zapisuje surowy JSON profilu dewelopera |
| `save_raw(...)` | Zapisuje gotowy słownik jako surowy JSON |
| `save_raw_developer(...)` | Zapisuje gotowy słownik jako surowy JSON dewelopera |
| `identify_developer(...)` | Identyfikuje nazwę dewelopera na podstawie URL |

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
