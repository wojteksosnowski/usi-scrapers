# Coda: Tabela Konkurenci

Tabela **Konkurenci** (`grid-3e-6RZhGju`) w dokumencie "USI Tracker" pełni rolę centralnego rejestru deweloperów. Jest to "punkt wejścia" dla procesu odkrywania nowych inwestycji oraz agregator statystyk dotyczących portfolio każdego dewelopera.

## 📋 Główne Zadania Tabeli
1.  **Rejestr Deweloperów**: Przechowuje nazwy, strony WWW oraz unikalne identyfikatory deweloperów w portalach RynekPierwotny i Otodom.
2.  **Automatyzacja Scrapingu**: Zawiera przyciski wyzwalające pobieranie listy inwestycji bezpośrednio z API portali.
3.  **Agregacja Danych**: Oblicza liczbę inwestycji, łączną liczbę mieszkań oraz średnią ocenę na podstawie tabeli `USImaster`.
4.  **Normalizacja**: Generuje `usiFolder` (slug), który jest używany jako nazwa katalogu w lokalnym systemie plików (`Public/USIdata/`).

## 🛠 Kluczowe Kolumny

| Kolumna | Typ | Opis / Formuła |
| :--- | :--- | :--- |
| **Deweloper** | Tekst | Nazwa dewelopera (Display Column). |
| **Inwestycje** | Liczba | `USImaster.CountIf(Deweloper=thisRow)` - liczba projektów w bazie. |
| **Średnia Ocena** | Liczba | Średnia z `ocenaLOG` projektów danego dewelopera. |
| **Standard** | Ikony | Mapowanie oceny na gwiazdki (np. `★¾`). |
| **usiFolder** | Tekst | Unikalny identyfikator folderu (slug). Kluczowy dla synchronizacji z Python workerem. |
| **rpID / rpSlug** | Tekst | ID i slug w portalu rynekpierwotny.pl. |
| **otoID / otoSlug** | Tekst | ID i slug w portalu otodom.pl. |

## ⚡ Przyciski i Automatyzacja

### `addusifolder`
Generuje wartość dla kolumny `usiFolder`. Jeśli pole jest puste, tworzy slug na podstawie `rpSlug`, `otoSlug` lub nazwy dewelopera (oczyszczając ją z polskich znaków i znaków specjalnych).
*   **Logika**: `Lower().RemoveDiacritics().RegexReplace("\s", "-")`

### `rpDEVsuck` (oraz `Copy of rpDEVsuck`)
Wyzwalają pobieranie danych z RynekPierwotny dla wybranego dewelopera.
*   **Działanie**: Używa packa `PineMintRPUtils` do zapytania API RP: `https://rynekpierwotny.pl/api/v2/offers/offer/?vendor={rpID}`.
*   **Wynik**: Dane JSON trafiają do obiektu/tabeli pomocniczej `rpJSONmainV2`.

### `add rpMainJSONV2`
Kluczowy przycisk przetwarzający surowe dane z API RynekPierwotny i populujący tabelę `rpScrape`.
*   **Mechanizm Stage Flattening**: Przycisk analizuje strukturę JSON. Jeśli inwestycja posiada tablicę `groups.stages`, tworzy **osobny wiersz dla każdego etapu** w tabeli `rpScrape`. W przeciwnym razie tworzy jeden wiersz dla całej inwestycji.
*   **Deep Scraping**: Dla każdego rekordu wywołuje `PineMintRPUtils::FetchRawTextFile`, aby pobrać szczegółowy JSON oferty (`/?s=offer-detail`), który jest zapisywany w kolumnie `rpScrape.rpJSON`.

### `otoDEV`
Wyzwalają pobieranie danych z Otodom.
*   **Działanie**: Używa packa `ScraperAPI` do pobrania zawartości strony profilu dewelopera. Wyciąga JSON z tagu `<script id="__NEXT_DATA__">`.
*   **Wynik**: Dodaje rekordy do tabeli pomocniczej `otoScrape`.

## 🔄 Przepływ Danych (Data Flow)

1.  **Dodanie Dewelopera**: Ręczne wpisanie nazwy lub import z CSV.
2.  **Uzupełnienie ID**: Wpisanie `rpID` / `otoID`.
3.  **Discovery**:
    *   Kliknięcie `rpDEVsuck` pobiera listę ofert dewelopera do `rpJSONmainV2`.
    *   Kliknięcie `add rpMainJSONV2` przetwarza listę, stosuje *Stage Flattening* i wypełnia `rpScrape` szczegółowymi danymi JSON.
    *   Dla Otodom: przycisk `otoDEV` dodaje rekordy do `otoScrape`.
4.  **Import do Mastera**: Z tabel tymczasowych (`rpScrape` / `otoScrape`) dane są przenoszone do `USImaster`.
5.  **Local Sync**: Python worker używa `usiFolder` do mapowania danych z Coda na lokalne pliki JSON w `Public/USIdata/`.

## ⚠️ Uwagi Eksploatacyjne
- Tabela zawiera ponad **2300 rekordów** deweloperów.
- Przycisk `dump` (usuwanie) jest zablokowany, jeśli deweloper ma przypisane inwestycje (`Inwestycje > 0`).
- Kolumna `usiFolder` musi być unikalna i zgodna z tym, co generuje funkcja `slugify` w `csv_importer.py`.
