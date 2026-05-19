# canonical.md — Nazewnictwo plików, struktura danych i zależności

Dokument opisuje **wszystkie konwencje nazewnicze**, struktury JSON i zależności
między plikami bazy danych USI Tracker. Stanowi jedyne źródło prawdy przy
weryfikacji spójności danych.

---

## 1. Katalogi główne

```
DROPBOX_PATH/
├── Public/
│   ├── USIdata/          ← USI_DATA_DIR   — dane inwestycji
│   ├── USI/              ← PUBLIC_USI_DIR — obrazy inwestycji
│   └── USIdev/           ← USI_DEV_DIR    — dane deweloperów
└── python_worker/
    └── data/
        ├── usi_counters.json    ← auto-increment ID
        └── wyrozniki.csv        ← tabela punktacji udogodnień
```

---

## 2. System identyfikatorów

Trzy sekwencje, współdzielące jeden plik `python_worker/data/usi_counters.json`:

| Prefiks   | Klucz w JSON | Przykład    | Zastosowanie                          |
|-----------|--------------|-------------|---------------------------------------|
| `DEV-`    | `"dev"`      | `DEV-26702` | Rekord dewelopera (Level 2)           |
| `INV-`    | `"inv"`      | `INV-00042` | Rekord inwestycji (zarezerwowane)     |
| `DM-`     | `"dm"`       | `DM-0492`   | Rekord scalenia deweloperów (Level 3) |

Format: `PREFIX-NNNNN` — zero-padded, minimum 4 cyfry.

Zapis atomowy: `threading.Lock()` (wątki) + `fcntl.flock()` (procesy).

```json
// usi_counters.json
{ "dev": 28504, "inv": 28714, "dm": 506 }
```

---

## 3. Slugifikacja

Slugifikacja jest tylko narzedziem pomocniczym. Nigdy nie mozna uzywać tego mechanizmu to odnajdywania sciezek czy identyfikacji rekordow.

Moduł: `python_worker/slug_utils.py` → `slugify(text)`

Algorytm (kolejność ważna):
1. Zamień `ł → l`, `Ł → L` (NFKD nie obsługuje polskiej kreski)
2. NFKD normalizacja
3. Usuń znaki non-ASCII
4. Zamień `[^a-z0-9]+` → `-`
5. Strip `-` z początku i końca
6. Lowercase

Slug jest **immutable** po pierwszym zapisie — nigdy nie modyfikuj slug istniejącego
rekordu. Slug RP/Otodom z portalu przepisywany dosłownie, bez przetransformowania
przez `slugify`.

---

## 4. Inwestycje — USIdata

### 4.1 Struktura katalogów

```
USIdata/
├── _index.json                              ← globalny indeks (computed)
└── {developer_slug}/
    └── {investment_slug}/
        ├── usi_{portal}_{portal_id}.json               ← CANONICAL (czytaj/pisz tu)
        ├── raw_{portal}_{portal_id}.json            ← surowe dane z portalu (immutable)
        ├── raw_{portal}_{portal_id}_YYYYMMDD_HHMMSS.json  ← archiwum (immutable)
        ├── meta_{portal}_{portal_id}.json           ← zaimportowane oceny z Coda
        ├── meta_{portal}_{portal_id}_YYYYMMDD_HHMMSS.json
        └── processing_log_{investment_slug}.txt     ← dziennik zdarzeń (append-only)
```

**Reguły nazewnicze:**
- `developer_slug` = katalog dewelopera w USIdata, **musi** odpowiadać `developer_slug`
  w pliku `usi_dev_*.json`
- `investment_slug` = katalog inwestycji, **musi** odpowiadać `investment_slug` wewnątrz
  pliku `usi_*.json`
- `portal` = skrot odpowiedni danemu portalowi `rp`, `oto`, `to`.
- `portal_id` = unikalne ID uzyskane z surowego json ze strony rynekpierwotny, otodom, tabelaofert właściwe danemu portalowi.
- Timestamp w nazwie archiwum: `YYYYMMDD_HHMMSS` (czas lokalny, bez strefy)

**Stare formaty (legacy — tylko odczyt):**

Po migracji `migrate_inv_filenames.py` (maj 2026) wszystkie pliki mają nowy format.
Dla folderów bez ID portalu (`sources` puste) pozostaje stary format jako fallback.

`_load_investment()` szuka pliku w kolejności:
1. `usi_rp_*.json` (glob) → `usi_oto_*.json` → `usi_to_*.json`  ← nowy format
2. `usi_{inv_slug}.json` → `usi_rp_{inv_slug}.json` → `usi_oto_{inv_slug}.json` → `usi_to_{inv_slug}.json`  ← legacy

Przy każdym kolejnym zapisie (Merger, `update_investment`) plik wychodzi jako
`usi_{portal}_{portal_id}.json`. Stary plik nie jest usuwany automatycznie —
do oczyszczenia służy `migrate_inv_filenames.py`.

---

### 4.2 usi_{portal}_{portal_id}.json — unified record

Budowany przez `Merger.merge()` z `python_worker/adapters/merger.py`.

```json
{
  "investment_slug": "szalasa-3-warszawa-tarchomin",
  "developer_slug": "022-investments",
  "name": "Szalasa 3",
  "developer": "022 INVESTMENTS",
  "website": null,
  "status": "Wstępna",
  "segment": "mieszkania deweloperskie",

  "sources": {
    "rp": {
      "id": "14563",
      "url": "https://rynekpierwotny.pl/oferty/022-investments/szalasa-3-...-14563/",
      "vendor_id": "10788"
    },
    "oto": {
      "url": "https://www.otodom.pl/pl/oferta/...-ID4lulo",
      "id": "ID4lulo",
      "agency_id": "9867181"
    },
    "to": {
      "id": "i123456",
      "url": "https://tabelaofert.pl/...,i123456"
    }
  },

  "location": {
    "coords": [52.2245, 20.9967],
    "address": "ul. Szalasa 3",
    "city": "Warszawa",
    "district": "Tarchomin"
  },

  "specifications": {
    "delivery_date": "2025-Q3",
    "delivery_quarter": 3,
    "delivery_year": 2025,
    "units_count": 108,
    "ceiling_height": 2.70
  },

  "financials": {
    "price_min": 480000.0,
    "price_max": 1100000.0,
    "price_avg": 690000.0,
    "price_m2_min": 8990.0,
    "price_m2_max": 14500.0
  },

  "amenities": {
    "labels": ["Parking podziemny", "Plac zabaw", "Monitoring"],
    "raw_codes": [101, 205, 312]
  },

  "ratings": {
    "status": "Wstępna",
    "Gwiazdki": null,
    "Balkony": 1.0,
    "Fasady": 0.0,
    "Wnętrza": null,
    "Teren": 1.0,
    "Mieszkania": 0.0,
    "Udogodnienia": 1.0,
    "komentarz": null,
    "Segment": "mieszkania deweloperskie",
    "ocenaLog": 0.71,
    "imgList": "/Public/USI/022-investments/szalasa-3-warszawa-tarchomin/szalasa-3_6df205.png"
  },

  "images_count": 12,
  "image_paths": ["/Public/USI/022-investments/szalasa-3-warszawa-tarchomin/szalasa-3_6df205.png"],
  "image_urls": [],

  "usi_inv_id": null,
  "usi_dev_id": null,

  "audit": {
    "created_at": "2024-03-15T10:22:01.123456",
    "updated_at": "2026-05-16T18:44:12.789012",
    "history": [
      {
        "timestamp": "2024-03-15T10:22:01.123456",
        "event": "Created",
        "changes": []
      },
      {
        "timestamp": "2026-05-16T18:44:12.789012",
        "event": "Sync: RP (local)",
        "changes": [
          { "field": "financials.price_avg", "old": 650000.0, "new": 690000.0 }
        ]
      }
    ]
  }
}
```

**Pole `sources` — klucz do łączenia z deweloperem:**

| Portal | Klucz ID w `sources` | Odpowiednik w `portal_mapping` dewelopera |
|--------|-----------------------|-------------------------------------------|
| `rp`   | `vendor_id`           | `portal_mapping.rp.id`                    |
| `oto`  | `agency_id`           | `portal_mapping.oto.agency_id` / `agency_ids[]` |
| `to`   | `klient_id`           | `portal_mapping.to.id`                    |

Filtr `_inv_matches_dev(inv, dev)` — tylko te pola decydują o przypisaniu inwestycji
do dewelopera. Brak ID = brak dopasowania (zero guessingu).

**Pole `image_paths`** zawiera dokładne ścieżki zapisane przez scraper.
Nigdy nie rekonstruuj tych ścieżek z nazwy katalogu — używaj wyłącznie wartości
z pliku.

---

### 4.3 raw_{portal}_{portal_id}.json — surowe dane portalu

Pliki **immutable** po pobraniu. Jedyne operacje dozwolone: odczyt i archiwizacja
(kopia z timestampem). Nigdy nie nadpisuj istniejącego `raw_*.json` w miejscu.

**Struktura raw_rp_{portal_id}.json** (odpowiedź API RynekPierwotny):

Wartości skalarne są opakowane w `{"type": "val"|"obj"|"arr", "value": ...}`.
Do odczytu używaj `adapters._get_val(data, key)`.

```json
{
  "id": "11939",
  "name": {"type": "val", "value": "Falista 168"},
  "address": "Łódź, ...",
  "geo_point": {"type": "obj", "value": {"coordinates": {"type": "arr", "value": [19.407, 51.773]}}},
  "vendor": {"type": "obj", "value": {"id": 1190, "name": "Ezbud Sp. z o.o.", "slug": "ezbud-sp-z-o-o"}},
  "construction_date_range": {"type": "obj", "value": {"upper": "2025-06-30"}},
  "properties": 38,
  "stats": {
    "ranges_price_min": 420994.0,
    "ranges_price_max": 1083405.0,
    "ranges_price_m2_min": 8990.0,
    "ranges_price_m2_max": 15240.0,
    "ranges_height_max": 280
  },
  "features": [{"id": "101"}, {"id": "205"}],
  "main_image": {"m_img_1500": "URL", "m_img_500": "URL"},
  "_raw_gallery": {"gallery": [{"image": {"g_img_2000": "URL", "g_img_1500": "URL"}}]}
}
```

Uwaga na `geo_point`: kolejność to `[longitude, latitude]` (GeoJSON) — odwrotna
niż `coords: [lat, lng]` w schemacie unified.

**Struktura raw_oto_{portal_id}.json** (Next.js `__NEXT_DATA__` z Otodom):

```json
{
  "ad": {
    "id": "64819756",
    "title": "Nazwa projektu",
    "url": "https://www.otodom.pl/pl/oferta/...-ID4lulo",
    "images": [{"large": "URL"}],
    "location": {
      "coordinates": {"latitude": 52.123, "longitude": 16.789},
      "address": {
        "street": {"name": "Ulica", "number": "10"},
        "city": {"name": "Warszawa"},
        "district": {"name": "Śródmieście"}
      }
    },
    "agency": {"id": "9867181", "name": "Nazwa dewelopera"},
    "topInformation": [
      {"label": "project_finish_date", "values": ["2025-03"]},
      {"label": "number_of_units_in_project", "values": ["45"]}
    ]
  }
}
```

**Struktura raw_to_{portal_id}.json** (TabelaOfert — JSON-LD + ekstrakcja):

```json
{
  "name": "Nazwa projektu",
  "url": "https://tabelaofert.pl/...,i123456",
  "brand": {"name": "Nazwa dewelopera"},
  "offers": {"lowPrice": 500000.0, "highPrice": 2000000.0},
  "additionalProperty": [{"name": "Parking podziemny"}],
  "_raw_gallery_urls": ["URL1", "URL2"],
  "_extracted_location": {
    "latitude": 52.123, "longitude": 16.789,
    "address": "ul. Proba 5", "city": "Kraków"
  }
}
```

---

### 4.4 meta_{portal}_{portal_id}.json — oceny z Coda

Źródło: Coda.io pack (tylko zapis z Cody do pliku, nie edytuj ręcznie).
Zachowywane przez Merger przy każdym rebuild — `existing_data.ratings` nie jest
nadpisywane przez dane z portali.

```json
{
  "status": "Wstępna",
  "Gwiazdki": null,
  "Balkony": 1.0,
  "Fasady": 0.0,
  "Wnętrza": null,
  "Teren": 1.0,
  "Mieszkania": 0.0,
  "Udogodnienia": 1.0,
  "komentarz": null,
  "Segment": "mieszkania deweloperskie",
  "ocenaLog": 0.71,
  "source": "rp",
  "id": "123456",
  "imgList": "/Public/USI/dev-slug/inv-slug/img_abc123.png, ..."
}
```

---

### 4.5 processing_log_{investment_slug}.txt — dziennik inwestycji

Format: jedna linia na zdarzenie, plain text.

```
[2026-05-16T18:44:12.789012] 022-investments/szalasa-3-warszawa-tarchomin - Sync: RP (local)
```

---

### 4.6 _index.json — globalny indeks inwestycji

Plik computed — generowany przez `python3 -m python_worker.main rebuild-index`.
Nigdy nie edytuj ręcznie. Używany przez UI jako fast-path przy listowaniu.

```json
{
  "built_at": "2026-05-16T20:00:00.000000",
  "count": 6924,
  "entries": [
    {
      "slug": "022-investments/szalasa-3-warszawa-tarchomin",
      "developer_slug": "022-investments",
      "investment_slug": "szalasa-3-warszawa-tarchomin",
      "name": "Szalasa 3",
      "developer": "022 INVESTMENTS",
      "city": "Warszawa",
      "district": "Tarchomin",
      "source": "RP",
      "source_url": "https://rynekpierwotny.pl/...",
      "source_links": [{"source": "RP", "url": "..."}, {"source": "OTO", "url": "..."}],
      "price_avg": 690000.0,
      "price_min": 480000.0,
      "price_max": 1100000.0,
      "price_m2_min": 8990.0,
      "price_m2_max": 14500.0,
      "units": 108,
      "delivery": "2025-Q3",
      "status": "Wstępna",
      "amenities": ["Parking podziemny", "Plac zabaw"],
      "amenities_score": 12,
      "amenities_matched": [{"label": "Parking podziemny", "hm_udo": 8}],
      "suggested_udogodnienia": 3,
      "coords": [52.2245, 20.9967],
      "photos": ["/api/image/022-investments/szalasa-3-warszawa-tarchomin/szalasa-3_6df205.png"],
      "usi_inv_id": null,
      "usi_dev_id": null,
      "ratings": {"status": "Wstępna", "Gwiazdki": null, "ocenaLog": 0.71},
      "comment": null,
      "photos_to_delete": 0,
      "folder_path": "/Volumes/.../USIdata/022-investments/szalasa-3-warszawa-tarchomin",
      "website": ""
    }
  ]
}
```

Po każdej zmianie struktury danych uruchom:
```
python3 -m python_worker.main rebuild-index
```

---

## 5. Deweloperzy — USIdev

### 5.1 Trójpoziomowa hierarchia plików

```
USIdev/
└── {developer_slug}/
    ├── usi_dev_{DEV-ID}_{developer_slug}.json   ← Level 2 — rekord portalu (1 per portal)
    ├── usi_dev_{DEV-ID}_{developer_slug}.json   ← Level 2 — drugi portal (ten sam slug, inny DEV-ID)
    ├── dev_master_{DM-ID}.json                  ← Level 3 — rekord scalenia (opcjonalny)
    ├── dev_log_{developer_slug}.txt             ← dziennik zdarzeń (append-only JSONL)
    ├── raw_rp_{portal_id}.json                  ← surowe dane RP (immutable)
    ├── raw_oto_{portal_id}.json                 ← surowe dane Otodom (immutable)
    ├── raw_to_{portal_id}.json                  ← surowe dane TabelaOfert (immutable)
    └── discovery.json                           ← wyniki ostatniego discovery (computed)
```

**Reguła 1:1:** Jeden `usi_dev_*.json` = dokładnie jeden portal w `portal_mapping`.
Dwie karty (`rp` + `oto`) dla tego samego dewelopera = dwa osobne pliki z dwoma DEV-ID.

**Priorytet wyszukiwania pliku (developer_manager.py):**
1. Nowy format z ID: `USIdev/{slug}/usi_dev_*_{slug}.json` (glob, sortowane)
2. Stary format canonical: `USIdev/{slug}/usi_dev_{slug}.json`
3. Legacy flat: `USIdev/usi_dev_{slug}.json`

---

### 5.2 usi_dev_{DEV-ID}_{developer_slug}.json — Level 2

```json
{
  "developer_slug": "ezbud-sp-z-oo-spk",
  "name": "\"Ezbud\" Sp. z o.o. Sp.k.",
  "usi_dev_id": "DEV-26702",

  "portal_mapping": {
    "rp": {
      "id": "1190",
      "slug": "ezbud-sp-z-oo-spk"
    },
    "oto": null,
    "to": null
  },

  "metadata": {},

  "suggestions": [
    {
      "usi_dev_id": "DEV-26700",
      "developer_slug": "ezbud",
      "reason": "Identyczna znormalizowana nazwa",
      "score": 0.97
    }
  ],

  "crawler": {
    "next_visit": "2026-05-30T14:18:47Z"
  },

  "parent_id": null,
  "master_id": "DM-0492",

  "audit": {
    "created_at": "2026-05-17T01:45:30.655718",
    "updated_at": "2026-05-17T14:46:11.800360"
  }
}
```

**Pola Level 3 — NIE przechowywane w Level 2:**
- `merged_from` → w `dev_master_*.json`
- `events` → w `dev_log_*.txt`

Po odczycie przez `get_developer()` lub `get_developer_by_id()`, do zwracanego
obiektu dołączane jest `merged_from` z pliku Level 3 (jeśli `parent_id` jest null).

**Pole `portal_mapping`:**

| Portal | Zawartość                                                              |
|--------|------------------------------------------------------------------------|
| `rp`   | `{"id": "1190", "slug": "ezbud-sp-z-o-o"}` — vendor ID (string)       |
| `oto`  | `{"agency_id": "9867181", "agency_ids": ["9867181", "8083158"]}`       |
| `to`   | `{"slug": "ezbud-sp-z-o-o"}` — slug TabelaOfert                       |

Pola null oznaczają brak konta dewelopera na danym portalu.

**`parent_id`** — ustawiane po scaleniu (merge): child.`parent_id` = target.`usi_dev_id`.
Rekordy z `parent_id != null` są ukryte w listach — `list_developers()` je filtruje.

**`master_id`** — odsyłacz do pliku Level 3 (`dev_master_{DM-ID}.json`).

---

### 5.3 dev_master_{DM-ID}.json — Level 3

Tworzony automatycznie przez `merge_developers()`. Żyje w katalogu `{target_slug}/`.

```json
{
  "dev_master_id": "DM-0492",
  "master_usi_dev_id": "DEV-26702",
  "master_slug": "ezbud-sp-z-oo-spk",

  "merged_from": [
    {
      "slug": "ezbud",
      "name": "EZBUD",
      "usi_dev_id": "DEV-26700",
      "merged_at": "2026-05-17T14:46:11.799505"
    }
  ],

  "dismissed": [
    {
      "usi_dev_id": "DEV-12345",
      "slug": "ezbud-holdings",
      "dismissed_at": "2026-05-10T09:00:00.000000"
    }
  ]
}
```

---

### 5.4 raw_{portal}_{portal_id}.json — profil portalu

Odpowiednik `raw_*.json` inwestycji, ale dla dewelopera.
**Nazewnictwo:** `raw_{portal}_{portal_id}.json` (jeśli ID portalu jest znane) lub `raw_{portal}_{slug}.json` (legacy/fallback).

**Archiwum:**
`raw_{portal}_{id}_{YYYYMMDD_HHMMSS}.json` (kopia z timestampem). Nigdy nie nadpisuj istniejącego `raw_*.json` w miejscu.

```json
{
  "_usi_meta": {"portal": "rp"},
  "id": "1190",
  "slug": "ezbud-sp-z-oo-spk",
  "_mock": true
}
```

Po prawdziwym crawlu `update-dev` nadpisuje plik pełną odpowiedzią portalu,
flaga `_mock` znika.

---

### 5.5 dev_log_{developer_slug}.txt — dziennik dewelopera

Format JSONL (jedna linia = jeden obiekt JSON).

```json
{"at": "2026-05-17T14:46:11.799754", "type": "merge_in", "source_slug": "ezbud", "source_name": "EZBUD"}
{"at": "2026-05-16T21:43:10.374455", "type": "discover", "by": "user", "found": 1}
{"at": "2026-05-10T09:00:00.000000", "type": "dismiss_suggestion", "dismissed_slug": "ezbud-holdings", "dismissed_id": "DEV-12345"}
```

Typy zdarzeń: `merge_in`, `unmerge`, `discover`, `dismiss_suggestion`.

---

### 5.6 discovery.json — wyniki discovery

Computed przez `DiscoveryService`. Niemodyfikuj ręcznie.

```json
{
  "dev_slug": "ezbud-sp-z-oo-spk",
  "checked_at": "2026-05-16T21:43:10.369145",
  "items": [
    {
      "id": "14287",
      "url": "https://rynekpierwotny.pl/oferty/.../wolczanska-248-...-14287/",
      "is_new": true,
      "registered": false,
      "portal": "rp"
    }
  ]
}
```

---

## 6. Obrazy — Public/USI

```
USI/
└── {developer_slug}/
    └── {investment_slug}/
        └── {image_filename}
```

Konwencja nazw plików obrazów (generowana przez scraper):

```
{project-slug}_{hash6}.{ext}
{project-slug}-{descriptor}_{hash6}.{ext}
```

Przykład: `szalasa-3_6df205.png`, `szalasa-3-zdjecie-inwestycji_d2057f.png`

W polu `image_paths` usi_*.json ścieżki zaczynają się od `/Public/USI/`.
W API endpoint `/api/image/{dev_slug}/{inv_slug}/{filename}` mapa na fizyczną ścieżkę.

---

## 7. Zależności między plikami — diagram przepływu

```
Portal RP API                Portal Otodom               Portal TabelaOfert
       │                           │                              │
       ▼                           ▼                              ▼
raw_rp_{portal_id}.json    raw_oto_{portal_id}.json    raw_to_{portal_id}.json
  (immutable)               (immutable)                  (immutable)
       │                           │                              │
       └───────────────────────────┴──────────────────────────────┘
                                   │
                              RPAdapter /
                            OtodomAdapter /
                             TOAdapter
                            (adapters/__init__.py)
                                   │
                                   ▼
                            Merger.merge()
                           (adapters/merger.py)
                                   │
                      ┌────────────┴────────────┐
                      │                         │
                      ▼                         ▼
            usi_{portal}_{portal_id}.json        meta_{portal}_{portal_id}.json
            (canonical, czyta UI)       (z Cody — tylko ratings,
                      │                  nie nadpisywane przez merge)
                      ▼
              _index.json (rebuilt)
```

```
Konkurenci.csv / Portal scrape
          │
          ▼
raw_{portal}_{dev_slug}.json (immutable)
          │
          ▼
_build_dev_from_raws()
          │
          ▼
usi_dev_{DEV-ID}_{dev_slug}.json  ←── create_developer_file()
          │                              (Level 2, 1 per portal)
          │                         ┌───┤ parent_id → ukryty w listach
          │                         │   └ master_id → wskaźnik na Level 3
          └────── merge_developers() ────────────┐
                                                  ▼
                                    dev_master_{DM-ID}.json
                                    (Level 3 — merged_from[])
```

---

## 8. Reguły spójności bazy

### 8.1 Inwestycje

| Reguła | Szczegół |
|--------|----------|
| Slug ≡ katalog | `investment_slug` w pliku = nazwa katalogu nadrzędnego |
| Slug dewelopera ≡ ścieżka | `developer_slug` w pliku = katalog w USIdata |
| `sources.rp.vendor_id` | musi odpowiadać `portal_mapping.rp.id` dewelopera |
| `sources.oto.agency_id` | musi być w `portal_mapping.oto.agency_ids[]` dewelopera |
| `image_paths` | dokładne ścieżki z scrapera — nie rekonstruuj |
| `raw_*` są immutable | nigdy nie edytuj po pobraniu |
| canonical = `usi_{portal}_{portal_id}.json` | np. `usi_rp_14563.json`, `usi_oto_ID4lulo.json` — jeden plik per inwestycja, nazwany po ID portalu |
| legacy (tylko odczyt) | `usi_{inv_slug}.json`, `usi_rp_{inv_slug}.json`, `usi_oto_{inv_slug}.json` — `_load_investment()` obsługuje kolejność: nowy format (rp→oto→to) → legacy slug |

### 8.2 Deweloperzy

| Reguła | Szczegół |
|--------|----------|
| 1 plik = 1 portal | `portal_mapping` ma dokładnie jeden klucz `rp`, `oto` lub `to` z wartością (pozostałe null) |
| Różne portale → różne DEV-ID | Ten sam `developer_slug`, ale każdy portal = osobny `usi_dev_*.json` |
| `parent_id != null` → ukryty | Rekordy child nie pojawiają się w `/api/developers` |
| `merged_from` → tylko Level 3 | Nigdy nie zapisuj `merged_from` bezpośrednio w Level 2 |
| `portal_mapping` rebuilded z raw | `_build_dev_from_raws()` zawsze wygrywa — nie pisz `portal_mapping` ręcznie |

### 8.3 Cross-reference inwestycja ↔ deweloper

Dopasowanie odbywa się wyłącznie przez ID portalu (zero guessingu):

```
investment.sources.rp.vendor_id  ==  developer.portal_mapping.rp.id
investment.sources.oto.agency_id  ∈  developer.portal_mapping.oto.agency_ids
investment.sources.to.klient_id  ==  developer.portal_mapping.to.id
```

Inwestycja "wie" do którego dewelopera nalezy. 

---

## 9. Transformacja danych: Adaptery i Merger

### 9.1 Unified base — schemat wejściowy Mergera

Każdy adapter (`RPAdapter`, `OtodomAdapter`, `TOAdapter`) produkuje dict w tym
samym formacie przed przekazaniem do `Merger.merge()`:

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
                       "units_count": None, "ceiling_height": None},
    "financials": {"price_min": None, "price_max": None, "price_avg": None,
                   "price_m2_min": None, "price_m2_max": None},
    "amenities": {"labels": [], "raw_codes": []},
    "image_urls": [],
    "images_count": 0,
    "image_paths": []
}
```

### 9.2 Merger — priorytety przy konflikcie danych

```
Dane bazowe:    rp_data  >  oto_data  >  to_data  >  existing_data
location:       uzupełnij brakujące pola (nie nadpisuj)
specifications: uzupełnij brakujące pola
financials:     uzupełnij brakujące pola (RP ma pierwszeństwo)
amenities:      suma zbiorów (labels + raw_codes)
image_urls:     deduplikacja + sort
sources:        zachowaj vendor_id / agency_id z existing_data
ratings:        wyłącznie z meta_*.json (Coda) — portale nie dostarczają
```

### 9.3 Pola trackowane w `audit.history`

Merger porównuje te pola po każdym merge i dopisuje do historii gdy się zmieniły:
`financials.price_avg`, `financials.price_min`, `financials.price_max`,
`financials.price_m2_min`, `financials.price_m2_max`,
`specifications.units_count`, `specifications.ceiling_height`, `specifications.delivery_date`,
`images_count`, `status`.

---

## 10. Identyfikatory portali

### RynekPierwotny (rp)

| Element | Wartość / Wzorzec |
|---------|-------------------|
| Vendor ID (deweloper) | liczba, np. `"1190"` |
| Offer ID (inwestycja) | liczba, np. `"11939"` |
| URL dewelopera | `https://rynekpierwotny.pl/oferty/{vendor-slug}/` |
| URL inwestycji | `https://rynekpierwotny.pl/oferty/{vendor-slug}/{offer-slug}-{offer-id}/` |
| Uwaga | `geo_point.coordinates` = `[lng, lat]` (GeoJSON), odwrotnie niż `coords: [lat, lng]` |
| Uwaga | Wartości skalarne opakowane: `{"type": "val", "value": X}` — używaj `_get_val()` |

### Otodom (oto)

| Element | Wartość / Wzorzec |
|---------|-------------------|
| Agency ID (deweloper) | liczba, np. `"9867181"` |
| `agency_ids[]` | lista wszystkich znanych ID (otoID zmienia się bez ostrzeżenia) |
| URL hash | sufiks `-ID{hash}` w URL inwestycji |
| URL inwestycji | `https://www.otodom.pl/pl/oferta/{slug}-ID{hash}/` |
| Uwaga | otoID jest niestabilny — `USIfolder` (inv_slug) jest jedynym pewnym kluczem |

### TabelaOfert (to)

| Element | Wartość / Wzorzec |
|---------|-------------------|
| Offer ID | liczba w URL: `...,i{id}` |
| URL inwestycji | `https://tabelaofert.pl/...,i123456` |
| ID dewelopera | `klient_id` — pobierane z meta tagu `klient-id` lub Next.js |

Dopasowanie realizowane jest przez unikalny `klient_id`. Powiązane śledztwo w kluczu `$.brand.logo` może stanowić dodatkową weryfikację.

---

## 11. Pliki pomocnicze

### wyrozniki.csv — punktacja udogodnień

```
Label,RPno,USIudo
Parking podziemny,101,8
Plac zabaw,205,4
Monitoring,312,2
```

Używana przez `_compute_amenity_score()` w `api/utils.py`:
- Dopasowanie po `RPno` (z `raw_codes`) lub przez substring `Label` (z `labels`)
- Suma `USIudo` → `amenities_score` → `suggested_udogodnienia` (tier 1–4)

### usi_counters.json — liczniki ID

```json
{"dev": 28504, "inv": 28714, "dm": 506}
```

Modyfikuj wyłącznie przez `DeveloperManager.generate_usi_id()` — zapis atomowy
z file lock.

---

## 12. Stany niespójności i jak je naprawić

| Objaw | Polecenie naprawy |
|-------|-------------------|
| Lista dew. pokazuje liczbę, widok dew. — 0 inwestycji | `backfill_inv_dev_ids.py --apply` (uzupełnia brakujące `vendor_id`/`agency_id`) |
| Stary flat plik `usi_dev_{slug}.json` bez DEV-ID | `init-devs` lub `rebuild-devs` — usuwa stary format automatycznie |
| `portal_mapping` z wieloma portalami w jednym pliku | `python3 -m python_worker.split_multi_portal_devs --apply` |
| Puste `merged_from` po merge w widoku UI | — (naprawione: `get_developer_by_id` teraz wzbogaca z Level 3) |
| Stałe referencje do usuniętych DEV-ID | `python3 -m python_worker.repair_stale_dev_refs --apply` |
| `portal_mapping` wskazuje na nieistniejący raw_*.json | `python3 -m python_worker.clean_portal_mappings --apply` |
| Nieaktualny `_index.json` | `python3 -m python_worker.main rebuild-index` |
| Pliki `usi_{slug}.json` w starym formacie | `python3 -m python_worker.migrate_inv_filenames --data-dir /path/USIdata` (dry-run), `--apply` do wykonania |
