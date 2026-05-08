# USI Tracker & Scrapers - Roadmap & Rekomendacje

Dokument podsumowujący wnioski z migracji warstwy scraperów oraz wytyczne dla przyszłego rozwoju ekosystemu USI.

## 1. Architektura i Refaktoryzacja

### Całkowita Migracja Adapterów (Single Source of Truth)
*   **Cel**: Usunięcie duplikacji logiki transformacji danych.
*   **Działanie**: Zmodyfikować `AdapterFactory` w projekcie `usi-tracker`, aby importował klasy bezpośrednio z `usi_scrapers.adapters`.
*   **Korzyść**: Możliwość całkowitego usunięcia folderu `python_worker/adapters/` z trackera. Logika transformacji będzie rozwijana i testowana wyłącznie w bibliotece.

### Stabilizacja Zależności
*   **Cel**: Zapewnienie powtarzalności środowiska.
*   **Działanie**: Dodać `curl_cffi` oraz `usi-scrapers` (w trybie edytowalnym) do `requirements.txt` w trackerze.
*   **Korzyść**: Szybsze wdrażanie nowych instancji i mniejsze ryzyko błędów `ModuleNotFoundError`.

## 2. Zarządzanie Danymi (Higher Level Logic)

### Cross-Portal Bundling (Deduplikacja)
*   **Cel**: Połączenie ofert tej samej inwestycji z różnych portali (RP, Otodom, TO).
*   **Działanie**: Implementacja usługi w trackerze, która na podstawie znormalizowanych danych GPS i nazw (slugów) tworzy rekordy zbiorcze ("Super-Records").
*   **Rola Biblioteki**: Biblioteka dostarcza "czyste" dane, Tracker zarządza ich relacjami.

### Weryfikacja Parzystości (Parity Guard)
*   **Cel**: Ochrona przed regresjami danych.
*   **Działanie**: Zintegrować skrypt `test_parity_usi.py` z procesem CI lub lokalnym workflow aktualizacji.
*   **Zasada**: Każda zmiana w adapterze biblioteki powinna być potwierdzona testem porównawczym z "bazowym" JSONem, aby uniknąć błędów w historycznych danych.

## 3. Rozszerzenie Funkcjonalności

### Enrichment POI (HERE Maps)
*   **Cel**: Podniesienie wartości analitycznej raportów.
*   **Działanie**: Wykorzystać istniejący moduł `geocoder.py` do stworzenia usługi `enrichment.py`.
*   **Funkcja**: Automatyczne pobieranie punktów zainteresowania (szkoły, komunikacja, parki) w promieniu X metrów od inwestycji i zapisywanie ich w sekcji `amenities`.

### Automatyzacja Rozpoznawania Deweloperów
*   **Cel**: Eliminacja rekordów "Nieznany Deweloper".
*   **Działanie**: Rozszerzyć funkcje `fetch_*_agency_name` tak, aby w przypadku braku dopasowania automatycznie przeszukiwały lokalną bazę `usi_dev_*.json` pod kątem podobieństwa nazw.

## 4. Jakość Danych (Deduplikacja Zdjęć)

### Ujednolicenie Czyszczenia Nazw
*   **Cel**: Spójne nazewnictwo plików na dysku.
*   **Działanie**: Wszystkie komponenty powinny korzystać z `usi_scrapers.utils.images.clean_filename`.
*   **Kluczowe**: Stripping parametrów cache-buster (`_e94b5737.webp`) musi być standardem, aby uniknąć duplikacji gigabajtów zdjęć na dysku.

---
*Dokument sporządzony po pomyślnym wdrożeniu Krok B04 (Shim Layer).*
