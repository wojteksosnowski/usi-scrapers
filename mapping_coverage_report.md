# Raport z Głębokiego Testu Pokrycia Mapowania API

## Portal: RynekPierwotny (rp)
**Przetestowane pliki (4):** raw_rp_17812.json, raw_rp_19840.json, raw_rp_571.json, raw_rp_955.json

### Obiekt: `investment`
- Razem kluczy: **27**
- W pełni pokryte: **5**
- Częściowo pokryte: **16**
- Całkowity brak pokrycia: **5**

#### Brakujące klucze (MISSING)
- `gallery`
- `groups`
- `groups_id`
- `groups_name`
- `groups_stages`

#### Szczegóły ekstrakcji (Różnice w zapisie / Częściowe pokrycie)
**🟢 `id`** (Sukcesy: 4, Błędy: 0)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 17812`
  - `raw_rp_19840.json`: `[int] 19840`
  - `raw_rp_571.json`: `[int] 571`

**🟢 `slug`** (Sukcesy: 4, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_rp_17812.json`: `[str] akacjowa-wita-krakow-pradnik-czerwony`
  - `raw_rp_19840.json`: `[str] apartamenty-beethovena-etap-2-apartamenty-inwestycyjne-warszawa-sielce`
  - `raw_rp_571.json`: `[str] awiator-gdansk-zaspa-rozstaje`

**🟢 `name`** (Sukcesy: 4, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_rp_17812.json`: `[str] Akacjowa Wita`
  - `raw_rp_19840.json`: `[str] Apartamenty Beethovena etap 2 - apartamenty inwestycyjne`
  - `raw_rp_571.json`: `[str] Awiator`

**🟡 `developer_id`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 1084`
  - `raw_rp_19840.json`: `[int] 955`
  - `raw_rp_571.json`: `[int] 885`

**🟡 `developer_slug`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_rp_17812.json`: `[str] atal-sa`
  - `raw_rp_19840.json`: `[str] dom-development-sa`
  - `raw_rp_571.json`: `[str] allcon-osiedla-sp-z-oo`

**🟡 `developer_name`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_rp_17812.json`: `[str] ATAL S.A.`
  - `raw_rp_19840.json`: `[str] Dom Development S.A.`
  - `raw_rp_571.json`: `[str] ALLCON`

**🟢 `units_count`** (Sukcesy: 4, Błędy: 0)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 66`
  - `raw_rp_19840.json`: `[int] 11`
  - `raw_rp_571.json`: `[int] 0`

**🟡 `price_min`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 655386`
  - `raw_rp_19840.json`: `[int] 588468`
  - `raw_rp_571.json`: `[int] 300230`

**🟡 `price_max`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 1036788`
  - `raw_rp_19840.json`: `[int] 1357334`
  - `raw_rp_571.json`: `[int] 569710`

**🟡 `price_m2_min`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 12744`
  - `raw_rp_19840.json`: `[int] 20600`
  - `raw_rp_571.json`: `[int] 6156`

**🟡 `price_m2_max`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 17072`
  - `raw_rp_19840.json`: `[int] 22800`
  - `raw_rp_571.json`: `[int] 8856`

**🟡 `ceiling_height_min`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 260`
  - `raw_rp_19840.json`: `[int] 260`
  - `raw_rp_571.json`: `[int] 266`

**🟡 `ceiling_height_max`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 260`
  - `raw_rp_19840.json`: `[int] 280`
  - `raw_rp_571.json`: `[int] 266`

**🟡 `address`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_rp_17812.json`: `[str] Kraków, Czyżyny, ul. Akacjowa`
  - `raw_rp_19840.json`: `[str] Warszawa, Mokotów, Sielce, ul. Dziekońskiego 10`
  - `raw_rp_571.json`: `[str] Gdańsk, Zaspa-Rozstaje, Al. Jana Pawła`

**🟢 `website`** (Sukcesy: 4, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_rp_17812.json`: `[str] https://akacjowawita.pl/`
  - `raw_rp_19840.json`: `[str] https://www.domd.pl/pl-pl/warszawa/lista-inwestycji/apartamenty-beethovena?tabInTabs=1`
  - `raw_rp_571.json`: `[str] http://www.allcon.pl/mieszkania/apartamenty/`

**🟡 `geo_point`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `list`
- Przykłady:
  - `raw_rp_17812.json`: `[list] [19.980811741192813, 50.085572167779894]`
  - `raw_rp_19840.json`: `[list] [21.046164060462406, 52.19489438779884]`
  - `raw_rp_571.json`: `[list] [18.60481140448332, 54.39789056586483]`

**🟡 `geo_point_coordinates`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `list`
- Przykłady:
  - `raw_rp_17812.json`: `[list] [19.980811741192813, 50.085572167779894]`
  - `raw_rp_19840.json`: `[list] [21.046164060462406, 52.19489438779884]`
  - `raw_rp_571.json`: `[list] [18.60481140448332, 54.39789056586483]`

**🟡 `latitude`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `float`
- Przykłady:
  - `raw_rp_17812.json`: `[float] 50.085572167779894`
  - `raw_rp_19840.json`: `[float] 52.19489438779884`
  - `raw_rp_571.json`: `[float] 54.39789056586483`

**🟡 `longitude`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `float`
- Przykłady:
  - `raw_rp_17812.json`: `[float] 19.980811741192813`
  - `raw_rp_19840.json`: `[float] 21.046164060462406`
  - `raw_rp_571.json`: `[float] 18.60481140448332`

**🟡 `construction_date_upper`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_rp_17812.json`: `[str] 2026-09-30`
  - `raw_rp_19840.json`: `[str] 2026-12-31`
  - `raw_rp_571.json`: `[str] 2017-01-01`

**🟡 `main_image`** (Sukcesy: 3, Błędy: 1)
- Odnalezione typy: `dict`
- Przykłady:
  - `raw_rp_17812.json`: `[dict] {'type': 'obj', 'value': {'m_img_375x211': 'https://thumbs.rynekpierwotny.pl/3e79b87d:L4N21wX_P-YlZ0...`
  - `raw_rp_19840.json`: `[dict] {'type': 'obj', 'value': {'m_img_375x211': 'https://thumbs.rynekpierwotny.pl/3e79b87d:PletXloyVLyiFt...`
  - `raw_rp_571.json`: `[dict] {'type': 'obj', 'value': {'m_img_375x211': 'https://thumbs.rynekpierwotny.pl/3e79b87d:yYEh2gP3601-IY...`

### Obiekt: `developer`
- Razem kluczy: **3**
- W pełni pokryte: **3**
- Częściowo pokryte: **0**
- Całkowity brak pokrycia: **0**

#### Brakujące klucze (MISSING)

#### Szczegóły ekstrakcji (Różnice w zapisie / Częściowe pokrycie)
**🟢 `id`** (Sukcesy: 4, Błędy: 0)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 17812`
  - `raw_rp_19840.json`: `[int] 19840`
  - `raw_rp_571.json`: `[int] 571`

**🟢 `slug`** (Sukcesy: 4, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_rp_17812.json`: `[str] akacjowa-wita-krakow-pradnik-czerwony`
  - `raw_rp_19840.json`: `[str] apartamenty-beethovena-etap-2-apartamenty-inwestycyjne-warszawa-sielce`
  - `raw_rp_571.json`: `[str] awiator-gdansk-zaspa-rozstaje`

**🟢 `name`** (Sukcesy: 4, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_rp_17812.json`: `[str] Akacjowa Wita`
  - `raw_rp_19840.json`: `[str] Apartamenty Beethovena etap 2 - apartamenty inwestycyjne`
  - `raw_rp_571.json`: `[str] Awiator`

### Obiekt: `stage`
- Razem kluczy: **6**
- W pełni pokryte: **1**
- Częściowo pokryte: **0**
- Całkowity brak pokrycia: **5**

#### Brakujące klucze (MISSING)
- `offer_id`
- `offer_slug`
- `offer_name`
- `vendor_name`
- `vendor_slug`

#### Szczegóły ekstrakcji (Różnice w zapisie / Częściowe pokrycie)
**🟢 `id`** (Sukcesy: 4, Błędy: 0)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_rp_17812.json`: `[int] 17812`
  - `raw_rp_19840.json`: `[int] 19840`
  - `raw_rp_571.json`: `[int] 571`

## Portal: Otodom (oto)
**Przetestowane pliki (7):** raw_oto_10541147.json, raw_oto_29-l.json, raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json, raw_oto_atrium-oliva.json, raw_oto_develia.json, raw_oto_kijowska-vita.json, raw_oto_nowa-polnica.json

### Obiekt: `investment`
- Razem kluczy: **25**
- W pełni pokryte: **1**
- Częściowo pokryte: **18**
- Całkowity brak pokrycia: **5**

#### Brakujące klucze (MISSING)
- `price_min`
- `price_m2_min`
- `geo_point`
- `delivery_fallback_quarter`
- `delivery_fallback_year`

#### Szczegóły ekstrakcji (Różnice w zapisie / Częściowe pokrycie)
**🟡 `id`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] 4jDHU`
  - `raw_oto_atrium-oliva.json`: `[str] 4vYC5`
  - `raw_oto_kijowska-vita.json`: `[str] 4ARiu`

**🟡 `numeric_id`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[int] 63786214`
  - `raw_oto_atrium-oliva.json`: `[int] 66964841`
  - `raw_oto_kijowska-vita.json`: `[int] 67890030`

**🟡 `slug`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] afi-home-zlota-83-zelazna-24-warszawa`
  - `raw_oto_atrium-oliva.json`: `[str] atrium-oliva`
  - `raw_oto_kijowska-vita.json`: `[str] kijowska-vita`

**🟡 `name`** (Sukcesy: 5, Błędy: 2)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_29-l.json`: `[str] 29 L`
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] AFI Home Złota 83 / Żelazna 24, Warszawa`
  - `raw_oto_atrium-oliva.json`: `[str] Atrium Oliva`

**🟢 `developer_id`** (Sukcesy: 7, Błędy: 0)
- Odnalezione typy: `str, int`
- Przykłady:
  - `raw_oto_10541147.json`: `[str] 10541147`
  - `raw_oto_29-l.json`: `[int] 11609210`
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[int] 8972977`

**🟡 `developer_name`** (Sukcesy: 5, Błędy: 2)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_29-l.json`: `[str] Archicom`
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] AFI Home Złota/Żelazna`
  - `raw_oto_atrium-oliva.json`: `[str] Allcon`

**🟡 `developer_slug`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] afi-home-zlota-zelazna`
  - `raw_oto_atrium-oliva.json`: `[str] allcon`
  - `raw_oto_kijowska-vita.json`: `[str] develia`

**🟡 `units_count`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] 146`
  - `raw_oto_atrium-oliva.json`: `[str] 105`
  - `raw_oto_kijowska-vita.json`: `[str] 84`

**🟡 `ceiling_height_min`** (Sukcesy: 2, Błędy: 5)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_kijowska-vita.json`: `[str] 265`
  - `raw_oto_nowa-polnica.json`: `[str] 255`

**🟡 `ceiling_height_max`** (Sukcesy: 2, Błędy: 5)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_kijowska-vita.json`: `[str] 300`
  - `raw_oto_nowa-polnica.json`: `[str] 400`

**🟡 `latitude`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `float`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[float] 52.231094`
  - `raw_oto_atrium-oliva.json`: `[float] 54.399070069826`
  - `raw_oto_kijowska-vita.json`: `[float] 52.253595537516`

**🟡 `longitude`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `float`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[float] 21.003458`
  - `raw_oto_atrium-oliva.json`: `[float] 18.565699185181`
  - `raw_oto_kijowska-vita.json`: `[float] 21.053958070842`

**🟡 `status`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] removed_by_user`
  - `raw_oto_atrium-oliva.json`: `[str] active`
  - `raw_oto_kijowska-vita.json`: `[str] active`

**🟡 `delivery_raw`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `list`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[list] [{'label': 'offered_estates_types_project', 'values': ['offered_estates_types_project::flats'], 'uni...`
  - `raw_oto_atrium-oliva.json`: `[list] [{'label': 'offered_estates_types_project', 'values': ['offered_estates_types_project::flats'], 'uni...`
  - `raw_oto_kijowska-vita.json`: `[list] [{'label': 'offered_estates_types_project', 'values': ['offered_estates_types_project::flats'], 'uni...`

**🟡 `images`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `list`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[list] [{'thumbnail': 'https://ireland.apollo.olxcdn.com/v1/files/eyJmbiI6Im1pNXZzZnJtenp6ai1BUEwiLCJ3Ijpbe...`
  - `raw_oto_atrium-oliva.json`: `[list] [{'thumbnail': 'https://ireland.apollo.olxcdn.com/v1/files/eyJmbiI6ImZoNXg5ZXN0OWs4My1FQ09TWVNURU0iL...`
  - `raw_oto_kijowska-vita.json`: `[list] [{'thumbnail': 'https://ireland.apollo.olxcdn.com/v1/files/eyJmbiI6ImVneWlpZmJzb3E3ejEtRUNPU1lTVEVNI...`

**🟡 `url`** (Sukcesy: 6, Błędy: 1)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_10541147.json`: `[str] https://www.otodom.pl/pl/firmy/deweloperzy/euro-styl-ID10541147`
  - `raw_oto_29-l.json`: `[str] https://www.otodom.pl/pl/oferta/29-l-ID4AEY6`
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] https://www.otodom.pl/pl/oferta/afi-home-zlota-83-zelazna-24-warszawa-ID4jDHU`

**🟡 `developer_url`** (Sukcesy: 4, Błędy: 3)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] https://www.otodom.pl/pl/firmy/deweloperzy/afi-home-zlota-zelazna-ID8972977`
  - `raw_oto_atrium-oliva.json`: `[str] https://www.otodom.pl/pl/firmy/deweloperzy/allcon-ID10556297`
  - `raw_oto_kijowska-vita.json`: `[str] https://www.otodom.pl/pl/firmy/deweloperzy/develia-ID10556359`

**🟡 `owner_name`** (Sukcesy: 6, Błędy: 1)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_10541147.json`: `[str] Euro Styl`
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] AFI Home`
  - `raw_oto_atrium-oliva.json`: `[str] Biuro Sprzedaży`

**🟡 `hash_id`** (Sukcesy: 6, Błędy: 1)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_10541147.json`: `[str] 10541147`
  - `raw_oto_29-l.json`: `[str] 4AEY6`
  - `raw_oto_afi-home-zlota-83-zelazna-24-warszawa.json`: `[str] 4jDHU`

### Obiekt: `developer`
- Razem kluczy: **3**
- W pełni pokryte: **0**
- Częściowo pokryte: **3**
- Całkowity brak pokrycia: **0**

#### Brakujące klucze (MISSING)

#### Szczegóły ekstrakcji (Różnice w zapisie / Częściowe pokrycie)
**🟡 `id`** (Sukcesy: 2, Błędy: 5)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_10541147.json`: `[str] 10541147`
  - `raw_oto_develia.json`: `[str] 10556359`

**🟡 `slug`** (Sukcesy: 2, Błędy: 5)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_10541147.json`: `[str] euro-styl`
  - `raw_oto_develia.json`: `[str] develia`

**🟡 `name`** (Sukcesy: 2, Błędy: 5)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_oto_10541147.json`: `[str] Euro Styl`
  - `raw_oto_develia.json`: `[str] DEVELIA`

## Portal: TabelaOfert (to)
**Przetestowane pliki (1):** raw_to_i8975118.json

### Obiekt: `investment`
- Razem kluczy: **18**
- W pełni pokryte: **9**
- Częściowo pokryte: **0**
- Całkowity brak pokrycia: **8**

#### Brakujące klucze (MISSING)
- `developer_slug`
- `price_m2_min`
- `price_m2_max`
- `ceiling_height_min`
- `ceiling_height_max`
- `brand_klient_id`
- `publisher_klient_id`
- `klient_id`

#### Szczegóły ekstrakcji (Różnice w zapisie / Częściowe pokrycie)
**🟢 `id`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_to_i8975118.json`: `[str] 8975118`

**🟢 `slug`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_to_i8975118.json`: `[str] atal-aura-telefoniczna-21-lodz-srodmiescie-mieszkania-na-sprzedaz`

**🟢 `name`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_to_i8975118.json`: `[str] ATAL Aura`

**🟢 `developer_id`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_to_i8975118.json`: `[str] 1035`

**🟢 `developer_name`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_to_i8975118.json`: `[str] ATAL S.A.`

**🟢 `units_count`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_to_i8975118.json`: `[int] 0`

**🟢 `price_min`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_to_i8975118.json`: `[int] 0`

**🟢 `price_max`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `int`
- Przykłady:
  - `raw_to_i8975118.json`: `[int] 0`

**🟢 `offers_list`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `list`
- Przykłady:
  - `raw_to_i8975118.json`: `[list] []`

### Obiekt: `developer`
- Razem kluczy: **3**
- W pełni pokryte: **1**
- Częściowo pokryte: **0**
- Całkowity brak pokrycia: **2**

#### Brakujące klucze (MISSING)
- `id`
- `slug`

#### Szczegóły ekstrakcji (Różnice w zapisie / Częściowe pokrycie)
**🟢 `name`** (Sukcesy: 1, Błędy: 0)
- Odnalezione typy: `str`
- Przykłady:
  - `raw_to_i8975118.json`: `[str] ATAL Aura`
