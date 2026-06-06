# TODO

## Kamień 08 — load_raw i has_local_raw w publicznym API
Rozbuduj API usi_scrapers o metody:

`load_raw(config, portal, portal_id) -> dict` — wczytuje surowy JSON inwestycji z dysku
`has_local_raw(config, portal, portal_id) -> bool` — sprawdza czy plik inwestycji istnieje lokalnie

### Krok 08.01
Dodanie funkcji `load_raw(config, portal, portal_id)` jako jawnego, czytelnego aliasu `get_raw_data` w `usi_scrapers/api.py`. Funkcja powinna mieć własny docstring opisujący intencję wywołania przez klienta.
- [x] Dodanie funkcji `load_raw(config: ScraperConfig, portal: str, portal_id: str) -> Optional[Dict[str, Any]]` w `usi_scrapers/api.py` jako wrapper wywołujący `get_raw_data(config, portal, portal_id)` z opisowym docstringiem.
- [x] Sprawdzenie czy `load_raw` jest eksportowane z `usi_scrapers/__init__.py` (lub czy wymaga dodania do `__all__`).

**Podsumowanie:** Dodano funkcję `load_raw` jako publiczny, opisowy alias dla `get_raw_data`. Funkcja posiada własny docstring tłumaczący intencję wywołania przez klientów. Nie wymagała dodania do `__init__.py` ze względu na sposób importowania funkcji `api.py` w projekcie.

### Krok 08.02
Dodanie funkcji `has_local_raw(config, portal, portal_id)` w `usi_scrapers/api.py`, która sprawdza czy plik raw_{portal}_{portal_id}.json istnieje w USIdata bez wczytywania jego zawartości (lekkie sprawdzenie bool).
- [x] Dodanie funkcji `has_local_raw(config: ScraperConfig, portal: str, portal_id: str) -> bool` w `usi_scrapers/api.py`, która używa `StorageResolver.lookup_investment` do znalezienia ścieżki i sprawdza `file_path.exists()` bez otwierania pliku.
- [x] Obsługa przypadku gdy portal jest nieznany lub inwestycja nie istnieje w indeksie — funkcja zwraca `False`.

**Podsumowanie:** Dodano funkcję `has_local_raw` realizującą lekkie sprawdzenie bool istnienia pliku inwestycji. Funkcja używa `StorageResolver.lookup_investment` + `file_path.exists()` bez otwierania pliku. Nieznany portal lub brak w indeksie bezpiecznie zwraca `False`.

### Krok 08.03
Testy jednostkowe dla obu nowych funkcji w `tests/test_api.py`.
- [x] Test `test_load_raw_delegates_to_get_raw_data` w `tests/test_api.py` sprawdzający że `load_raw` zwraca ten sam wynik co `get_raw_data` dla istniejącego pliku.
- [x] Test `test_has_local_raw_true` w `tests/test_api.py` — gdy plik istnieje, funkcja zwraca `True`.
- [x] Test `test_has_local_raw_false_missing_file` w `tests/test_api.py` — gdy plik nie istnieje w indeksie, zwraca `False`.
- [x] Test `test_has_local_raw_false_unknown_portal` w `tests/test_api.py` — nieznany portal zwraca `False`.

**Podsumowanie:** Zaimplementowano 4 testy jednostkowe pokrywające: delegowanie `load_raw` do `get_raw_data`, pozytywne i negatywne przypadki `has_local_raw` oraz obsługę nieznanego portalu. Wszystkie 4 testy przechodzą pomyślnie.