# Pobieranie danych z Otodom.pl (OTO)

Dokumentacja procesów pobierania, ekstrakcji JSON oraz obsługi rekordów wieloetapowych dla portalu Otodom.pl.

## 1. Mechanizm Pozyskiwania Danych (JSON)

W przeciwieństwie do portalu RynekPierwotny.pl, Otodom nie udostępnia publicznego, prostego API zwracającego czyste dane JSON. System USI Tracker wykorzystuje fakt, że Otodom jest aplikacją opartą na frameworku **Next.js**.

### Ekstrakcja `__NEXT_DATA__`
Dane są pobierane bezpośrednio z kodu źródłowego HTML strony inwestycji. Skrypt `python_worker/scraper_otodom.py` lokalizuje blok:
```html
<script id="__NEXT_DATA__" type="application/json">...</script>
```
Zawartość tego tagu jest parsowana jako JSON. Kluczowe dane znajdują się w ścieżce:
`props -> pageProps -> ad` (dla stron szczegółów) lub `props -> pageProps -> data -> searchAds` (dla listingu).

### Przykładowe Pola w JSON (Obiekt `ad`):
- **ID Inwestycji**: `ad.id`
- **Nazwa**: `ad.title`
- **Lokalizacja**: `ad.location.coordinates` (`latitude`, `longitude`)
- **Termin Oddania**: `ad.topInformation` (szukany element z label: `project_finish_date`)
- **Galeria**: `ad.images` (pobierane są linki `large`)
- **Deweloper**: `ad.agency` (zawiera `name`, `id` oraz `url`)

## 2. Zapytania Generujące Dane

System USI Tracker wykonuje zapytania do dwóch typów stron Otodom:

1.  **Strona Listingu (Discovery)**:
    - URL: `https://www.otodom.pl/pl/inwestycje/oferty/{region}?investmentEstateType=FLATS&by=LATEST`
    - Cel: Wykrycie nowych slugów inwestycji.
2.  **Strona Szczegółów (Scrape)**:
    - URL: `https://www.otodom.pl/pl/oferta/{investment-slug}`
    - Cel: Pobranie pełnych metadanych i obrazów.

## 3. Obsługa Rekordów Wieloetapowych

Model danych Otodom różni się znacząco od RynekPierwotny.pl w kwestii etapowania:

### Brak "Spłaszczania" (Flattening)
W portalu RynekPierwotny jedna inwestycja "matka" może zawierać listę etapów w jednym JSONie. W **Otodom każdy etap jest traktowany jako całkowicie oddzielna oferta (ogłoszenie inwestycji)**.

- **Identyfikacja**: Każdy etap posiada własny unikalny `ID` oraz `slug` w portalu Otodom (np. `apartamenty-kameliowa-vi-etap-ID4AYaT`).
- **Import**: System USI Tracker importuje każdy taki rekord jako niezależny plik `usi_*.json`. Nie ma potrzeby stosowania `stage_detector.py` (który jest zarezerwowany dla RP), ponieważ portal sam separuje te dane.
- **Grupowanie**: Rekordy te są wiązane w USI Tracker poprzez `developer_slug` oraz nazewnictwo w Coda, ale technicznie są to osobne byty od momentu pobrania.

## 4. Mapowanie Danych (OtodomAdapter)

Klasa `OtodomAdapter` w `adapters.py` odpowiada za transformację surowego JSONa z Otodom do formatu USI:

| Pole USI | Ścieżka w JSON Otodom | Uwagi |
| :--- | :--- | :--- |
| `coords` | `location.coordinates` | Bezpośrednie lat/lng (w przeciwieństwie do RP, gdzie kolejność jest odwrócona) |
| `delivery_date` | `topInformation[label=project_finish_date]` | Konwertowane z `YYYY-MM-DD` na format "Q kw. YYYY" |
| `units_count` | `characteristics[key=number_of_properties]` | |
| `price_min` | `characteristics[key=price_per_m_from]` | |

## 5. Przykłady

### Przykład Discovery (Listing)
Listingi są zdefiniowane w Coda na stronie `scrapeotodom`. System iteruje po linkach regionalnych i wyciąga z nich `slugi`.

### Przykład JSONa (Fragment)
```json
{
  "ad": {
    "id": 67916467,
    "title": "Apartamenty Kameliowa VI Etap",
    "slug": "apartamenty-kameliowa-vi-etap-ID4AYaT",
    "location": {
      "coordinates": {
        "latitude": 51.27193,
        "longitude": 22.51272
      }
    },
    "topInformation": [
      {
        "label": "project_finish_date",
        "values": ["2027-06-30"]
      }
    ]
  }
}
```

## przycisk add otoMainJSON
```
ForEach(
  otoJSONmain,
  AddRow(
    otoScrape,
    otoScrape.otoSlug,
    CurrentValue.ParseJSON("$.slug")
      .RegexExtract(
        "(?:.*)(?=-ID)"
      ),
    otoScrape.otoID,
    CurrentValue.ParseJSON("$.slug").RegexExtract("(?<=ID).+$").Trim(),
    otoScrape.Inwestycja,
    CurrentValue.ParseJSON("$.title"),
    otoScrape.otoJSON,
    CurrentValue,
    otoScrape.Termin,
    Concatenate(
      CurrentValue
        .ParseJSON(
          "$.investmentEstimatedDelivery.quarter"
        ),
      " kw. ",
      CurrentValue.ParseJSON("$.investmentEstimatedDelivery.year")
    ),
    otoScrape.otoAdres,
    Concatenate(
      "https://www.otodom.pl/pl/inwestycja/",
      CurrentValue.ParseJSON("$.slug")
    )
  )
)
```