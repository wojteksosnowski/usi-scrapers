## Rozszerzenie Progress Reporting (0.4.4) — 2026-05-12
- Dodano obsługę callbacka `on_progress` do funkcji `fetch_investment`, umożliwiając ustandaryzowane raportowanie postępu również dla pojedynczych pobrań (total=1).

## Batch Processing i Progress Reporting (0.4.3) — 2026-05-12
- Dodano funkcję `process_batch` do sekwencyjnego pobierania paczek inwestycji.
- Zaimplementowano ustandaryzowany system raportowania postępu (`on_progress`) z bogatym payloadem (indeksy, procenty, statusy, błędy).
- Wprowadzono wbudowany throttling (losowe opóźnienia `delay_range`) chroniący przed wykryciem wzorca bota.
- Dodano mechanizm Retry dla błędów 429 (Too Many Requests) i timeoutów (10s oczekiwania przed ponowieniem).
- Pełna izolacja I/O: wykorzystanie `TechnicalDataManager` do natychmiastowego zapisu JSON i zdjęć na dysk podczas procesowania paczki.

## Refaktoryzacja Discovery i Scrape API (0.4.2) — 2026-05-12
- Zminimalizowano dane zwracane przez Discovery API do niezbędnego minimum (`id` i `url`).
- Wprowadzono autonomiczne wykrywanie slugów (dewelopera i inwestycji) bezpośrednio ze stron portali.
- Całkowicie usunięto zależność od sztucznego generowania slugów (`slugify`) na rzecz natywnych identyfikatorów.
- Ujednolicono sygnatury metod `scrape_*` i `fetch_investment`, usuwając konieczność przekazywania slugów na wejściu.
- Dodano suitę testów bezpieczeństwa weryfikującą poprawność natywnej ekstrakcji slugów.

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
