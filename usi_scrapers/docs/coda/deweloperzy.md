# Deweloperzy w USI Tracker

System USI Tracker traktuje "Dewelopera" jako nadrzędny obiekt organizacyjny dla inwestycji. Wszystkie dane w systemie są strukturyzowane pod kątem przynależności do konkretnej firmy deweloperskiej.

## 📁 Przechowywanie Danych

Informacje o deweloperach są przechowywane w dwóch głównych lokalizacjach:

1.  **Pliki JSON (`usi_dev_{slug}.json`)**:
    *   Lokalizacja: `Public/USIdev/` (centralny magazyn) oraz `Public/USIdata/{dev_slug}/` (lokalny magazyn przy danych inwestycji).
    *   Zawartość: Mapowanie identyfikatorów portalowych (RP ID, OTO ID, TO ID), nazwa oficjalna, strona WWW.
2.  **Coda (Tabela "Konkurenci")**:
    *   Służy jako interfejs użytkownika do zarządzania listą deweloperów i wyzwalania procesów odkrywania nowych projektów.

## 🆔 Identyfikacja i Slugowanie

Kluczowym elementem jest `developer_slug`. Jest on generowany na podstawie nazwy dewelopera przy użyciu funkcji `slugify`.

*   **Normalizacja**: Polskie znaki są zamieniane na ich odpowiedniki (np. `ł` -> `l`), spacje na myślniki, a znaki specjalne usuwane.
*   **Stabilność**: Raz nadany slug (np. `dom-development-sa`) jest używany jako nazwa folderu i klucz w plikach JSON. Zmiana nazwy w Coda bez aktualizacji sluga może przerwać powiązanie z plikami na dysku.

## 🏗 Struktura Rekordu Dewelopera (Schema)

```json
{
  "developer_slug": "develia",
  "name": "Develia S.A.",
  "website": "https://www.develia.pl",
  "portal_mapping": {
    "rp": {
      "id": "123",
      "slug": "develia"
    },
    "oto": {
      "agency_ids": ["987654"]
    },
    "to": {
      "agency_id": "456"
    }
  },
  "last_updated": "2024-03-20T10:00:00Z"
}
```

## 🔄 Cykl Życia i Procesy

### 1. Rejestracja (Inicjalizacja)
Nowi deweloperzy trafiają do systemu głównie poprzez:
*   **Import CSV**: Plik `reference-data/deweloperzy.csv` jest przetwarzany przez `csv_importer.py`.
*   **Coda Sync**: Przyciski w tabeli `Konkurenci` pozwalają na dodanie nowych podmiotów.

### 2. Discovery (Odkrywanie)
Proces `python3 -m python_worker.main discover {dev_slug}`:
1.  Ładuje plik `usi_dev_{slug}.json`.
2.  Odczytuje identyfikatory dla RP, OTO i TO.
3.  Wykonuje zapytania do API portali w celu znalezienia projektów, których nie ma jeszcze w folderze `Public/USIdata/{dev_slug}/`.

### 3. Update (Aktualizacja)
Proces `python3 -m python_worker.main update-dev {dev_slug}` iteruje po wszystkich folderach inwestycji przypisanych do dewelopera i aktualizuje ich dane (ceny, statusy sprzedaży).

## 🧩 Powiązania w Kodzie

*   **`DeveloperManager` (`python_worker/developer_manager.py`)**: Klasa odpowiedzialna za operacje I/O na plikach JSON deweloperów.
*   **`Merger` (`python_worker/merger.py`)**: Podczas scalania danych z różnych portali, `Merger` używa danych dewelopera do walidacji i grupowania rekordów.
*   **UI**: Lokalny interfejs React pozwala na filtrowanie i grupowanie wszystkich 6000+ rekordów według dewelopera.