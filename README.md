# USI Scrapers

Pakiet odpowiadający za pobieranie (scrapowanie) danych z polskich portali nieruchomości (RynekPierwotny, Otodom, TabelaOfert) i ich transformację do ustandaryzowanego formatu USI (Unified Schema for Investments).

## Publiczne API

Pakiet docelowo będzie udostępniał następujące metody (w pliku `usi_scrapers/api.py`):

- `list_investments(developer_slug, portal)` - pobieranie listy ofert dewelopera z wybranego portalu.
- `fetch_investment(url_or_slug, portal)` - pobieranie szczegółów i metadanych pojedynczej inwestycji.
- `transform_raw(raw_json, portal)` - translacja surowych danych (Raw JSON) na standardowy schemat USI.

## Instalacja

W celu instalacji w głównym środowisku (np. `usi-tracker`) w trybie deweloperskim (edytowalnym), uruchom:

```bash
pip install -e .
```

## Testowanie (Compliance)

Aby zagwarantować stabilność wyników scraperów, stosowane są testy regresyjne i snapshotowe (katalog `tests/`). Modyfikacje logiki adapterów i fetchera nie mogą zmieniać docelowego formatu USI dla historycznych zestawów surowych danych.

```bash
pip install -e ".[dev]"
pytest
```
