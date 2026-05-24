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
Pobiera pełne dane o konkretnej inwestycji. Scraper automatycznie wykrywa natywne slugi dewelopera i inwestycji. Wspiera opcjonalny callback `on_progress` do raportowania statusu.

```python
data = fetch_investment(config, fetcher, portal="rp", identifier="12345", on_progress=callback)
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

### `list_developers`
Pobiera listę deweloperów z katalogu wskazanego portalu. Obsługuje paginację.

```python
from usi_scrapers.api import list_developers

dev_page = list_developers(config, fetcher, portal="rp", page=1)
print(f"Strona {dev_page.page}/{dev_page.total_pages}. Znaleziono {len(dev_page.developers)} deweloperów.")
```

---

## Narzędzia Techniczne

### `download_raw` / `download_raw_dev`
Pobierają i automatycznie zapisują surowe pliki JSON w strukturze katalogowej `USIdata/` (ścieżka pobierana z `config.public_dir`).

### `save_raw` / `save_raw_developer`
Zapisuje przekazany słownik jako surowy plik JSON w strukturze katalogowej `USIdata/`. Wymaga ręcznego podania `portal_id`.

```python
from usi_scrapers.api import save_raw

saved_path = save_raw(config, data_dict, dev_slug="moj-dev", inv_slug="moja-inw", portal_prefix="rp", portal_id="123")
```

### `identify_developer`
Próbuje wyciągnąć nazwę dewelopera ze strony oferty na podstawie podanego adresu URL (szczególnie przydatne dla Otodom i TabelaOfert, gdzie nazwa dewelopera może być zaszyta głęboko w HTML).

```python
from usi_scrapers.api import identify_developer

dev_name = identify_developer(fetcher, portal="otodom", url="https://www.otodom.pl/pl/oferta/...")
```

### `classify_segment`
Klasyfikuje inwestycję do jednej z 5 kategorii USI na podstawie agnostycznych sygnałów diagnostycznych. Zwraca `None`, jeśli klasyfikacja nie jest możliwa (null fallback).

```python
from usi_scrapers import classify_segment

# Przykładowe sygnały wyciągnięte ze scrapera
signals = {
    "apartments": "11",
    "houses": None,
    "rental": False,
    "commercial": None,
    "investment": ["flats"]
}

segment = classify_segment(signals)
# "mieszkania deweloperskie"
```

**Kategorie (Segmenty):**
1. `mieszkania deweloperskie`
2. `lokale inwestycyjne`
3. `segmenty i domy`
4. `prs`
5. `lokale usługowe`

---

## Mapowanie Danych (`usi_scrapers.mapping`)

Moduł `mapping` odpowiada za ekstrakcję danych z surowych struktur JSON przy użyciu deklaratywnych ścieżek zdefiniowanych w `portal_data_mapping.json`.

### `load_mapping`
Ładuje i cache'uje zawartość pliku `portal_data_mapping.json`.

```python
from usi_scrapers.mapping import load_mapping

mapping_data = load_mapping()
```

### `get_mapping`
Pobiera definicje ścieżek dla konkretnego portalu i typu encji.

```python
from usi_scrapers.mapping import get_mapping

# Pobierz mapowanie dla inwestycji na Otodom
oto_invest_mapping = get_mapping("oto", "investment")
```

**Argumenty:**
- `portal_prefix` (*str*): Prefix portalu (np. `oto`, `rp`, `to`).
- `entity_type` (*str*): Typ encji, domyślnie `investment`.

### `resolve_path`
Rdzeń silnika ekstrakcji. Rozwiązuje złożone ścieżki w strukturach JSON.

```python
from usi_scrapers.mapping import resolve_path

data = {"nested": {"list": [{"id": 1, "val": "A"}, {"id": 2, "val": "B"}]}}
result = resolve_path(data, "nested.list[id=2].val")
# result == "B"
```

**Obsługiwane funkcje:**
- **Notacja kropkowa**: `a.b.c`
- **Indeksy tablic**: `a[0].b`
- **Filtrowanie tablic**: `a[key=value].b`
- **Potoki (Fallback)**: `a.b | a.c` (zwraca pierwszą nie-pustą wartość).
- **Regex**: Jeśli ścieżka jest słownikiem `{"path": "...", "regex": "..."}`, po wyciągnięciu wartości zostanie na niej wykonany regex.

---

## Konfiguracja (`usi_scrapers.models.ScraperConfig`)

Kluczowe pola:
- `public_dir`: `Path` – główny katalog zapisu danych.
- `scraperapi_key`: `Optional[str]` – klucz do ScraperAPI (fallback).
- `otodom_discovery_urls`: `List[str]` – lista URL-i do globalnego skanowania Otodom.
- `rp_discovery_urls`: `List[str]` – lista URL-i do globalnego skanowania RP.

---

## Logowanie (`usi_scrapers.get_logger`)

Pakiet używa ustandaryzowanego loggera, który automatycznie dodaje informację o wersji pakietu do każdej wiadomości.

```python
from usi_scrapers import get_logger

logger = get_logger(__name__)
logger.info("Rozpoczynanie procesu...")
# Output: [usi-scrapers v0.7.9] Rozpoczynanie procesu...
```
