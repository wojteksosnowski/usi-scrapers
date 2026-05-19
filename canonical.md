# Canonical — nazewnictwo plików, folderów i ich zawartości

Dokument opisuje wszystkie typy plików tworzonych przez `usi-scrapers`, konwencje nazewnicze,
zależności między nimi oraz źródła danych. Jest podstawą do utrzymania spójności bazy danych.

---

## Prefiksy portali

Każdy plik powiązany z portalem używa jednego z trzech prefiksów:

| Portal | Prefix w nazwie pliku | Identyfikator w `api.py` |
|---|---|---|
| RynekPierwotny | `rp` | `"rp"` |
| Otodom | `oto` | `"oto"` / `"otodom"` |
| TabelaOfert | `to` | `"to"` / `"tabelaofert"` |

---

## Struktura katalogów (od `public_dir`)

```
public_dir/
├── USI/                          # zdjęcia inwestycji
│   └── {dev_slug}/
│       └── {inv_slug}/
│           └── {filename.ext}
│
├── USIdata/                      # dane JSON inwestycji
│   └── {dev_slug}/
│       └── {inv_slug}/
│           ├── raw_{portal}_{id}.json
│           ├── raw_{portal}_{id}_{YYYYMMDD_HHMMSS}.json   ← archiwum
│           ├── meta_{portal}_{id}.json
│           ├── meta_{portal}_{id}_{YYYYMMDD_HHMMSS}.json  ← archiwum
│           ├── usi_stage_stub.json                        ← RP multi-etap
│           └── usi_{inv_slug}.json                        ← TYLKO usi-tracker
│
└── USIdev/                       # dane JSON deweloperów
    └── {dev_slug}/
        ├── raw_{portal}_{id}.json
        ├── raw_{portal}_{id}_{YYYYMMDD_HHMMSS}.json        ← archiwum
        └── logo_{portal}_{id}.{ext}
```

> `public_dir` pochodzi z `ScraperConfig.public_dir`. Symlink `Public/` w repozytorium to tylko narzędzie debug — nie używać w produkcji.

---

## Pliki danych inwestycji (`USIdata/`)

### `raw_{portal}_{id}.json`

**Ścieżka:** `{public_dir}/USIdata/{dev_slug}/{inv_slug}/raw_{portal}_{id}.json`

**Kluczowa zasada:** Pliki identyfikowane są WYŁĄCZNIE przez `portal_id`.
- **Otodom**: `ad.id` (numeryczny) LUB `ID{hash}` z URL (np. `ID6G8v`).
- **RynekPierwotny**: `offer_id` (numeryczny).
- **TabelaOfert**: `id` inwestycji (prefiksowane `i`, np. `i8982461`).

**Zawartość:** surowa odpowiedź portalu bez normalizacji — pełny JSON API RP, `pageProps` Otodom lub JSON-LD + ekstrakcja TabelaOfert. Każdy plik zawiera na początku sekcję `_usi_meta`:

```json
{
  "_usi_meta": {
    "portal": "rp",
    "portal_url": "https://rynekpierwotny.pl",
    "portal_id": "12345",
    "source_url": "https://rynekpierwotny.pl/oferty/...",
    "saved_at": "2026-05-17T10:00:00+00:00"
  },
  ...surowe dane portalu...
}
```

**Kto tworzy:**
- `utils/io.py → save_raw_json()` — wywołana przez:
  - `api.download_raw()` → per-portalowe `download_raw_*_json()`
  - `TechnicalDataManager.save_raw_data()` wewnątrz `process_batch()` — natychmiast po scrape'ie
  - `import_usimaster_csv()` — z kolumny `rpJSON` / `otoJSON` w CSV

**Zachowanie przy nadpisaniu:** istniejący plik jest najpierw przemianowany z suffixem `_{YYYYMMDD_HHMMSS}` (archiwum w tym samym katalogu), nowy plik trafia na oryginalną nazwę.

**`dev_slug` skąd pochodzi:** z pola `developer_slug` w zwróconym przez scraper słowniku. W przypadku `import_usimaster_csv` — z indeksu `USIdev` (patrz sekcja [Zależności](#zależności)).

---

### `meta_{portal}_{id}.json`

**Ścieżka:** `{public_dir}/USIdata/{dev_slug}/{inv_slug}/meta_{portal}_{id}.json`

**Zawartość:** dane redakcyjne z `USImaster-prep.csv` przypisane do konkretnego portalu. Pola:

| Klucz JSON | Kolumna CSV | Typ |
|---|---|---|
| `status` | `Ocena` | string |
| `Gwiazdki` | `Gwiazdki` | float |
| `Balkony` | `Balkony` | float |
| `Fasady` | `Fasady` | float |
| `Wnętrza` | `Wnętrza` | float |
| `Teren` | `Teren` | float |
| `Mieszkania` | `Mieszkania` | float |
| `Udogodnienia` | `Udogodnienia` | float |
| `komentarz` | `komentarz` | string |
| `Segment` | `Segment` | string |
| `ocenaLog` | `ocenaLOG` | float |
| `imgList` | `imgList` (podzielony) | string (ścieżki csv) |

**`imgList`** — lista ścieżek do zdjęć oddzielona przecinkami, np. `/USI/dev-slug/inv-slug/photo.jpg`. Jeden wiersz CSV może mieć jedno wspólne `imgList`; importer rozdziela je na `meta_rp_*` i `meta_oto_*` na podstawie dopasowania nazw plików do galerii z surowych JSONów. Ścieżki stale-ważne są korygowane przez `_fix_imglist_paths()`.

**Kto tworzy:** wyłącznie `import_usimaster_csv()` via `save_meta_json()`.

**Zachowanie przy nadpisaniu:** jak wyżej — archiwum z timestampem.

---

### `usi_stage_stub.json`

**Ścieżka:** `{public_dir}/USIdata/{dev_slug}/{inv_slug}/usi_stage_stub.json`

**Zawartość:** placeholder dla siostrzanego etapu inwestycji wieloetapowej RP, która nie została jeszcze zescrapowana. Pola:

```json
{
  "source": "rynekpierwotny.pl",
  "status": "stub",
  "groups_id": 123,
  "groups_name": "Osiedle ABC",
  "stage_id": 456,
  "stage_sort": 2,
  "stage_is_current": false,
  "offer_id": "67890",
  "name": "Osiedle ABC etap 2",
  "slug": "osiedle-abc-etap-2",
  "url": "https://rynekpierwotny.pl/oferty/...",
  "developer_slug": "dev-slug",
  "investment_slug": "osiedle-abc-etap-2",
  "created_at": "2026-05-17T10:00:00+00:00",
  "sibling_stage_folders": ["dev-slug/osiedle-abc-etap-1"]
}
```

**Kto tworzy:** `run_stage_detection()` w `utils/stage_detector.py` — wywoływany przez `usi-tracker`, nie przez API tego pakietu. Plik tworzony tylko gdy: (a) istniejący `app_result_*.json` ma dane RP multi-stage, (b) katalog siostrzanego etapu nie zawiera jeszcze `app_result_*.json`.

---

### `usi_{inv_slug}.json`

**Ścieżka:** `{public_dir}/USIdata/{dev_slug}/{inv_slug}/usi_{inv_slug}.json`

**Kto tworzy:** wyłącznie `usi-tracker`. Ten pakiet tylko zwraca ścieżkę przez `TechnicalDataManager.get_usi_json_path()`. Plik nie jest tworzony ani modyfikowany przez `usi-scrapers`.

---

## Pliki deweloperów (`USIdev/`)

### `raw_{portal}_{id}.json`

**Ścieżka:** `{public_dir}/USIdev/{dev_slug}/raw_{portal}_{id}.json`

**Zawartość:** surowy profil dewelopera z portalu + sekcja `_usi_meta` (jak w raw inwestycji, z dodatkiem `source_url`). Dla `import_competitors_csv` zawiera też flagę `"_mock": true` — dane z CSV, nie z portalu.

**Format per portal:**
- **RP:** pola z API vendora (`id`, `slug`, `name`, `logo`, ...)
- **OTO:** pola z `pageProps` agencji (`agency_id`, `agency_ids` — lista wszystkich ID, `name`, ...)
- **TO:** JSON-LD `Organization`/`LocalBusiness` + `<h1>` ze strony dewelopera

**Kto tworzy:**
- `save_dev_raw_json()` w `utils/io.py` — wywołana przez:
  - `api.download_raw_dev()` → per-portalowe `download_raw_*_dev_json()` (pobiera z portalu)
  - `import_competitors_csv()` (tworzy mock z pliku CSV)

**Zachowanie przy nadpisaniu:** jak wyżej — archiwum z timestampem.

**Kluczowe pola dla indeksu:**
- `raw_rp_{id}.json` → pole `id` (vendor_id RP, np. `"884"`)
- `raw_oto_{id}.json` → pole `agency_id` + tablica `agency_ids` (może mieć kilka ID Otodom na dewelopera)

---

### `logo_{portal}_{id}.{ext}`

**Ścieżka:** `{public_dir}/USIdev/{dev_slug}/logo_{portal}_{id}.{ext}`

**Przykład:** `USIdev/unidevelopment/logo_rp_955.png`

**Rozszerzenie:** pobrane z URL (`jpg`, `png`, `webp`); fallback `.jpg`.

**Kto tworzy:** `download_developer_logo()` w `utils/images.py` — jako efekt uboczny `download_raw_*_dev_json()`. Plik nie jest tworzony gdy portal nie zwraca logo. Pomijany jeśli istnieje plik > 1 KB.

**Źródło URL logo per portal:**
- RP: pola `logo`, `logo_url`, `image` (string lub `{"url": ...}`)
- Otodom: `advertiser.logoUrl`, `agency.logo.url`, `agency.logoUrl`; fallback shallow scan na `*logo*`
- TO: priorytet `og:image` meta tag, fallback `<img class/alt="logo">`

---

## Zdjęcia inwestycji (`USI/`)

**Ścieżka:** `{public_dir}/USI/{dev_slug}/{inv_slug}/{filename}`

**Kto tworzy:** `download_image()` / `save_images()` w `utils/images.py`, wywołane przez `TechnicalDataManager.sync_images()` wewnątrz `process_batch()`. Pomijane jeśli plik > 1 KB.

### Reguły nazewnictwa pliku — `clean_filename(url)`

| Portal | Wzorzec URL | Wynikowa nazwa pliku |
|---|---|---|
| Otodom CDN | `.../v1/files/{hash}/image;s=800x600` | `{hash}.jpg` |
| TabelaOfert CDN | `.../ID-photo-name.jpg` | `photo-name.jpg` |
| RP / inne | standardowy basename URL | basename z usuniętym suffixem `_[a-f0-9]{8}` |

Otodom zwraca zdjęcia jako `.webp` niezależnie od rozszerzenia w URL — `_oto_image_filenames()` w importerze uwzględnia obie nazwy przy weryfikacji `imgList`.

---

## Pliki archiwalne

Każdy plik `raw_*` i `meta_*` ma mechanizm archiwowania: przed nadpisaniem istniejący plik jest przemianowany do:

```
raw_{portal}_{id}_{YYYYMMDD_HHMMSS}.json
meta_{portal}_{id}_{YYYYMMDD_HHMMSS}.json
```

Archiwa pozostają w tym samym katalogu. Nie są automatycznie usuwane.

---

## Pliki referencyjne (`reference/`)

| Plik | Zawartość | Używany przez |
|---|---|---|
| `reference/konkurenci.csv` | lista konkurentów — kolumny: `Deweloper`, `rpSlug`, `rpID`, `otoSlug`, `otoID` | `import_competitors_csv()` |
| `reference/usimaster/USImaster-prep.csv` | dane redakcyjne inwestycji — kolumny: `rpJSON`, `otoJSON`, `imgList`, pola ocen | `import_usimaster_csv()` |
| `reference/usimaster/USImaster.csv` | pełna baza master (wersja readonly/export) | usi-tracker |
| `reference/usimaster/USImaster_skipped.csv` | wiersze odrzucone przez `import_usimaster_csv` (brak wpisu w USIdev) | diagnostyka |
| `reference/usimaster/missing_developers.csv` | deweloperzy bez wpisu w USIdev | diagnostyka |
| `reference/usimaster/oto_search_results.csv` | wyniki wyszukiwania Otodom | diagnostyka |

---

## Zależności między plikami

### 1. `import_usimaster_csv` → wymaga `USIdev`

Importer nie zna `dev_slug` z wiersza CSV — wyciąga go z indeksu `USIdev`:

```
USIdev/*/raw_rp_*.json  →  vendor["id"]  →  rp_index[vendor_id] = dev_slug
USIdev/*/raw_oto_*.json →  agency_ids[]  →  oto_index[agency_id] = dev_slug
```

Jeśli wpis brakuje → wiersz trafia do `USImaster_skipped.csv`. Dlatego **`import_competitors_csv` lub `download_raw_dev` musi być uruchomione przed `import_usimaster_csv`**.

### 2. `meta_{portal}_{inv_slug}.json` → wymaga `raw_{portal}_{inv_slug}.json`

`imgList` w meta pliku zawiera ścieżki do plików z `USI/`. Ścieżki są korygowane przez `_fix_imglist_paths()` na podstawie indeksu wszystkich plików w `USI/`. Jeśli zdjęcia nie zostały pobrane (`USI/` pusty), ścieżki mogą być błędne.

### 3. `usi_stage_stub.json` → wymaga `app_result_*.json` (z usi-tracker)

Stage detector (`run_stage_detection`) skanuje `USIdata/**/app_result_*.json` (pliki pisane przez usi-tracker) i tworzy stuby dla brakujących etapów. Nie działa bez wcześniejszego uruchomienia usi-tracker.

### 4. `raw_oto_{dev_slug}.json` → `agency_ids` musi być tablicą

Jeden deweloper może mieć wiele ID Otodom (różne kampanie). `import_competitors_csv` przy nadpisaniu istniejącego pliku dołącza nowe ID do tablicy `agency_ids` zamiast nadpisywać. Indeks `oto_index` w importerze iteruje po całej tablicy.

---

## Mapowanie: identifier → slug

Identyfikatory przekazywane do API różnią się per portal:

| Portal | `identifier` | Przykład |
|---|---|---|
| RP (deweloper) | vendor slug lub numeric ID | `"unidevelopment-955"` lub `"955"` |
| Otodom (deweloper) | agency numeric ID | `"10556359"` |
| TabelaOfert (deweloper) | developer slug | `"unidevelopment"` |
| RP (inwestycja) | numeric offer ID | `"12345"` |
| Otodom (inwestycja) | pełny URL `/pl/oferta/{slug}` | `"https://..."` |
| TO (inwestycja) | pełny URL + suffix `,i{id}` | `"https://...,i8982461"` |

URL inwestycji Otodom używa `/pl/oferta/{slug}` (nie `/pl/inwestycja/`) — potwierdzone na 2300+ rekordach produkcyjnych.

---

## Pole `_usi_meta` — struktura

Każdy plik `raw_*.json` zawiera na początku sekcję `_usi_meta` dodawaną przez `save_raw_json()` / `save_dev_raw_json()`:

```json
"_usi_meta": {
  "portal": "rp",                          // prefix portalu
  "portal_url": "https://rynekpierwotny.pl",
  "portal_id": "12345",                    // ID oferty/vendora w portalu (opcjonalne)
  "source_url": "https://...",             // URL źródłowy (tylko w raw dev)
  "saved_at": "2026-05-17T10:00:00+00:00" // UTC ISO 8601
}
```

Plik mock z `import_competitors_csv` zawiera dodatkowo `"_mock": true` bezpośrednio w danych (nie w `_usi_meta`).

---

## Kolejność operacji (typowy flow)

```
1. import_competitors_csv()          → USIdev/{dev_slug}/raw_{portal}_{dev_slug}.json (mock)
        ↓ lub
   download_raw_dev()                → USIdev/{dev_slug}/raw_{portal}_{dev_slug}.json (real)
                                     → USIdev/{dev_slug}/logo_{portal}_{dev_slug}.{ext}

2. process_batch() / download_raw()  → USIdata/{dev_slug}/{inv_slug}/raw_{portal}_{inv_slug}.json
                                     → USI/{dev_slug}/{inv_slug}/{filename}

3. import_usimaster_csv()            → USIdata/{dev_slug}/{inv_slug}/raw_{portal}_{inv_slug}.json
                                     → USIdata/{dev_slug}/{inv_slug}/meta_{portal}_{inv_slug}.json
   (wymaga USIdev z kroku 1)

4. usi-tracker (zewnętrzny)          → USIdata/{dev_slug}/{inv_slug}/app_result_*.json
                                     → USIdata/{dev_slug}/{inv_slug}/usi_{inv_slug}.json

5. run_stage_detection()             → USIdata/{dev_slug}/{inv_slug}/usi_stage_stub.json
   (wymaga app_result_* z kroku 4)
```
