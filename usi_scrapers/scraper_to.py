import re
import json
import logging
from pathlib import Path
from typing import Optional
from .fetcher import Fetcher
from .models import ScraperConfig, DeveloperPage
from .utils.io import save_raw_json, save_dev_raw_json, save_raw_html, lookup_developer_by_id, lookup_investment_by_id

from .utils.images import save_images
from .utils.portals import portal_api_url, portal_url, get_portal
from .mapping import get_mapping, resolve_path
from .utils.scrapers import generic_discover_investments, generic_download_dev_json

from usi_scrapers.logger import get_logger

logger = get_logger(__name__)


# --- Compiled Regex Constants ---
RE_URL_ID_JSON = re.compile(r',i?(\d+)(?:[/?]|$)')
RE_META_KLIENT_ID = re.compile(r'<meta[^>]+name=["\']klient-id["\'][^>]+content=["\'](\d+)["\']')
RE_NEXT_KLIENT_ID = re.compile(r'\\?"klientId\\?":(\d+)')
RE_NEXT_F_KLIENT_ID = re.compile(r'\\?"klient\\?"\s*:\s*\{\s*\\?"id\\?"\s*:\s*(\d+)')
RE_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
RE_SCRIPT_TAG = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL)
RE_KLIENT_ID_OBJ = re.compile(r'(\{.*?["\']klientId["\']\s*:\s*\d+.*?\})')
RE_NEXT_F_KLIENT_OBJ = re.compile(r'\\?"klient\\?"\s*:\s*(\{\s*\\?"id\\?":\d+.*?\\?"nazwaKlienta\\?".*?\})[,\}\]]')
RE_ID_MATCH = re.compile(r'"id":(\d+)')
RE_NAZWA_MATCH = re.compile(r'"nazwaKlienta":"([^"]+)"')
RE_LOGO_MATCH = re.compile(r'"logo":"([^"]+)"')
RE_API_TOKEN = re.compile(r'/_next/static/chunks/[^"]+-([a-f0-9]{10})\.js')
RE_H1_TAG = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
RE_SPAN_TAG = re.compile(r"<span[^>]*>(.*?)</span>", re.DOTALL)
RE_HTML_TAGS = re.compile(r"<[^>]+>")
RE_NAZWA_RSC = re.compile(r'"nazwa":"([^"]+)"')
RE_TITLE_TAG = re.compile(r"<title>(.*?)</title>", re.IGNORECASE)
RE_GALLERY_URL = re.compile(r'\\"url\\":\\"(https?://content\.tabelaofert\.pl/[^\\]+)')
RE_CONTENT_IMAGE = re.compile(r'(?:https?:)?//content\.tabelaofert\.pl/[^\s\"\\<>]+\.(?:webp|jpg|jpeg|png)', re.IGNORECASE)
RE_CDN_FNAME_END = re.compile(r"[^/]+-/(.+)$")
RE_CDN_FNAME_HASH = re.compile(r'_[a-f0-9]{8}\.')
RE_STEM_DIGITS = re.compile(r'-\d+$')
RE_STEM_8DIGITS = re.compile(r"-\d{8}")
RE_INV_SLUG = re.compile(r'/inwestycja/([^,]+)')
RE_SCALE = re.compile(r"scale_(\d+)")
RE_URL_ID_EXTRACT = re.compile(r",i(\d+)(?:[/?]|$)")
RE_DEV_CANDIDATE = re.compile(r'data-developer="([^"]+)"')
RE_DEV_CANDIDATE_SPAN = re.compile(r'<span>([^<]+)</span>')
RE_PAGE_PARAM = re.compile(r'page=\d+')
RE_LISTING_HREF = re.compile(r'href="(/inwestycja/([^",]+),i(\d+))"')
RE_IMG_SRC = re.compile(r'src="(https?://content\.tabelaofert\.pl/[^"]+\.(?:webp|jpg|png|jpeg))"')
RE_URL_PARSER_FALLBACK = re.compile(r'/inwestycja/([^,]+),i(\d+)')
RE_KRYTERIUM_ID = re.compile(r'klientKryterium[^\w]+([a-zA-Z0-9-]+)')
RE_KRYTERIUM_OBJ = re.compile(r'\\?"kryterium\\?"\s*:\s*\\?"([a-zA-Z0-9-]+)\\?"')
RE_DEV_LINK = re.compile(r'href="([^"]*/katalog-firm/deweloperzy/([^/"?#]+))"')
RE_DEV_LIST_LINK = re.compile(r'href="https://tabelaofert\.pl(/katalog-firm/deweloperzy/([^"/?]+))"')
RE_PAGE_NUM = re.compile(r'href="[^"]*[?&]page=(\d+)"')
# --------------------------------

def download_raw_to_dev_json(url: str, target_dir: Path, fetcher: Fetcher, config: ScraperConfig) -> Optional[str]:
    """
    Downloads raw JSON for a TabelaOfert developer profile and saves it.
    Enforces PURE-RAW rule: saves the exact JSON from the portal.
    Returns the resolved developer slug.
    """
    def fetch_to_dev(u, f):
        html = fetch_to_html(u, f)
        if not html: return None
        d = extract_to_dev_raw_json(html)
        if isinstance(d, dict) and "url" not in d:
            d["url"] = u
        return d

    def extract_id(d):
        to_dev_mapping = get_mapping("to", "developer")
        res = resolve_path(d, to_dev_mapping.get("id"))
        return str(res) if res else None

    def extract_logo(d):
        if not d: return None
        if "logo_url" in d: return d["logo_url"]
        if "logo" in d:
            if isinstance(d["logo"], dict): return d["logo"].get("url")
            return d["logo"]
        if "image" in d:
            if isinstance(d["image"], dict): return d["image"].get("url")
            return d["image"]
        return None

    def extract_slug(d):
        to_dev_mapping = get_mapping("to", "developer")
        return resolve_path(d, to_dev_mapping.get("slug"))

    return generic_download_dev_json(
        fetcher, config, url, target_dir, "to",
        fetch_func=fetch_to_dev,
        extract_id_func=extract_id,
        extract_logo_func=extract_logo,
        extract_slug_func=extract_slug,
        source_url=url
    )


def extract_to_klient_id(html: str, raw_json: dict = None) -> str | None:
    """Extracts internal klient-id from TabelaOfert JSON or HTML fallback."""
    # 1. PURE-RAW: read from JSON directly!
    if raw_json:
        to_mapping = get_mapping("to", "investment")
        klient_id = resolve_path(raw_json, to_mapping.get("klient_id"))
        if klient_id: return str(klient_id)
        
        brand_klient_id = resolve_path(raw_json, to_mapping.get("brand_klient_id"))
        if brand_klient_id: return str(brand_klient_id)
        
        pub_klient_id = resolve_path(raw_json, to_mapping.get("publisher_klient_id"))
        if pub_klient_id: return str(pub_klient_id)
        
        # Fallbacks for `identifier`
        brand = raw_json.get("brand", {})
        if isinstance(brand, dict) and "identifier" in brand: return str(brand["identifier"])
        
        publisher = raw_json.get("publisher", {})
        if isinstance(publisher, dict) and "identifier" in publisher: return str(publisher["identifier"])

    # 2. From Meta Tag (fallback)
    m = RE_META_KLIENT_ID.search(html)
    if m:
        return m.group(1)
    
    # 3. From Next.js Pages Router state (escaped JSON fallback)
    m = RE_NEXT_KLIENT_ID.search(html)
    if m:
        return m.group(1)
        
    # 4. From Next.js App Router state (self.__next_f.push)
    m = RE_NEXT_F_KLIENT_ID.search(html)
    if m:
        return m.group(1)
        
    return None


def extract_to_dev_raw_json(html: str) -> dict:
    """Extracts pure raw JSON for TabelaOfert developer (no aggregations or fake dicts)."""
    # 1. Check for Next.js data (purest form if available)
    m_next = RE_NEXT_DATA.search(html)
    if m_next:
        try:
            return json.loads(m_next.group(1))
        except:
            pass

    # 2. Check for JSON-LD Organization/LocalBusiness
    scripts = RE_SCRIPT_TAG.findall(html)
    for s in scripts:
        if '"@type":"Organization"' in s or '"@type": "Organization"' in s or '"@type":"LocalBusiness"' in s or '"@type": "LocalBusiness"' in s:
            try:
                d = json.loads(s.strip())
                items = d if isinstance(d, list) else [d]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") in ("Organization", "LocalBusiness"):
                        return item
            except Exception:
                pass

    # 3. Extract JSON object containing klientId from Next_f or window
    for s in scripts:
        if 'klientId' in s or 'klient-id' in s:
            # Match innermost json object containing klientId
            match = RE_KLIENT_ID_OBJ.search(s)
            if match:
                try:
                    return json.loads(match.group(1).replace(r'\"', '"'))
                except:
                    pass

    # 4. Extract from Next.js App Router (self.__next_f.push)
    m_klient = RE_NEXT_F_KLIENT_OBJ.search(html)
    if m_klient:
        try:
            # Clean up escape characters and try to parse the substring.
            # Next.js App Router escapes strings in __next_f.push
            raw_str = m_klient.group(1).replace(r'\"', '"').replace(r'\\', '\\')
            
            # Since regex matching of nested brackets is brittle, we'll construct a simplified dict manually
            # if full JSON parsing fails.
            try:
                # Attempt to parse fully if the regex happened to capture a balanced object
                return json.loads(raw_str)
            except json.JSONDecodeError:
                # Fallback: extract key fields manually and construct a synthetic dict
                synthetic = {}
                
                id_match = RE_ID_MATCH.search(raw_str)
                if id_match: synthetic["klient_id"] = int(id_match.group(1))
                
                nazwa_match = RE_NAZWA_MATCH.search(raw_str)
                if nazwa_match: synthetic["nazwa"] = nazwa_match.group(1)
                
                logo_match = RE_LOGO_MATCH.search(raw_str)
                if logo_match: synthetic["logo"] = logo_match.group(1)
                
                return synthetic
                
        except Exception:
            pass
                    
    return {}

def extract_to_api_token(html: str) -> str | None:
    """Extracts the API version token from Next.js script hashes."""
    # Pattern for hashes like c1661a4a02 in /_next/static/chunks/main-app-c1661a4a02.js
    m = RE_API_TOKEN.search(html)
    if m:
        return f"v{m.group(1)}"
    logger.debug("extract_to_api_token: no token found in HTML script hashes")
    return None

def fetch_to_api_gallery(inv_id: str, token: str, fetcher: Fetcher) -> list[str]:
    """Fetches investment gallery using the hidden JSON API."""
    url = portal_api_url("to", "gallery", token=token, inv_id=inv_id)
    logger.info(f"Fetching TO Gallery API: {url}")
    data = fetcher.fetch_json(url)
    if not data:
        logger.debug(f"fetch_to_api_gallery: no data returned for {url}")
        return []
    
    images = data.get("data", {}).get("images", [])
    return [img["url"] for img in images if isinstance(img, dict) and "url" in img]

def fetch_to_api_mapa(inv_id: str, token: str, fetcher: Fetcher) -> dict | None:
    """Fetches investment map data using the hidden JSON API."""
    url = portal_api_url("to", "mapa", token=token, inv_id=inv_id)
    logger.info(f"Fetching TO Mapa API: {url}")
    data = fetcher.fetch_json(url)
    if not data:
        logger.debug(f"fetch_to_api_mapa: no data returned for {url}")
        return None
    return data

def extract_to_data(html: str, url: str, fetcher: Fetcher = None) -> dict:
    """
    Centralized extraction logic for TabelaOfert.
    """
    data = parse_to_product(html) or {}
    data["url"] = url
    
    to_id = _extract_to_id(url)
    if to_id:
        data["to_id"] = to_id
    
    # 1. Clean Name extraction
    clean_name = None
    h1_match = RE_H1_TAG.search(html)
    if h1_match:
        content = h1_match.group(1)
        span_match = RE_SPAN_TAG.search(content)
        if span_match:
            clean_name = RE_HTML_TAGS.sub("", span_match.group(1)).strip()
    
    if not clean_name:
        rsc_names = RE_NAZWA_RSC.findall(html)
        if rsc_names:
            clean_name = rsc_names[0]
            
    if clean_name:
        data["name"] = clean_name
    elif not data.get("name"):
        title_match = RE_TITLE_TAG.search(html)
        if title_match:
            data["name"] = title_match.group(1).split("-")[0].strip()

    # 2. Location & Geo
    lat, lng = extract_geo(data)
    
    offers_data = data.get("offers", {})
    offers = offers_data.get("offers", []) if isinstance(offers_data, dict) else []
    
    address_obj = {}
    if offers and isinstance(offers[0], dict):
        address_obj = offers[0].get("itemOffered", {}).get("address", {})
        
    street = address_obj.get("streetAddress")
    city = address_obj.get("addressLocality")
    region = address_obj.get("addressRegion")
    
    address = ", ".join(filter(None, [street, city])) or None
    
    data["_extracted_location"] = {
        "address": address,
        "city": city,
        "region": region,
        "street": street,
        "latitude": lat,
        "longitude": lng
    }

    # 3. Gallery (API Priority -> HTML Fallback)
    gallery_urls = []
    inv_id = _extract_to_id(url)
    token = extract_to_api_token(html)
    
    if inv_id and token and fetcher:
        gallery_urls = fetch_to_api_gallery(inv_id, token, fetcher)
        
    if not gallery_urls:
        gallery_urls = extract_gallery_urls(html)
        
    data["_raw_gallery_urls"] = gallery_urls
    
    return data

def download_raw_to_json(url: str, target_dir: Path, fetcher: Fetcher, config: ScraperConfig) -> Path | None:
    """
    Downloads raw data for a TabelaOfert investment and saves it.
    """
    html = fetch_to_html(url, fetcher)
    if not html:
        logger.error(f"Failed to fetch TO HTML for {url}")
        return None

    data = parse_to_product(html) or {}
    to_id = _extract_to_id(url)
    portal_id = to_id if to_id else None

    dev_slug = target_dir.parent.name
    inv_slug = target_dir.name

    # Resolve Investment Slug (ID-based lookup)
    if portal_id:
        existing_inv_slug = lookup_investment_by_id(config.public_dir, dev_slug, "to", portal_id)
        if existing_inv_slug:
            inv_slug = existing_inv_slug
            logger.info(f"Matched investment ID {portal_id} to existing investment slug: {inv_slug}")

    # Fetch hidden map API
    token = extract_to_api_token(html)
    if to_id and token and fetcher:
        map_data = fetch_to_api_mapa(to_id, token, fetcher)
        if map_data:
            data["_raw_mapa"] = map_data

    cleaned_html = clean_to_html(html)
    # Temporary fallback to save HTML using the new target_dir
    # save_raw_html signature still requires slugs, let's bypass it and write directly or wait
    # Actually, Krok 02.03 is about removing dev_slug/inv_slug from TechnicalDataManager,
    # but we should probably refactor save_raw_html as well if it uses them.
    # We will modify save_raw_html in io.py next.
    from .utils.io import save_raw_html
    save_raw_html(cleaned_html, target_dir, "to", portal_id=portal_id or "unknown")
    
    # Dodajemy surowy i odchudzony kod HTML do obiektu, żeby parser mógł korzystać z regexów "w locie"
    data["_raw_html"] = cleaned_html

    return save_raw_json(data, target_dir, "to", portal_id=portal_id)

def clean_to_html(html: str) -> str:
    """Removes bloat from HTML while preserving inline JSON data and content."""
    # Usuwamy skrypty z src (zewnętrzne biblioteki, analytics itp)
    html = re.sub(r'<script\b[^>]*\bsrc\b[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
    # Usuwamy wbudowane style i svg
    html = re.sub(r'<style\b[^>]*>.*?</style>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<svg\b[^>]*>.*?</svg>', '', html, flags=re.IGNORECASE | re.DOTALL)
    return html

def fetch_to_html(url: str, fetcher: Fetcher) -> str:
    """Fetch tabelaofert page HTML using the centralized Fetcher."""
    return fetcher.fetch(url) or ""

def parse_to_product(html: str) -> dict:
    scripts = RE_SCRIPT_TAG.findall(html)
    for s in scripts:
        if '"@type":"Product"' in s or '"@type": "Product"' in s:
            try:
                content = s.strip()
                if content.startswith("self.__next_f.push"):
                    continue
                d = json.loads(content)
                if isinstance(d, list):
                    for item in d:
                        if item.get("@type") == "Product": return item
                elif d.get("@type") == "Product":
                    return d
            except json.JSONDecodeError:
                continue
    return {}

def extract_geo(product: dict) -> tuple:
    offers_data = product.get("offers", {})
    if not isinstance(offers_data, dict): return None, None
    
    offers = offers_data.get("offers", [])
    if not isinstance(offers, list): return None, None
    
    for offer in offers:
        geo = offer.get("itemOffered", {}).get("geo", {})
        lat = geo.get("latitude")
        lng = geo.get("longitude")
        if lat is not None and lng is not None:
            try:
                return float(lat), float(lng)
            except (TypeError, ValueError):
                continue
    return None, None

def extract_additional_prop(product: dict, name: str) -> str | None:
    props = product.get("additionalProperty", [])
    if not isinstance(props, list): return None
    
    for prop in props:
        if prop.get("name") == name:
            return prop.get("value")
    return None

def extract_gallery_urls(html: str) -> list[str]:
    found_urls = []
    
    # Target only the main content area, excluding "Other investments" and "Similar offers"
    main_window = html
    for stop_word in ["Inne inwestycje", "Podobne oferty", "Polecane inwestycje"]:
        # Find position of stop word
        idx = html.find(stop_word)
        if idx != -1:
            main_window = html[:idx]
            break

    # 1. From script tags (often contains the main gallery)
    scripts = RE_SCRIPT_TAG.findall(main_window)
    for s in scripts:
        if '"galeria"' in s and '"zdjecia"' in s:
            urls = RE_GALLERY_URL.findall(s)
            if urls:
                found_urls.extend([u.rstrip('"') for u in urls])
                
    # 2. Targeted regex on main window
    regex = r'(?:https?:)?//content\.tabelaofert\.pl/[^\s\"\\<>]+\.(?:webp|jpg|jpeg|png)'
    found = RE_CONTENT_IMAGE.findall(main_window)
    for u in found:
        u_clean = u if u.startswith("http") else ("https:" + u)
        # Skip thumbnails
        if any(p in u_clean for p in ["thumb_200x200", "scale_300", "scale_245", "thumb_600x400"]):
            continue
        found_urls.append(u_clean)
            
    return list(dict.fromkeys(found_urls))

def _cdn_filename(url: str) -> str:
    fname = url.rsplit("/", 1)[-1]
    m = RE_CDN_FNAME_END.search(url)
    if m: 
        fname = m.group(1)
    else:
        parts = fname.split(",")
        if len(parts) > 1: fname = parts[-1]
    
    fname = RE_CDN_FNAME_HASH.sub('.', fname)
    return fname

def _investment_image_prefix(image_url: str) -> str | None:
    fname = _cdn_filename(image_url)
    if "/" in fname:
        fname = fname.rsplit("/", 1)[-1]
        
    stem = fname.rsplit(".", 1)[0]
    stem = RE_STEM_DIGITS.sub('', stem)
    
    m = RE_STEM_8DIGITS.search(stem)
    if m:
        return stem[: m.start()]
    
    parts = stem.split("-")
    if len(parts) > 3:
        return "-".join(parts[:4])
    return "-".join(parts)

def filter_investment_images(urls: list[str], product: dict, inv_url: str = None) -> list[str]:
    main_image = product.get("image")
    if isinstance(main_image, list) and main_image:
        main_image = main_image[0]
        
    to_id = _extract_to_id(inv_url) if inv_url else None
    prefix = _investment_image_prefix(str(main_image)) if main_image else None
    
    if prefix and (len(prefix) < 5 or prefix.lower() in ("mieszkanie", "logo", "mapa")):
        if inv_url:
            slug_match = RE_INV_SLUG.search(inv_url)
            if slug_match:
                prefix = "-".join(slug_match.group(1).split("-")[:3])

    candidates = []
    for url in urls:
        fname = _cdn_filename(url)
        
        # 1. ID Check (Strong signal for TabelaOfert plans)
        if to_id and (f"plany/{to_id}" in url or f"mapa-i{to_id}" in fname):
             candidates.append(url)
             continue

        # 2. Skip generic stuff
        if any(p in fname.lower() for p in ["mapa-", "logo-", "icon-", "avatar-", "spacer-"]):
            continue
            
        # 3. Prefix Check
        if prefix:
            prefix_parts = prefix.split("-")
            short_prefix = "-".join(prefix_parts[:2]) if len(prefix_parts) > 1 else prefix
            
            clean_fname = fname.rsplit("/", 1)[-1] if "/" in fname else fname
            if not clean_fname.startswith(short_prefix):
                continue
        
        candidates.append(url)

    # 4. Fallback if filter too aggressive
    if not candidates and urls:
        for url in urls:
            fname = _cdn_filename(url)
            if not any(p in fname.lower() for p in ["mapa-", "logo-", "icon-", "avatar-"]):
                candidates.append(url)

    # 5. Deduplicate and take highest resolution
    by_filename: dict[str, tuple[int, str]] = {}
    for url in candidates:
        fname = _cdn_filename(url)
        m = RE_SCALE.search(url)
        scale = int(m.group(1)) if m else 0
        if fname not in by_filename or scale > by_filename[fname][0]:
            by_filename[fname] = (scale, url)
            
    return [v[1] for v in by_filename.values()]

def _extract_to_id(url: str) -> str | None:
    if not url: return None
    m = RE_URL_ID_EXTRACT.search(url)
    return m.group(1) if m else None

def fetch_to_agency_name(url: str, fetcher: Fetcher) -> str | None:
    html = fetch_to_html(url, fetcher)
    if not html:
        return None
        
    product = parse_to_product(html)
    if isinstance(product.get("brand"), dict):
        name = product.get("brand", {}).get("name")
        if name: return name

    h1_match = RE_H1_TAG.search(html)
    if h1_match:
        spans = RE_SPAN_TAG.findall(h1_match.group(1))
        if len(spans) >= 2:
            dev_candidate = RE_HTML_TAGS.sub("", spans[-1]).strip()
            if dev_candidate and len(dev_candidate) < 100:
                return dev_candidate

    dev_match = RE_DEV_CANDIDATE.search(html)
    if dev_match:
        return dev_match.group(1).strip()

    return "Nieznany Deweloper"

def discover_to_listing(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None, max_pages: int = 3) -> list[dict]:
    """
    Discovers TabelaOfert investments from a listing page with pagination.
    max_pages: Limit for pagination to prevent downloading entire catalogs (default: 3).
    """
    if not identifier:
        logger.error("discover_to_listing requires an identifier (URL)")
        return []

    url = identifier
    all_offers = []
    seen_ids = set()

    base_url = url
    current_page = 1

    while True:
        if max_pages and current_page > max_pages:
            logger.info(f"Reached max_pages limit ({max_pages}) for TabelaOfert discovery.")
            break

        page_url = base_url
        if "page=" in page_url:            page_url = RE_PAGE_PARAM.sub(f'page={current_page}', page_url)
        else:
            connector = "&" if "?" in page_url else "?"
            page_url += f"{connector}page={current_page}"

        logger.info(f"Discovering TabelaOfert investments from URL (page {current_page}): {page_url}")
        html = fetch_to_html(page_url, fetcher)
        if not html: 
            break
        
        page_offers = []
        matches = list(RE_LISTING_HREF.finditer(html))
        
        if not matches:
            break

        for m in matches:
            full_path, slug_part, to_id = m.groups()
            if to_id in seen_ids: 
                continue
            seen_ids.add(to_id)
            
            full_url = f"https://tabelaofert.pl{full_path}"
            name = slug_part.replace("-", " ").title()
            
            start_search = max(0, m.start() - 2000)
            end_search = min(len(html), m.end() + 1000)
            window = html[start_search:end_search]
            
            img_matches = list(RE_IMG_SRC.finditer(window))
            
            image_url = None
            if img_matches:
                for m_img in img_matches:
                    u = m_img.group(1)
                    if not any(p in u.lower() for p in ["logo-", "icon-", "avatar-", "spacer-", "mapa-"]):
                        image_url = u
                        break
                if not image_url:
                    image_url = img_matches[-1].group(1)

            dev_name = None
            dev_match = RE_DEV_CANDIDATE.search(window)
            if not dev_match:
                dev_match = RE_DEV_CANDIDATE_SPAN.search(window)
            
            if dev_match:
                dev_name = dev_match.group(1).strip()

            all_offers.append({
                "id": to_id,
                "url": full_url,
            })
            
            if limit and len(all_offers) >= limit:
                return all_offers

        if 'class="next"' not in html and 'rel="next"' not in html:
            break
            
        current_page += 1
            
    return all_offers

def discover_to_investments(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None, max_pages: int = 3) -> list[dict]:
    if not identifier:
        logger.info("Performing global TabelaOfert discovery via config URLs")
        return generic_discover_investments(
            config, fetcher, config.to_discovery_urls,
            lambda c, f, u, l: discover_to_listing(c, f, identifier=u, limit=l, max_pages=max_pages),
            limit=limit
        )

    url = portal_url("to", "developer", slug=identifier)
    return discover_to_listing(config, fetcher, identifier=url, limit=limit, max_pages=max_pages)

def scrape_tabelaofert(url: str, fetcher: Fetcher) -> dict:
    logger.info(f"Scraping TabelaOfert: {url}")
    html = fetch_to_html(url, fetcher)
    if not html:
        return {"error": "Could not fetch HTML"}

    product = extract_to_data(html, url, fetcher=fetcher)
    
    # Native slug extraction
    from .utils.url_parser import parse_url
    parsed = parse_url(url)
    investment_slug = parsed.get("investment_slug")
    if not investment_slug:
        # Emergency fallback for URL parsing
        match = RE_URL_PARSER_FALLBACK.search(url)
        if match:
            investment_slug = match.group(1)
            
    if not investment_slug:
        return {"error": f"Could not determine investment_slug from URL: {url}"}
    
    # 1. KRYTYCZNA ZASADA: Pierwszeństwo ma zawsze ID (klient-id)
    klient_id = extract_to_klient_id(html, raw_json=product)
    if not klient_id:
        return {"error": f"CRITICAL: Could not extract klient-id for TabelaOfert from {url}. Aborting to prevent identity mismatch."}

    logger.info(f"Extracted klient-id {klient_id} for TabelaOfert developer resolution.")
    
    # Resolve local developer folder slug using the ID
    developer_slug = lookup_developer_by_id(fetcher.config.public_dir, "to", klient_id)
    to_dev_url = None
    
    if developer_slug:
        logger.info(f"Matched TO klient-id {klient_id} to existing developer slug: {developer_slug}")
    else:
        temp_slug = None
        
        # 1. New Next.js payload structure (as seen in __next_f stream)
        # We use a very flexible regex to catch various escaping levels
        m_next = re.search(r'slug[\\"]+,\s*[\\"]+deweloperzy/([^\\"?# ]+)[\\"]+', html)
        if not m_next:
            m_next = re.search(r'katalog-firm[\\"]+,\s*[\\"]+deweloperzy[\\"]+,\s*[\\"]+([^\\"?# ]+)[\\"]+', html)
        
        if m_next:
            temp_slug = m_next.group(1)
            logger.info(f"Extracted developer slug from Next.js payload: {temp_slug}")
        else:
            # 2. Extract from any deweloperzy/ URL in HTML (URL fallback)
            # We look for all candidates and pick the first one that is NOT a known city
            all_dev_urls = re.findall(r'/katalog-firm/deweloperzy/([^/"?#\\<> ]+)', html)
            city_slugs = {
                "warszawa", "krakow", "lodz", "wroclaw", "poznan", "gdansk", "szczecin", 
                "bydgoszcz", "lublin", "bialystok", "katowice", "gdynia", "czestochowa", 
                "radom", "sosnowiec", "torun", "kielce", "rzeszow", "gliwice", "zabrze", 
                "olsztyn", "bielsko-biala", "bytom", "zielona-gora", "rybnik", "ruda-slaska",
                "opolskie", "dolnoslaskie", "mazowieckie", "slaskie", "malopolskie", "wielkopolskie"
            }
            for s in all_dev_urls:
                if s not in city_slugs and s != "unknown" and not s.startswith("strona"):
                    temp_slug = s
                    logger.info(f"Extracted developer slug from HTML URL (non-city): {temp_slug}")
                    break
                    
            if not temp_slug:
                # 3. Fallback to older kryterium logic
                m = RE_KRYTERIUM_ID.search(html)
                if not m:
                    m = RE_KRYTERIUM_OBJ.search(html)
                if m:
                    temp_slug = m.group(1)

        if temp_slug:
            # Construct canonical developer URL
            to_dev_url = f"https://tabelaofert.pl/katalog-firm/deweloperzy/{temp_slug}"
            logger.info(f"Proactively fetching TO developer profile to resolve slug: {to_dev_url}")
            temp_dir = Path(fetcher.config.public_dir) / "USIdev" / f"temp_{klient_id}"
            resolved_slug = download_raw_to_dev_json(to_dev_url, temp_dir, fetcher, fetcher.config)
            if resolved_slug:
                developer_slug = resolved_slug
                logger.info(f"Proactively resolved TO developer slug: {developer_slug}")

    if not developer_slug:
        err_msg = (
            f"Developer resolution failed for TabelaOfert klient-id {klient_id}. "
            f"Local ID lookup failed, and API download from developer URL '{to_dev_url if to_dev_url else 'None'}' did not yield a valid slug."
        )
        return {"error": err_msg}
    
    # ID-based Investment Identification
    to_id = _extract_to_id(url)
    portal_id = to_id if to_id else None
    if portal_id:
        existing_inv_slug = lookup_investment_by_id(fetcher.config.public_dir, developer_slug, "to", portal_id)
        if existing_inv_slug:
            investment_slug = existing_inv_slug
            logger.info(f"Matched investment ID {portal_id} to existing investment slug: {investment_slug}")

    ext_loc = product.get("_extracted_location", {})
    address = ext_loc.get("address")
    city = ext_loc.get("city")
    region = ext_loc.get("region")
    lat = ext_loc.get("latitude")
    lng = ext_loc.get("longitude")

    # Removed hardcoded lowPrice/highPrice variables

    gallery_urls = product.get("_raw_gallery_urls", [])
    filtered_urls = filter_investment_images(gallery_urls, product, url)
    
    amenities = []
    props = product.get("additionalProperty", [])
    if isinstance(props, list):
        _meta = {"Wysokość mieszkania", "Termin oddania", "Dostępna liczba ofert"}
        amenities = [
            {"name": p["name"], "value": p["value"]}
            for p in props if isinstance(p, dict) and p.get("name") not in _meta
        ]

    to_mapping = get_mapping("to", "investment")
    
    # Try mapping first, fallback to manual extraction
    mapped_price_min = resolve_path(product, to_mapping.get("price_min"))
    mapped_price_max = resolve_path(product, to_mapping.get("price_max"))

    # Extract agnostic signals
    signals = {}
    signal_mapping = to_mapping.get("signals", {})
    for key, path in signal_mapping.items():
        signals[key] = resolve_path(product, path)

    # Obrazy zostaną pobrane i zlokalizowane przez TechnicalDataManager w KROKU 2 (api.py)
    # Zwracamy surowe URL-e, aby manager wiedział co pobrać.

    return {
        "source": "tabelaofert.pl",
        "to_id": _extract_to_id(url),
        "to_url": url,
        "developer_slug": developer_slug,
        "investment_slug": investment_slug,
        "name": resolve_path(product, to_mapping.get("name")) or product.get("name"),
        "developer_name": resolve_path(product, to_mapping.get("developer_name")),
        "address": address,
        "city": city,
        "region": region,
        "latitude": lat,
        "longitude": lng,
        "price_min": mapped_price_min,
        "price_max": mapped_price_max,
        "properties_count": resolve_path(product, to_mapping.get("units_count")),
        "ceiling_height_min": resolve_path(product, to_mapping.get("ceiling_height_min")),
        "ceiling_height_max": resolve_path(product, to_mapping.get("ceiling_height_max")),
        "construction_date_upper": extract_additional_prop(product, "Termin oddania"),
        "amenities": amenities,
        "image_urls": filtered_urls,
        "signals": signals,
        "raw_details": product,
        "fetch_vector": fetcher.last_fetch_vector
    }


def discover_to_developers(
    fetcher: Fetcher,
    page: int = 1,
    base_url: Optional[str] = None,
) -> DeveloperPage:
    """Pobiera jedną stronę listy deweloperów z TabelaOfert."""
    listing_url = base_url or get_portal("to")["developer_list_url"].format(page=page)
    if base_url:
        if "page=" in listing_url:
            listing_url = RE_PAGE_PARAM.sub(f'page={page}', listing_url)
        else:
            connector = "&" if "?" in listing_url else "?"
            listing_url = f"{listing_url}{connector}page={page}"

    html = fetch_to_html(listing_url, fetcher)
    if not html:
        logger.error(f"Failed to fetch TO developer listing: {listing_url}")
        return DeveloperPage(developers=[], total_pages=1, page=page)

    seen_slugs: set[str] = set()
    developers = []
    # Developer profile links are absolute URLs; city/filter links are relative — match only absolute
    for m in RE_DEV_LIST_LINK.finditer(html):
        full_path, slug = m.group(1), m.group(2)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        developers.append({
            "url": f"https://tabelaofert.pl{full_path}",
            "name": None,
            "slug": slug,
        })

    # Determine total_pages from paginator links
    page_nums = [int(n) for n in RE_PAGE_NUM.findall(html)]
    if page_nums:
        total_pages = max(page_nums)
    elif 'class="next"' in html or 'rel="next"' in html:
        total_pages = page + 1
    else:
        total_pages = page

    return DeveloperPage(developers=developers, total_pages=total_pages, page=page)
