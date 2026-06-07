Oto zintegrowany, jednolity dokument **CANONICAL.md**. Łączy on specyfikację systemów `usi-scrapers` oraz `usi-tracker`, eliminując powtórzenia, zachowując precyzyjną strukturę katalogów, reguły spójności, opisy formatów plików oraz architekturę obu komponentów.

---

# CANONICAL.md — Kompletna specyfikacja architektury, bazy danych i standardów nazewnictwa

Ten dokument stanowi jedyne, ostateczne źródło prawdy (SSOT) dla konwencji nazewniczych, struktur plików JSON, zależności oraz przepływu danych w ekosystemie USI (zarówno dla komponentu pobierającego `usi-scrapers`, jak i systemu zarządzania `usi-tracker`).

---

## 1. Struktura katalogów i lokalizacja bazy danych

Główny katalog współdzielony (w środowisku produkcyjnym definiowany przez `ScraperConfig.public_dir` lub `DROPBOX_PATH/Public/`) zawiera trzy kluczowe podkatalogi. Symlink `Public/` w repozytorium służy wyłącznie do celów deweloperskich i debugowania.

```
LOKALIZACJA_BAZY_DANYCH/ (np. DROPBOX_PATH/Public/ lub public_dir/)
├── USI/                            # Obrazy i galerie inwestycji
│   └── {dev_slug}/
│       └── {inv_slug}/
│           └── {filename.ext}
│
├── USIdata/                        # Dane JSON oraz dzienniki inwestycji
│   ├── _index.json                 # Globalny indeks inwestycji (computed)
│   └── {dev_slug}/
│       └── {inv_slug}/
│           ├── raw_{portal}_{portal_id}.json
│           ├── raw_{portal}_{portal_id}_{YYYYMMDD_HHMMSS}.json   ← Archiwum surowych danych
│           ├── meta_{portal}_{portal_id}.json
│           ├── meta_{portal}_{portal_id}_{YYYYMMDD_HHMMSS}.json  ← Archiwum metadanych z Cody
│           ├── usi_stage_stub.json                               ← Placeholder dla etapu wieloetapowego RP
│           └── usi_{portal}_{portal_id}.json                     ← Unified Record (Główny plik produkcyjny)
│
└── USIdev/                         # Dane JSON deweloperów
    └── {dev_slug}/
        ├── usi_dev_{portal}_{portal_id}.json       ← Level 2: Rekord portalu dewelopera (1 na portal)
        ├── dev_master_{DM-ID}.json                ← Level 3: Rekord scalenia deweloperów (opcjonalny)
        ├── dev_log_{portal}_{portal_id}.txt                 ← Dziennik zdarzeń dewelopera (append-only JSONL)
        ├── discovery_{portal}_{portal_id}.json                        ← Wyniki ostatniego discovery (computed)
        ├── raw_{portal}_{portal_id}.json          ← Surowe dane profilu dewelopera
        ├── raw_{portal}_{portal_id}_{YYYYMMDD_HHMMSS}.json   ← Archiwum profilu dewelopera
        └── logo_{portal}_{portal_id}.{ext}        ← Plik logo dewelopera z danego portalu

python_worker/data/ (Lokalne dane aplikacyjne tracker-worker)
├── usi_counters.json               # Liczniki auto-increment dla unikalnych ID (DEV, INV, DM)
└── wyrozniki.csv                   # Tabela punktacji i wag udogodnień inwestycji

```

---

## 2. System identyfikatorów, prefiksów i slugifikacji

### 2.1 Prefiksy portali

| Portal | Prefix w nazwie pliku | Identyfikator w systemie (`api.py`, `sources`) |
| --- | --- | --- |
| RynekPierwotny | `rp` | `"rp"` |
| Otodom | `oto` | `"oto"` / `"otodom"` |
| TabelaOfert | `to` | `"to"` / `"tabelaofert"` |

### 2.2 System wewnętrznych ID (USI Counters)

Trzy sekwencje identyfikatorów współdzielą atomowy plik `python_worker/data/usi_counters.json`. Generowanie wartości odbywa się wyłącznie przez `DeveloperManager.generate_usi_id()` przy użyciu blokad systemowych (`threading.Lock()` dla wątków + `fcntl.flock()` dla procesów). Format to `PREFIX-NNNNN` (uzupełniany zerami do minimum 4 cyfr):

* **`DEV-`** (klucz `"dev"`): Rekord dewelopera (Level 2). Przykład: `DEV-26702`
* **`INV-`** (klucz `"inv"`): Rekord inwestycji. Przykład: `INV-00042`
* **`DM-`** (klucz `"dm"`): Rekord scalenia deweloperów (Level 3). Przykład: `DM-0492`

### 2.3 Algorytm slugifikacji (`slug_utils.py`)

Slugifikacja jest jednokierunkowym narzędziem pomocniczym. **Nigdy nie wolno używać mechanizmu slugifikacji do dynamicznego odnajdywania ścieżek lub identyfikacji istniejących rekordów.** Slug po pierwszym zapisie staje się **immutable** (niezmienny).
*Uwaga:* Slugi pochodzące bezpośrednio z portali RP i Otodom są przepisywane dosłownie, bez przepuszczania przez poniższy algorytm.

1. Zamiana liter `ł → l`, `Ł → L` (NFKD nie obsługuje polskiej kreski).
2. Normalizacja NFKD.
3. Usunięcie znaków niebędących kodami ASCII.
4. Zamiana ciągu znaków `[^a-z0-9]+` na pojedynczy myślnik `-`.
5. Usunięcie myślników `-` z początku i końca tekstu.
6. Konwersja na małe litery (lowercase).

---

## 3. Specyfikacja plików inwestycji (`USIdata/`)

### 3.1 `raw_{portal}_{portal_id}.json` (Zasada PURE-RAW)

* **Ścieżka:** `{public_dir}/USIdata/{dev_slug}/{inv_slug}/raw_{portal}_{portal_id}.json`
* **Identyfikacja `portal_id`:** * **Otodom:** `ad.id` (numeryczny) LUB `ID{hash}` wyciągnięty z adresu URL (np. `ID6G8v`).
* **RynekPierwotny:** `offer_id` (numeryczny).
* **TabelaOfert:** Identyfikator inwestycji poprzedzony literą `i` (np. `i8982461`).


* **Zasada PURE-RAW:** Pliki te są **immutable** po pobraniu. Zawierają wyłącznie czysty, surowy zrzut danych z API lub struktur strony portalu (np. pełne API RP, `pageProps` z Next.js Otodom lub JSON-LD TabelaOfert). Nie wstrzykuje się do nich żadnych metadanych systemowych ani dat pobrania. Daty te wynikają z systemu plików lub plików archiwalnych.
* **Specyfika struktur:**
* *RynekPierwotny:* Wartości skalarne są opakowane w strukturę `{"type": "val"|"obj"|"arr", "value": ...}`. Do odczytu wymagane jest użycie funkcji `adapters._get_val()`. Pole `geo_point.coordinates` przyjmuje format GeoJSON `[lng, lat]`, czyli odwrotnie niż w zunifikowanym formacie trackerowym.



### 3.2 `meta_{portal}_{portal_id}.json` (Oceny redakcyjne z Cody)

* **Ścieżka:** `{public_dir}/USIdata/{dev_slug}/{inv_slug}/meta_{portal}_{portal_id}.json`
* **Zawartość:** Dane redakcyjne zaimportowane ze skryptów obsługujących CSV (`USImaster-prep.csv`). Zawierają statusy, oceny cząstkowe (`Balkony`, `Fasady`, `Wnętrza`, `Teren`, `Mieszkania`, `Udogodnienia`), komentarze, segment oraz `imgList` — przemapowaną listę ścieżek do zdjęć stałowartościowych, dopasowanych przez importera do galerii z surowych JSONów.

### 3.3 `usi_{portal}_{portal_id}.json` (Unified Record — Canonical)

* **Ścieżka:** `{public_dir}/USIdata/{dev_slug}/{inv_slug}/usi_{portal}_{portal_id}.json`
* **Opis:** Główny, zunifikowany plik produkcyjny generowany przez komponent `Merger.merge()`. Stanowi podstawę odczytu danych dla interfejsu użytkownika. Agreguje dane ze wszystkich dostępnych źródeł portali dla danej inwestycji, dbając o zachowanie historii audytowej oraz właściwych priorytetów danych.

### 3.4 `usi_stage_stub.json` (Detekcja etapów)

* **Ścieżka:** `{public_dir}/USIdata/{dev_slug}/{inv_slug}/usi_stage_stub.json`
* **Opis:** Placeholder generowany przez `utils/stage_detector.py` (`run_stage_detection()`) w sytuacjach, gdy wykryto wieloetapową inwestycję na RynekPierwotny (`groups_id`), ale sąsiedni etap nie posiada jeszcze swojego pliku zunifikowanego ani katalogu w bazie.

### 3.5 `processing_log_{investment_slug}.txt`

Log zdarzeń w formacie plain-text (append-only), dokumentujący każdą operację zapisu i synchronizacji wykonaną na poziomie katalogu inwestycji. Format wpisu: `[TIMESTAMP] {dev_slug}/{inv_slug} - {Zdarzenie}`.

### 3.6 Plik `_index.json` (Globalny indeks inwestycji)

* **Ścieżka:** `{public_dir}/USIdata/_index.json`
* **Opis:** Kompletny, zrekonstruowany i wyliczony indeks wszystkich inwestycji w bazie danych. Służy jako fast-path dla interfejsu graficznego. **Nigdy nie należy edytować go ręcznie.** Aktualizacja następuje za pomocą polecenia: `python3 -m python_worker.main rebuild-index`.

---

## 4. Specyfikacja plików deweloperów (`USIdev/`)

Zarządzanie strukturą deweloperów oparte jest na trójpoziomowej architekturze, która separuje dane pobrane z portali od logicznych procesów scalania (merge) podmiotów rynkowych.

```
Level 1: Warstwa fizycznego katalogu dewelopera ({dev_slug}/)
  │
  ├──► Level 2: Pliki portali dewelopera (usi_dev_{DEV-ID}_{dev_slug}.json)
  │             - Maksymalnie 1 aktywny portal na plik
  │             - Zawiera odnośnik raw_file oraz sekcję portal_mapping
  │
  └──► Level 3: Plik scalenia i unifikacji (dev_master_{DM-ID}.json)
                - Definiuje nadrzędność i relacje po operacjach merge
                - Przechowuje tablice merged_from[] oraz dismissed[]

```

### 4.1 `usi_dev_{DEV-ID}_{developer_slug}.json` (Level 2 — Rekord portalu)

* **Zasada 1:1:** Jeden plik Level 2 odpowiada powiązaniu z **dokładnie jednym** portalem w słowniku `portal_mapping` (pozostałe portale mają wartość `null`). Jeżeli deweloper posiada konta na dwóch portalach (np. `rp` i `oto`), w tym samym folderze dewelopera muszą znajdować się dwa osobne pliki z dwoma unikalnymi identyfikatorami `DEV-ID`.
* **Pola zabronione:** Pliki Level 2 **nie mogą** bezpośrednio przechowywać tablicy `merged_from` (należy ona do Level 3). Pole `parent_id` jest uznane za **obsolete** i jest automatycznie usuwane podczas zapisu przez funkcję `create_developer_file()`. Relacja podrzędności ("child") wynika wyłącznie ze struktury pliku master na Level 3. Rekordy posiadające przypisanie do pliku master są automatycznie ukrywane na listach w `/api/developers`.

### 4.2 `dev_master_{DM-ID}.json` (Level 3 — Rekord scalenia)

Generowany automatycznie przez procedurę `merge_developers()`. Przechowuje informacje o wszystkich deweloperach scalonych do danego podmiotu (`merged_from`) wraz z datami wykonania operacji, oraz listę odrzuconych sugestii połączeń (`dismissed`).

### 4.3 `raw_{portal}_{portal_id}.json` (Profil dewelopera)

Surowy zrzut profilu dewelopera pobrany z zewnętrznego portalu. Zgodnie z zasadą PURE-RAW nie zawiera metadanych systemowych. Wyjątkiem są pliki generowane przez skrypt `import_competitors_csv()`, które otrzymują flagę `"_mock": true` osadzoną bezpośrednio w strukturze JSON, informującą system, że dane są makietą zbudowaną na bazie pliku CSV, a nie rzeczywistym zrzutem z API portalu.

### 4.4 `logo_{portal}_{portal_id}.{ext}`

* **Opis:** Fizyczny plik graficzny logo pobierany podczas scrapowania dewelopera (`utils/images.py → download_developer_logo()`). Jeżeli portal nie zwraca poprawnego adresu URL logo, plik nie powstaje. Pobieranie jest pomijane, jeżeli na dysku istnieje już plik o rozmiarze większym niż 1 KB.

---

## 5. Przetwarzanie i transformacja danych: Adaptery i Merger

### 5.1 Zunifikowany schemat wejściowy (Zrzut przed scaleniem)

Wszystkie adaptery portali (`RPAdapter`, `OtodomAdapter`, `TOAdapter` w `adapters/__init__.py`) przekształcają dane surowe do identycznego słownika wejściowego, zanim zostanie wywołana metoda `Merger.merge()`:

```python
{
    "investment_slug": str,
    "developer_slug": str,
    "name": str,
    "developer": str | None,
    "website": None,
    "sources": {"rp"|"oto"|"to": {...}},
    "location": {"coords": [lat|None, lng|None], "address": None, "city": None, "district": None},
    "specifications": {"delivery_date": None, "delivery_quarter": None, "delivery_year": None,
                       "units_count": None, "ceiling_height_min": None, "ceiling_height_max": None},
    "financials": {"price_min": None, "price_max": None, "price_avg": None,
                   "price_m2_min": None, "price_m2_max": None},
    "amenities": {"labels": [], "raw_codes": []},
    "image_urls": [],
    "images_count": 0,
    "image_paths": []
}

```

### 5.2 Strategia rozwiązywania konfliktów danych w Mergerze

W przypadku jednoczesnego występowania danych z wielu portali dla tej samej inwestycji, `Merger.merge()` stosuje następujące priorytety nadpisywania i scalania pól:

1. **Hierarchia ważności źródeł:** `RynekPierwotny (rp)` > `Otodom (oto)` > `TabelaOfert (to)` > `existing_data` (dane dotychczas zapisane).
2. **Sekcje `location` oraz `specifications`:** System uzupełnia brakujące (wartości `null`) pola z portali o niższym priorytecie, ale nigdy nie nadpisuje wartości pozyskanych ze źródła o wyższym priorytecie.
3. **Sekcja `financials`:** Ceny są uzupełniane z zachowaniem bezwzględnego pierwszeństwa danych pochodzących z platformy RynekPierwotny.
4. **Sekcja `amenities` (Udogodnienia):** Następuje wyliczenie sumy zbiorów unikalnych wartości zarówno dla tekstowych `labels`, jak i numerycznych kodów `raw_codes` ze wszystkich dostępnych źródeł portali.
5. **Sekcja `sources`:** System rygorystycznie dba o zachowanie historycznych i stałych identyfikatorów `vendor_id` oraz `agency_id` z `existing_data`.
6. **Sekcja `ratings` (Oceny i parametry jakościowe):** Pochodzą **wyłącznie** z plików `meta_*.json` (zasilanych przez system Coda). Dane z portali nie mają uprawnień do modyfikowania tej sekcji.

### 5.3 Pola historyczne monitorowane w `audit.history`

Po każdym uruchomieniu procedury merge system weryfikuje zmiany na wskazanych polach struktury inwestycji. Wykrycie modyfikacji skutkuje dopisaniem obiektu zmiany (z polami `field`, `old`, `new`) do tablicy historii audytowej:

* Ceny średnie, minimalne i maksymalne kwotowo oraz za m² (`financials.*`).
* Liczba lokali (`specifications.units_count`), wysokość sufitów (`ceiling_height`) oraz data oddania (`delivery_date`).
* Łączna liczba obrazów w galerii (`images_count`) oraz status inwestycji (`status`).

---

## 6. Standardy i reguły nazewnictwa plików galerii (`USI/`)

Zdjęcia i pliki binarne zapisywane w strukturze katalogów `{public_dir}/USI/{dev_slug}/{inv_slug}/` podlegają rygorystycznemu czyszczeniu nazw za pomocą funkcji `clean_filename(url)`. Pobieranie i zapis na dysku są pomijane, jeżeli plik lokalny istnieje i ma rozmiar większy niż 1 KB.

| Portal źródłowy | Format/Wzorzec wejściowego URL | Przetworzona nazwa pliku na dysku |
| --- | --- | --- |
| **Otodom CDN** | `.../v1/files/{hash}/image;s=800x600` | `{hash}.jpg` *(Uwaga: Pliki z Otodom są zawsze zapisywane i sprawdzane wewnętrznie jako format `.webp`)* |
| **TabelaOfert CDN** | `.../ID-photo-name.jpg` | `photo-name.jpg` |
| **RynekPierwotny / Inne** | Standardowy basename z adresu URL | Basename z bezwzględnie usuniętym sufiksem skrótu md5/hex `_[a-f0-9]{8}` |

---

## 7. Reguły spójności bazy i cross-referencji (Integracja danych)

### 7.1 Spójność wewnętrzna obiektów

* **Zasada tożsamości slugów:** Wartość `investment_slug` wewnątrz pliku JSON **musi** być w 100% identyczna z nazwą katalogu inwestycji na dysku. Wartość `developer_slug` wewnątrz pliku musi odpowiadać nazwie katalogu dewelopera.
* **Obsługa formatów historycznych (Inwestycje):** Podczas odczytu (`_load_investment()`) system implementuje strategię fallback. Wyszukiwanie pliku odbywa się w następującej sekwencji:
1. Nowy format bazujący na ID portalu: `usi_rp_*.json` → `usi_oto_*.json` → `usi_to_*.json`.
2. Formaty dziedziczone (legacy): `usi_{inv_slug}.json` → `usi_rp_{inv_slug}.json` → `usi_oto_{inv_slug}.json` → `usi_to_{inv_slug}.json`.
*Każdy ponowny zapis inwestycji wymusza konwersję do nowego formatu (`usi_{portal}_{portal_id}.json`). Czyszczenie starych plików realizuje skrypt `migrate_inv_filenames.py --apply`.*



### 7.2 Cross-reference (Wiązanie inwestycji z deweloperem)

Powiązanie inwestycji z odpowiednią kartą dewelopera w bazie danych odbywa się **wyłącznie na podstawie sztywnych identyfikatorów portali**. System nie stosuje metod heurystycznych, zgadywania nazw ani analizy tekstu. Dopasowanie zachodzi tylko wtedy, gdy spełniony jest jeden z poniższych warunków logicznych:

$$\text{investment.sources.rp.vendor\_id} \equiv \text{developer.portal\_mapping.rp.id}$$

$$\text{investment.sources.oto.agency\_id} \in \text{developer.portal\_mapping.oto.agency\_ids}$$

---

## 8. Zależności kolejnościowe (Typowy przepływ operacji)

Z uwagi na mechanizm rozwiązywania ścieżek `StorageResolver`, aplikacja kliencka operuje w trybie bezdyskowym na bazie UID. Kluczowe jest zachowanie poprawnej sekwencji uruchamiania procesów w systemie, ponieważ komponenty późniejsze wymagają struktur wygenerowanych w krokach wcześniejszych:

```
KROK 1: Inicjalizacja bazy deweloperów (Wymagane przed importem inwestycji)
   ├──► import_competitors_csv()  ──► Tworzy makiety profilów deweloperów (flagowane _mock)
   └──► download_raw_dev()        ──► Pobiera realne dane deweloperów i logotypy z portali
                                      (Buduje indeks powiązań ID -> dev_slug dla kroku 3)
                                      
KROK 2: Pobieranie surowych danych i obrazów inwestycji
   └──► process_batch() / download_raw() ──► Zapisuje raw_{portal}_{id}.json oraz zasoby w USI/

KROK 3: Import danych redakcyjnych i ocen jakościowych
   └──► import_usimaster_csv() ──► Tworzy pliki meta_{portal}_{id}.json. 
                                   (Wymaga bazy deweloperów z Kroku 1 do określenia dev_slug)

KROK 4: Generowanie rekordów zunifikowanych (Komponent zewnętrzny)
   └──► usi-tracker (Merger)   ──► Tworzy usi_{portal}_{portal_id}.json oraz app_result_*.json

KROK 5: Analiza powiązań i etapów inwestycji
   └──► run_stage_detection()  ──► Generuje stany usi_stage_stub.json na bazie analizy Kroku 4

```

---

## 9. Przewodnik diagnostyczny (Usuwanie niespójności)

| Objaw i problem | Narzędzie i polecenie naprawcze |
| --- | --- |
| Indeks jest nieaktualny, interfejs UI nie odzwierciedla zmian w strukturach plików JSON. | `python3 -m python_worker.main rebuild-index` |
| Baza zawiera przestarzałe pliki inwestycji nazwane od sluga zamiast od ID portalu. | `python3 -m python_worker.migrate_inv_filenames --data-dir /sciezka/USIdata --apply` |
| Liczba inwestycji na liście deweloperów nie zgadza się z widokiem szczegółowym (brakujące ID). | `python3 -m python_worker.backfill_inv_dev_ids.py --apply` |
| W bazie znajdują się stare pliki płaskie `usi_dev_{slug}.json` bez nadanych unikalnych sekwencji DEV-ID. | Uruchomienie skryptu inicjalizującego: `init-devs` lub `rebuild-devs`. |
| Jeden plik dewelopera zawiera zmapowanych wiele portali jednocześnie (naruszenie zasady Level 2). | `python3 -m python_worker.split_multi_portal_devs --apply` |
| Struktura dewelopera `portal_mapping` odwołuje się do nieistniejących fizycznie plików surowych `raw_*.json`. | `python3 -m python_worker.clean_portal_mappings --apply` |
| W bazie danych pozostały wiszące, uszkodzone referencje do usuniętych lub scalonych identyfikatorów DEV-ID. | `python3 -m python_worker.repair_stale_dev_refs --apply` |