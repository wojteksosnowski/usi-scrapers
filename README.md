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

### Scraping pojedynczej inwestycji (Ingest & Refresh)

```python
from usi_scrapers.api import ingest_investment_by_url, refresh_investment_by_id

# Dodawanie nowej inwestycji na podstawie URL
data = ingest_investment_by_url(
    config, fetcher, url="http://rynekpierwotny.pl/oferty/deweloper/inwestycja-123/"
)

# Odświeżanie istniejącej inwestycji na podstawie ID (wymaga podania portalu)
data = refresh_investment_by_id(
    config, fetcher, portal="rp", identifier="123", dev_slug="deweloper", inv_slug="inwestycja"
)
```

## Struktura wyjściowa

```
{public_dir}/USIdata/{dev_slug}/{inv_slug}/
    raw_rp_{inv_slug}.json
    raw_oto_{inv_slug}.json
    raw_to_{inv_slug}.json

{public_dir}/USI/{dev_slug}/{inv_slug}/
    *.webp / *.jpg

## Mapowanie Danych (`portal_data_mapping.json`)

Plik `usi_scrapers/schemas/portal_data_mapping.json` służy jako centralne, w pełni deklaratywne źródło prawdy dla ścieżek dostępu i transformacji ustrukturyzowanych danych pobranych z portali. Api dla tego pliku ma za zadanie być **agnostyczne w stosunku do źródła danych** (kolejne warstwy aplikacji nie muszą wiedzieć, z jakiego portalu pochodzą wyciągnięte informacje).
Obsługuje:
- **Dot notation**: `parent.child.value`
- **Root access**: `.` dla przekazania całego dokumentu JSON.
- **Operatory alternatywy**: `pathA|pathB` pozwalają na bezpieczny fallback w przypadku braku lub zmiany nazwy pola.
- **Indeksowanie i filtrowanie tablic**: `array[0].value` lub `array[name=Cecha].value`.
- **Ekstrakcja z HTML w locie**: Dostęp do surowego HTML poprzez `_raw_html` z ewaluacją po wyrażeniach (np. `{"path": "_raw_html", "regex": "(?s)class=\"dev-link\""}`).
- **Transformatory (`transform`)**: Konwersja i standaryzacja danych w locie, dzięki dynamicznemu systemowi transformatorów z pliku `transformers.py` (np. operacje: `cm_to_m`, `date_to_quarter`, ekstrakcje adresów typu `clean_street`, `rp_extract_city`, czy obróbka galerii np. `rp_gallery_to_flat_list`). Dodatkowo na poziomie transformatora istnieje ujednolicone rozliczanie się z jednostek (np. PLN_na_m2). 
- **Ewaluacja sygnałów (`evaluate_signals`)**: Potężny mechanizm ewaluacji logicznej. Pozwala np. na ustalanie segmentu (apartament/inwestycja) czy typu transakcji, przeszukując zestaw dróg/ścieżek.

### System Transformatorów (Transformers)
Znajdujący się w `transformers.py` moduł korzystający ze wzorca dekoratora `@register_transformer`. Pozwala na całkowitą izolację problemów związanych z formatowaniem i kategoryzacją poszczególnych pól. Wszelkie modyfikacje danych (jak np. ucinanie przedrostków "ul." czy dzielenie wieloczłonowych miast dla Rynku Pierwotnego) realizowane są po stronie poszczególnych "małych, testowalnych" funkcji przypisanych bezpośrednio w pliku mapującym.

## Testy

```bash
venv/bin/pytest
venv/bin/pytest tests/test_scraper_otodom.py
```
