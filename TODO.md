# TODO

## Kamień 02 — Nowy interfejs API zwracający UID
### Krok 02.01
Modyfikacja funkcji pobierających (jak `api.download_raw`), aby zwracały słownik z informacjami takimi jak `status`, `portal_id`, `dev_slug`, `inv_slug` zamiast polegać na kliencie zarządzającym zapisem.

- [x] Refaktoryzacja `download_raw` i `download_raw_dev` w `api.py` tak, aby zwracały słownik identyfikatorów. (Wykonane przy okazji refaktoryzacji `target_dir`).
- [ ] Zaktualizowanie testów jednostkowych w `tests/test_api.py`, by poprawnie weryfikowały nowy słownikowy format zwracany przez `download_raw`.

## Kamień 03 — API do odczytu danych przez ID
### Krok 03.01
Stworzenie funkcji pozwalających klientowi na odpytanie backendu po ID inwestycji (np. `api.get_raw_data`), które za pomocą Storage Resolvera same odnajdą fizyczny plik i zwrócą przetworzonego JSONa.

- [ ] Dodanie metody `get_raw_data(config, portal, portal_id) -> dict` w `api.py`, odpytującej `StorageResolver` o lokalizację.
- [ ] Zaimplementowanie mechanizmu wczytywania JSONa ze ścieżki i zwracania go klientowi.
- [ ] Dodanie metody `get_raw_dev_data(config, portal, portal_id) -> dict` w `api.py`.
- [ ] Stworzenie testów jednostkowych dla tych metod w `tests/test_api.py`.
