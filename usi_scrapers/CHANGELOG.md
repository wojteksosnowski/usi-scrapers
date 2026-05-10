## Zmiana kontraktu dla health_check — 2026-05-10
- Przywrócono wsteczną kompatybilność kontraktu `health_check` poprzez dodanie aliasu `verify_consistency`.
- Wprowadzono ostrzeżenie o deprecacji (`DeprecationWarning`) dla starszego aliasu.
- Zaktualizowano sygnaturę `health_check`, czyniąc parametry `config` i `fetcher` opcjonalnymi (automatyczna inicjalizacja).
- Dodano suitę testów regresyjnych `tests/test_health_check.py`.

## Brak natywnego wsparcia dla skanowania globalnego — 2026-05-10
- Zaimplementowano natywne wsparcie dla skanowania globalnego w scraperze Otodom.
- Zrefaktoryzowano api.py, delegując pętlę po URL-ach discovery do wnętrza scrapera.
- Dodano testy jednostkowe weryfikujące globalne discovery (deduplikacja, limity).
- Potwierdzono stabilność całego systemu (93 passed tests, health_check smoke test OK).

## Chaos w sygnaturach metod API — 2026-05-10
- Ujednolicono sygnatury metod discovery we wszystkich scraperach do standardu (config, fetcher, identifier, limit).
- Zintegrowano nowe sygnatury z modułem api.py (list_investments, health_check).
- Zaktualizowano infrastrukturę testową, zapewniając 100% zdanych testów po zmianach.
- Poprawiono spójność wewnętrznych wywołań w modułach scraperów.
