# Zasady pobierania danych z RynekPierwotny.pl (RP)

System USI Tracker wykorzystuje API v2 portalu RynekPierwotny.pl do pozyskiwania szczegółowych danych o inwestycjach. Poniżej opisano mechanizmy zapytań, strukturę danych oraz obsługę inwestycji wieloetapowych.

## 1. Zapytania API (JSON Queries)

Głównym źródłem danych są endpointy API RynekPierwotny zwracające ustrukturyzowane dane JSON. W dokumencie Coda oraz w workerze Python używane są trzy główne typy zapytań:

### A. Zapytanie Listy (Discovery / JSONMAIN)
Służy do wykrywania nowych inwestycji lub masowej aktualizacji.
*   **URL:** `https://rynekpierwotny.pl/api/v2/offers/offer/?s=offer-list&display_type=1&distance=5&for_sale=true&limited_presentation=false&page=1&page_size=30&show_on_listing=true&type=1`
*   **Parametry:**
    - `s=offer-list`: Tryb listy ofert.
    - `page_size=30`: Maksymalna liczba rekordów na stronę (RP nie zwraca więcej niż 30).
    - `type=1`: Filtrowanie typów (mieszkania/domy).

### B. Zapytanie Dewelopera
Pobiera wszystkie oferty przypisane do konkretnego dostawcy (vendor).
*   **URL:** `https://rynekpierwotny.pl/api/v2/offers/offer/?s=vendor-detail-offer-list&vendor={vendor_id}&page_size=30`

### C. Zapytanie Szczegółów (Offer Detail)
Pobiera pełne dane o konkretnym `offer_id` (w tym opis, współrzędne, etapy).
*   **Szczegóły:** `https://rynekpierwotny.pl/api/v2/offers/offer/{offer_id}/?s=offer-detail`
*   **Galeria:** `https://rynekpierwotny.pl/api/v2/offers/offer/{offer_id}/?s=offer-detail-gallery`

---

## 2. Obsługa Rekordów Wieloetapowych (Stage Flattening)

RynekPierwotny grupuje etapy inwestycji pod jednym "parasolem" grupy, ale każdy etap posiada własny unikalny `offer_id`. System USI Tracker stosuje strategię **spłaszczania etapów** (Stage Flattening).

### Mechanizm wykrywania etapów:
1.  W JSONie szczegółów scraper szuka obiektu `groups`.
2.  Jeśli `groups` zawiera tablicę `stages`, system traktuje każdy element tej tablicy jako osobną inwestycję w USI Tracker.
3.  **Cross-linking:** Każdy etap przechowuje referencję do swoich "rodzeństwa" (siblings) w polu `sibling_stage_folders`.

### Przykład struktury JSON (Etapy):
```json
"groups": {
    "id": 654,
    "name": "Lawinowa 18",
    "stages": [
        {
            "id": 1796,
            "name": "Etap I i II",
            "offer": { "id": 20237, "slug": "lawinowa-18-lodz-mileszki" },
            "sort": 1,
            "current": false
        },
        {
            "id": 1797,
            "name": "Etap III",
            "offer": { "id": 20318, "slug": "lawinowa-18-etap-iii-lodz-mileszki" },
            "sort": 2,
            "current": true
        }
    ]
}
```

### Stubs (Zaślepki)
Jeśli system wykryje etap, który nie istnieje jeszcze w lokalnej bazie `Public/USIdata/`, tworzy plik `usi_stage_stub.json`. Pozwala to na automatyczne "odkrycie" brakujących etapów tej samej inwestycji bez ponownego skanowania całej listy portalu.

---

## 3. Mapowanie danych w Coda

W tabeli `usiKonkurencja` (USIMaster), dane z RP są mapowane następująco:
*   **`rpID`**: Mapowane na `offer.id` z API.
*   **`rpJSON`**: Przechowuje pełny zrzut z endpointu `offer-detail`.
*   **Status Etapu**: Wyciągany za pomocą formuł Coda lub adaptera Python:
    - `is_current`: Czy ten konkretny `offer_id` jest obecnie promowany jako główny.
    - `stage_sort`: Kolejność etapu (np. 1, 2, 3).

## 4. Przykłady URLi (Techniczne)

| Typ | Przykładowy URL API |
| :--- | :--- |
| **Lista** | `.../api/v2/offers/offer/?s=offer-list...` |
| **Szczegóły** | `.../api/v2/offers/offer/20318/?s=offer-detail` |
| **Stage URL** | `.../oferty/{vendor}/{slug}-{id}/?show_sold_stage=true&stage={stage_id}` |

> [!NOTE]
> RP API v2 zwraca dane w formacie `{ "type": "...", "value": ... }`. System USI Tracker posiada wbudowane helpery (np. `get_v` w Pythonie), które automatycznie "rozpakowują" te wartości do płaskiej struktury.

## przycisk add rpMainJSONV2

ForEach(
  rpJSONmainV2,
  If(
    CurrentValue.ParseJSON("$.value.groups.value.stages.value")
      .IsBlank(),
    AddRow(
      rpScrape,
      rpScrape.Inwestycja,
      CurrentValue.ParseJSON("$.value.name"),
      rpScrape.rpAdres,
      Concatenate(
        "https://rynekpierwotny.pl/oferty/",
        CurrentValue.ParseJSON("$.value.vendor..slug").Trim(),
        "/",
        CurrentValue.ParseJSON("$.value.slug").Trim(),
        "-",
        CurrentValue.ParseJSON("$.value.id").Trim(),
        "/"
      ),
      rpScrape.rpJSON,
      PineMintRPUtils::FetchRawTextFile(
        Concatenate(
          "https://rynekpierwotny.pl/api/v2/offers/offer/",
          CurrentValue.ParseJSON("$.value.id"),
          "/?s=offer-detail"
        )
      )
        .ToText()
    ),
    ForEach(
      CurrentValue.ParseJSON("$.value.groups.value.stages.value"),
      AddRow(
        rpScrape,
        rpScrape.Inwestycja,
        CurrentValue.ParseJSON("$.value.offer.value.name"),
        rpScrape.rpAdres,
        Concatenate(
          "https://rynekpierwotny.pl/oferty/",
          CurrentValue
            .ParseJSON(
              "$.value.offer.value.vendor.value.slug"
            )
            .Trim(),
          "/",
          CurrentValue.ParseJSON("$.value.offer.value.slug").Trim(),
          "-",
          CurrentValue.ParseJSON("$.value.offer.value.id").Trim(),
          "/?show_sold_stage=true&stage=",
          CurrentValue.ParseJSON("$.value.id")
        ),
        rpScrape.rpJSON,
        PineMintRPUtils::FetchRawTextFile(
          Concatenate(
            "https://rynekpierwotny.pl/api/v2/offers/offer/",
            CurrentValue.ParseJSON("$.value.offer.value.id").Trim(),
            "/?s=offer-detail"
          )
        )
          .ToText()
      )
    )
  )
)