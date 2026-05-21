import re
import json
import logging
from pathlib import Path
from typing import Optional
from .fetcher import Fetcher
from .models import ScraperConfig, DeveloperPage
from .utils.io import save_raw_json, save_dev_raw_json, lookup_developer_by_id, lookup_investment_by_id
from .utils.string import slugify
from .utils.portals import portal_api_url, portal_url, get_portal
from .mapping import get_mapping, resolve_path
from .utils.scrapers import generic_discover_investments, generic_download_dev_json

from . import get_logger

logger = get_logger(__name__)

def download_raw_to_dev_json(url: str, dev_slug: Optional[str], fetcher: Fetcher, config: ScraperConfig) -> Optional[str]:
    """
    Downloads raw JSON for a TabelaOfert developer profile and saves it.
    Enforces PURE-RAW rule: saves the exact JSON from the portal.
    Returns the resolved developer slug.
    """
    def fetch_to_dev(u, f):
        html = fetch_to_html(u, f)
        if not html: return None
        return extract_to_dev_raw_json(html)

    def extract_id(d):
        if not d: return None
        if "klientId" in d: return str(d["klientId"])
        if "klient_id" in d: return str(d["klient_id"])
        if "identifier" in d: return str(d["identifier"])
        
        # From Next.js pageProps if it's __NEXT_DATA__
        props = d.get("props", {}).get("pageProps", {})
        if props.get("klientId"): return str(props["klientId"])
        if props.get("developer", {}).get("id"): return str(props["developer"]["id"])
        
        # From JSON-LD URL
        for key in ["@id", "url"]:
            val = d.get(key)
            if val and isinstance(val, str):
                m = re.search(r',i?(\d+)(?:[/?]|$)', val)
                if m: return m.group(1)
        return None

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

    return generic_download_dev_json(
        fetcher, config, url, dev_slug, "to",
        fetch_func=fetch_to_dev,
        extract_id_func=extract_id,
        extract_logo_func=extract_logo,
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
    m = re.search(r'<meta[^>]+name=["\']klient-id["\'][^>]+content=["\'](\d+)["\']', html)
    if m:
        return m.group(1)
    
    # 3. From Next.js state (escaped JSON fallback)
    m = re.search(r'\\?"klientId\\?":(\d+)', html)
    if m:
        return m.group(1)
        
    return None


def extract_to_dev_raw_json(html: str) -> dict:
    """Extracts pure raw JSON for TabelaOfert developer (no aggregations or fake dicts)."""
    # 1. Check for Next.js data (purest form if available)
    m_next = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m_next:
        try:
            return json.loads(m_next.group(1))
        except:
            pass

    # 2. Check for JSON-LD Organization/LocalBusiness
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
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
            match = re.search(r'(\{.*?["\']klientId["\']\s*:\s*\d+.*?\})', s)
            if match:
                try:
                    return json.loads(match.group(1).replace(r'\"', '"'))
                except:
                    pass
                    
    return {}

def extract_to_api_token(html: str) -> str | None:
    """Extracts the API version token from Next.js script hashes."""
    # Pattern for hashes like c1661a4a02 in /_next/static/chunks/main-app-c1661a4a02.js
    m = re.search(r'/_next/static/chunks/[^"]+-([a-f0-9]{10})\.js', html)
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
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    if h1_match:
        content = h1_match.group(1)
        span_match = re.search(r"<span[^>]*>(.*?)</span>", content, re.DOTALL)
        if span_match:
            clean_name = re.sub(r"<[^>]+>", "", span_match.group(1)).strip()
    
    if not clean_name:
        rsc_names = re.findall(r'"nazwa":"([^"]+)"', html)
        if rsc_names:
            clean_name = rsc_names[0]
            
    if clean_name:
        data["name"] = clean_name
    elif not data.get("name"):
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
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

def download_raw_to_json(url: str, dev_slug: str, inv_slug: str, fetcher: Fetcher, config: ScraperConfig) -> Path | None:
    """
    Downloads raw data for a TabelaOfert investment and saves it.
    """
    html = fetch_to_html(url, fetcher)
    if not html:
        logger.error(f"Failed to fetch TO HTML for {url}")
        return None

    data = parse_to_product(html) or {}
    to_id = _extract_to_id(url)
    portal_id = f"i{to_id}" if to_id else None

    # Resolve Investment Slug (ID-based lookup)
    if portal_id:
        existing_inv_slug = lookup_investment_by_id(config.public_dir, dev_slug, "to", portal_id)
        if existing_inv_slug:
            inv_slug = existing_inv_slug
            logger.info(f"Matched investment ID {portal_id} to existing investment slug: {inv_slug}")

    return save_raw_json(data, config.public_dir, dev_slug, inv_slug, "to", portal_id=portal_id)

def fetch_to_html(url: str, fetcher: Fetcher) -> str:
    """Fetch tabelaofert page HTML using the centralized Fetcher."""
    return fetcher.fetch(url) or ""

def parse_to_product(html: str) -> dict:
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
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
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", main_window, re.DOTALL)
    for s in scripts:
        if '"galeria"' in s and '"zdjecia"' in s:
            urls = re.findall(r'\\"url\\":\\"(https?://content\.tabelaofert\.pl/[^\\]+)', s)
            if urls:
                found_urls.extend([u.rstrip('"') for u in urls])
                
    # 2. Targeted regex on main window
    regex = r'(?:https?:)?//content\.tabelaofert\.pl/[^\s\"\\<>]+\.(?:webp|jpg|jpeg|png)'
    found = re.findall(regex, main_window, re.IGNORECASE)
    for u in found:
        u_clean = u if u.startswith("http") else ("https:" + u)
        # Skip thumbnails
        if any(p in u_clean for p in ["thumb_200x200", "scale_300", "scale_245", "thumb_600x400"]):
            continue
        found_urls.append(u_clean)
            
    return list(dict.fromkeys(found_urls))

def _cdn_filename(url: str) -> str:
    fname = url.rsplit("/", 1)[-1]
    m = re.search(r"[^/]+-/(.+)$", url)
    if m: 
        fname = m.group(1)
    else:
        parts = fname.split(",")
        if len(parts) > 1: fname = parts[-1]
    
    fname = re.sub(r'_[a-f0-9]{8}\.', '.', fname)
    return fname

def _investment_image_prefix(image_url: str) -> str | None:
    fname = _cdn_filename(image_url)
    if "/" in fname:
        fname = fname.rsplit("/", 1)[-1]
        
    stem = fname.rsplit(".", 1)[0]
    stem = re.sub(r'-\d+$', '', stem)
    
    m = re.search(r"-\d{8}", stem)
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
            slug_match = re.search(r'/inwestycja/([^,]+)', inv_url)
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
        m = re.search(r"scale_(\d+)", url)
        scale = int(m.group(1)) if m else 0
        if fname not in by_filename or scale > by_filename[fname][0]:
            by_filename[fname] = (scale, url)
            
    return [v[1] for v in by_filename.values()]

def _extract_to_id(url: str) -> str | None:
    if not url: return None
    m = re.search(r",i(\d+)(?:[/?]|$)", url)
    return m.group(1) if m else None

def fetch_to_agency_name(url: str, fetcher: Fetcher) -> str | None:
    html = fetch_to_html(url, fetcher)
    if not html:
        return None
        
    product = parse_to_product(html)
    if isinstance(product.get("brand"), dict):
        name = product.get("brand", {}).get("name")
        if name: return name

    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    if h1_match:
        spans = re.findall(r"<span[^>]*>(.*?)</span>", h1_match.group(1), re.DOTALL)
        if len(spans) >= 2:
            dev_candidate = re.sub(r"<[^>]+>", "", spans[-1]).strip()
            if dev_candidate and len(dev_candidate) < 100:
                return dev_candidate

    dev_match = re.search(r'data-developer="([^"]+)"', html)
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
        if "page=" in page_url:            page_url = re.sub(r'page=\d+', f'page={current_page}', page_url)
        else:
            connector = "&" if "?" in page_url else "?"
            page_url += f"{connector}page={current_page}"

        logger.info(f"Discovering TabelaOfert investments from URL (page {current_page}): {page_url}")
        html = fetch_to_html(page_url, fetcher)
        if not html: 
            break
        
        page_offers = []
        matches = list(re.finditer(r'href="(/inwestycja/([^",]+),i(\d+))"', html))
        
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
            
            img_matches = list(re.finditer(r'src="(https?://content\.tabelaofert\.pl/[^"]+\.(?:webp|jpg|png|jpeg))"', window))
            
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
            dev_match = re.search(r'data-developer="([^"]+)"', window)
            if not dev_match:
                dev_match = re.search(r'<span>([^<]+)</span>', window)
            
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
        match = re.search(r'/inwestycja/([^,]+),i(\d+)', url)
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
    if developer_slug:
        logger.info(f"Matched TO klient-id {klient_id} to existing developer slug: {developer_slug}")

    # Resolve (if needed) and Update developer data using the internal API
    # If developer_slug is None, it will be resolved from the profile data
    to_dev_url = None
    if developer_slug:
        to_dev_url = portal_url("to", "developer", slug=developer_slug)
    else:
        # Try to find a temporary slug from HTML to build the profile URL
        m = re.search(r'\\?"klientKryterium\\?":\\?"([^"\\?]+)\\?"', html)
        temp_slug = m.group(1) if m else None
        if not temp_slug or temp_slug == "unknown":
            dev_links = re.findall(r'href="([^"]*/katalog-firm/deweloperzy/([^/"?#]+))"', html)
            city_slugs = {"warszawa", "krakow", "lodz", "wroclaw", "poznan", "gdansk", "szczecin", "bydgoszcz", "lublin", "bialystok", "katowice", "gdynia", "czestochowa", "radom"}
            for link, s in dev_links:
                if s not in city_slugs and s != "unknown":
                    temp_slug = s
                    break
        if temp_slug:
            to_dev_url = portal_url("to", "developer", slug=temp_slug)

    if to_dev_url:
        developer_slug = download_raw_to_dev_json(to_dev_url, developer_slug, fetcher, fetcher.config)
        if developer_slug:
            logger.info(f"Resolved/Updated developer '{developer_slug}' data from TabelaOfert.")

    if not developer_slug:
        return {"error": f"Failed to resolve developer_slug from API for klient-id {klient_id} from {url}"}
    
    # ID-based Investment Identification
    to_id = _extract_to_id(url)
    portal_id = f"i{to_id}" if to_id else None
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
        "raw_details": product,
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
            listing_url = re.sub(r'page=\d+', f'page={page}', listing_url)
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
    for m in re.finditer(r'href="https://tabelaofert\.pl(/katalog-firm/deweloperzy/([^"/?]+))"', html):
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
    page_nums = [int(n) for n in re.findall(r'href="[^"]*[?&]page=(\d+)"', html)]
    if page_nums:
        total_pages = max(page_nums)
    elif 'class="next"' in html or 'rel="next"' in html:
        total_pages = page + 1
    else:
        total_pages = page

    return DeveloperPage(developers=developers, total_pages=total_pages, page=page)
