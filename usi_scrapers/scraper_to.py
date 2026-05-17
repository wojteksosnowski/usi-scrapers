import re
import json
import logging
from pathlib import Path
from typing import Optional
from .fetcher import Fetcher
from .models import ScraperConfig, DeveloperPage
from .utils.io import save_raw_json, save_dev_raw_json, lookup_developer_by_id
from .utils.string import slugify
from .utils.portals import portal_api_url, portal_url, get_portal

from . import get_logger

logger = get_logger(__name__)

def download_raw_to_dev_json(url: str, dev_slug: str, fetcher: Fetcher, config: ScraperConfig) -> Path | None:
    """
    Downloads raw JSON for a TabelaOfert developer profile and saves it.
    Also downloads developer logo when found in the page HTML.
    """
    from .utils.images import download_developer_logo
    html = fetch_to_html(url, fetcher)
    if not html:
        logger.error(f"Failed to fetch TO HTML for {url}")
        return None

    data = extract_to_dev_data(html, url)

    logo_url = extract_to_dev_logo(html)
    if logo_url:
        data["logo_url"] = logo_url
        download_developer_logo(logo_url, dev_slug, config, portal_prefix="to")
    else:
        logger.debug(f"No logo URL found in TO developer page for {dev_slug}")

    return save_dev_raw_json(data, config.public_dir, dev_slug, "to", portal_id=data.get("url", url).rstrip("/").rsplit("/", 1)[-1], source_url=url)


def extract_to_dev_data(html: str, url: str) -> dict:
    """Extracts basic data from a TabelaOfert developer page."""
    data: dict = {"url": url}

    # Name from JSON-LD Organization/LocalBusiness
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    for s in scripts:
        for org_type in ('"Organization"', '"LocalBusiness"'):
            if org_type in s:
                try:
                    d = json.loads(s.strip())
                    items = d if isinstance(d, list) else [d]
                    for item in items:
                        if isinstance(item, dict) and item.get("@type") in ("Organization", "LocalBusiness"):
                            if item.get("name"):
                                data["name"] = item["name"]
                            break
                except Exception:
                    pass

    # Fallback name from <h1>
    if not data.get("name"):
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
        if h1:
            data["name"] = re.sub(r"<[^>]+>", "", h1.group(1)).strip() or None

    return data


def extract_to_dev_logo(html: str) -> str | None:
    """Extracts developer logo URL from TabelaOfert developer page HTML."""
    # 1. og:image meta tag — most stable
    og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if og:
        return og.group(1)
    og = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.IGNORECASE)
    if og:
        return og.group(1)

    # 2. <img> with class or alt containing "logo"
    img = re.search(r'<img[^>]+(?:class|alt)=["\'][^"\']*logo[^"\']*["\'][^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if img:
        return img.group(1)
    img = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]+(?:class|alt)=["\'][^"\']*logo[^"\']*["\']', html, re.IGNORECASE)
    if img:
        return img.group(1)

    return None

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

    data = extract_to_data(html, url, fetcher=fetcher)
    to_id = _extract_to_id(url)
    portal_id = f"i{to_id}" if to_id else None
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

def discover_to_listing(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None) -> list[dict]:
    """
    Discovers TabelaOfert investments from a listing page with pagination.
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
        page_url = base_url
        if "page=" in page_url:
            page_url = re.sub(r'page=\d+', f'page={current_page}', page_url)
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

def discover_to_investments(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None) -> list[dict]:
    if not identifier:
        all_results = []
        seen_ids = set()
        for url in config.to_discovery_urls:
            batch = discover_to_listing(config, fetcher, identifier=url, limit=limit)
            for item in batch:
                if item["id"] not in seen_ids:
                    all_results.append(item)
                    seen_ids.add(item["id"])
                    if limit and len(all_results) >= limit:
                        return all_results
        return all_results
        
    url = portal_url("to", "developer", slug=identifier)
    return discover_to_listing(config, fetcher, identifier=url, limit=limit)

def scrape_tabelaofert(url: str, fetcher: Fetcher) -> dict:
    logger.info(f"Scraping TabelaOfert: {url}")
    html = fetch_to_html(url, fetcher)
    if not html:
        return {"error": "Could not fetch HTML"}

    product = extract_to_data(html, url, fetcher=fetcher)
    brand_name = product.get("brand", {}).get("name", "") if isinstance(product.get("brand"), dict) else ""
    
    # Native slug extraction
    from .utils.url_parser import parse_url
    parsed = parse_url(url)
    investment_slug = parsed.get("investment_slug", "unknown")
    
    developer_slug = "unknown"
    # Search for developer profile link in HTML
    dev_link_match = re.search(r'href="/katalog-firm/deweloperzy/([^/"?#]+)"', html)
    if dev_link_match:
        to_dev_slug = dev_link_match.group(1)
        
        # ID-based lookup (highest priority) - using TO slug as the portal ID
        existing_slug = lookup_developer_by_id(fetcher.config.public_dir, "to", to_dev_slug)
        if existing_slug:
            developer_slug = existing_slug
            logger.info(f"Matched TO dev slug {to_dev_slug} to existing developer slug: {developer_slug}")
        else:
            developer_slug = to_dev_slug

        # Add/update developer in database
        if developer_slug != "unknown":
            full_dev_url = portal_url("to", "developer", slug=to_dev_slug)
            download_raw_to_dev_json(full_dev_url, developer_slug, fetcher, fetcher.config)
            logger.info(f"Saved developer '{developer_slug}' data from TabelaOfert.")
    
    ext_loc = product.get("_extracted_location", {})
    address = ext_loc.get("address")
    city = ext_loc.get("city")
    region = ext_loc.get("region")
    lat = ext_loc.get("latitude")
    lng = ext_loc.get("longitude")

    offers_data = product.get("offers", {})
    try:
        price_min = float(offers_data.get("lowPrice") or 0) or None
        price_max = float(offers_data.get("highPrice") or 0) or None
    except (TypeError, ValueError):
        price_min = price_max = None

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

    return {
        "source": "tabelaofert.pl",
        "to_id": _extract_to_id(url),
        "to_url": url,
        "developer_slug": developer_slug,
        "investment_slug": investment_slug,
        "name": product.get("name"),
        "developer_name": brand_name or None,
        "address": address,
        "city": city,
        "region": region,
        "latitude": lat,
        "longitude": lng,
        "price_min": price_min,
        "price_max": price_max,
        "properties_count": offers_data.get("offerCount"),
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
