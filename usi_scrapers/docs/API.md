# API Reference - USI Scrapers

Ten dokument zawiera szczegółowy opis publicznych metod dostępnych w pakiecie `usi-scrapers`.

## Główny moduł API (`usi_scrapers.api`)

### `health_check`
Wykonuje test sprawdzający (smoke-test) poprawność działania discovery i scrapingu dla wybranych portali.

```python
from usi_scrapers.api import health_check

# Automatyczna inicjalizacja (używa /tmp jako public_dir)
result = health_check()

# Z podaną konfiguracją
result = health_check(config, fetcher, portals=["rp", "otodom"])
```

**Argumenty:**
- `config` (*Optional[ScraperConfig]*): Obiekt konfiguracji. Jeśli `None`, zostanie stworzony domyślny.
- `fetcher` (*Optional[Fetcher]*): Instancja fetchera. Jeśli `None`, zostanie stworzona nowa.
- `portals` (*Optional[List[str]]*): Lista portali do sprawdzenia (np. `["rp", "otodom", "tabelaofert"]`).

**Zwraca:** `Dict[str, Any]` zawierający status `ok` oraz szczegółowe wyniki dla każdego portalu.

---

### `verify_consistency` (Alias)
**@deprecated:** Alias dla `health_check`. Zachowany dla wstecznej kompatybilności. Emituje `DeprecationWarning`.

---

### `list_investments` (Discovery)
Pobiera listę inwestycji (nazwa, slug, ID, URL) z danego portalu.

```python
from usi_scrapers.api import list_investments

# Globalne discovery (używa linków z config)
investments = list_investments(config, fetcher, portal="otodom")

# Discovery dla konkretnego dewelopera
investments = list_investments(config, fetcher, portal="rp", identifier="dom-development-sa-955")
```

**Obsługa portali:**
- **RP**: `identifier` to slug lub ID dewelopera. Jeśli `None`, skanuje globalnie.
- **Otodom**: `identifier` to ID agencyjne (np. "12345") lub URL listingu. Jeśli `None`, skanuje globalnie przy użyciu `config.otodom_discovery_urls`.
- **TabelaOfert**: `identifier` to slug dewelopera. Jeśli `None`, skanuje globalnie.

---

### `fetch_investment` (Scraping)
Pobiera pełne dane o konkretnej inwestycji. Scraper automatycznie wykrywa natywne slugi dewelopera i inwestycji.

```python
data = fetch_investment(config, fetcher, portal="rp", identifier="12345")
```

---

### `process_batch`
Sekwencyjnie pobiera listę inwestycji z obsługą throttling, retry i ustandaryzowanym raportowaniem postępu. Wykorzystuje `TechnicalDataManager` do natychmiastowego zapisu danych i zdjęć na dysk (izolacja I/O).

```python
from usi_scrapers.api import process_batch

def my_callback(report):
    print(f"Postęp: {report['progress_percent']}% | Status: {report['status']}")

results = process_batch(
    config,
    fetcher,
    portal="otodom",
    identifiers=["https://...", "https://..."],
    on_progress=my_callback,
    delay_range=(1.0, 3.0),
    max_retries=3
)
```

**Argumenty:**
- `identifiers` (*List[str]*): Lista adresów URL lub ID do pobrania.
- `on_progress` (*Callable[[Dict], None]*): Callback otrzymujący szczegółowy raport.
- `delay_range` (*tuple*): Zakres losowego opóźnienia między inwestycjami (sekundy).
- `max_retries` (*int*): Liczba ponowień przy błędach 429 lub timeoutach.

**Format Raportu (`on_progress`):**
```json
{
  "total": 149,
  "current_index": 5,
  "progress_percent": 3,
  "status": "success",          // "success" | "failed" | "retrying"
  "investment": {
    "dev_slug": "urban-home",
    "inv_slug": "nowe-branice",
    "identifier": "https://..."
  },
  "message": "Pobrano pomyślnie i zapisano 12 zdjęć.",
  "error_details": null
}
```

---

### `fetch_many`
Starsza wersja wsadowego scrapingu. Zaleca się używanie `process_batch` dla lepszej kontroli i raportowania.


---

## Narzędzia Techniczne

### `download_raw` / `download_raw_dev`
Pobierają i automatycznie zapisują surowe pliki JSON w strukturze katalogowej `USIdata/` (ścieżka pobierana z `config.public_dir`).

### `identify_developer`
Próbuje wyciągnąć nazwę dewelopera ze strony oferty (szczególnie przydatne dla Otodom i TabelaOfert).

---

## Konfiguracja (`usi_scrapers.models.ScraperConfig`)

Kluczowe pola:
- `public_dir`: `Path` – główny katalog zapisu danych.
- `scraperapi_key`: `Optional[str]` – klucz do ScraperAPI (fallback).
- `otodom_discovery_urls`: `List[str]` – lista URL-i do globalnego skanowania Otodom.
- `rp_discovery_urls`: `List[str]` – lista URL-i do globalnego skanowania RP.
