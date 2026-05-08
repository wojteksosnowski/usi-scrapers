import re
import json
import logging
from pathlib import Path
from .fetcher import Fetcher
from .models import ScraperConfig
from .utils.io import save_raw_json, save_dev_raw_json
from .utils.string import slugify

logger = logging.getLogger(__name__)

def download_raw_to_dev_json(url: str, dev_slug: str, fetcher: Fetcher, config: ScraperConfig) -> Path | None:
    """
    Downloads raw JSON for a TabelaOfert developer profile and saves it.
    """
    html = fetch_to_html(url, fetcher)
    if not html:
        logger.error(f"Failed to fetch TO HTML for {url}")
        return None

    data = extract_to_data(html, url)
    return save_dev_raw_json(data, config.public_dir, dev_slug, "to")

def extract_to_data(html: str, url: str) -> dict:
    """
    Centralized extraction logic for TabelaOfert.
    Combines JSON-LD, RSC fragments, and H1 analysis.
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

    if (not street or not city) and data.get("description"):
        desc = data.get("description", "")
        parts_segments = re.split(r"[✔️➤]", desc)
        for segment in parts_segments:
            segment = segment.strip()
            if "ul." in segment or (city and city in segment):
                parts = [p.strip() for p in segment.split(",")]
                if len(parts) >= 2:
                    city = parts[0]
                    street = parts[-1]
                    break
    
    address = ", ".join(filter(None, [street, city])) or None
    
    data["_extracted_location"] = {
        "address": address,
        "city": city,
        "region": region,
        "latitude": lat,
        "longitude": lng
    }

    # 3. Gallery
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

    data = extract_to_data(html, url)
    return save_raw_json(data, config.public_dir, dev_slug, inv_slug, "to")

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
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    for s in scripts:
        if '"galeria"' in s and '"zdjecia"' in s:
            urls = re.findall(r'\\"url\\":\\"(https?://content\.tabelaofert\.pl/[^\\]+)', s)
            if urls:
                found_urls.extend([u.rstrip('"') for u in urls])
                
    regex = r'(?:https?:)?//content\.tabelaofert\.pl/[^\s\"\\<>]+\.(?:webp|jpg|jpeg|png)'
    found = re.findall(regex, html, re.IGNORECASE)
    for u in found:
        if u.startswith("//"):
            found_urls.append("https:" + u)
        else:
            found_urls.append(u)
            
    return list(dict.fromkeys(found_urls))

def _cdn_filename(url: str) -> str:
    fname = url.rsplit("/", 1)[-1]
    m = re.search(r"[^/]+-/(.+)$", url)
    if m: fname = m.group(1)
    else:
        parts = fname.split(",")
        if len(parts) > 1: fname = parts[-1]
    fname = re.sub(r'_[a-f0-9]{8}\.', '.', fname)
    return fname

def _investment_image_prefix(image_url: str) -> str | None:
    fname = _cdn_filename(image_url)
    stem = fname.rsplit(".", 1)[0]
    stem = re.sub(r'-\d+$', '', stem)
    
    m = re.search(r"-\d{8}", stem)
    if m:
        return stem[: m.start()]
    
    parts = stem.split("-")
    if len(parts) > 3:
        return "-".join(parts[:4])
    return "-".join(parts)

def filter_investment_images(urls: list[str], product: dict) -> list[str]:
    main_image = product.get("image")
    if isinstance(main_image, list) and main_image:
        main_image = main_image[0]
        
    prefix = _investment_image_prefix(str(main_image)) if main_image else None
    candidates = []
    for url in urls:
        fname = _cdn_filename(url)
        if any(fname.startswith(p) for p in ["mapa-", "logo-", "icon-", "avatar-"]):
            continue
            
        if prefix and not fname.startswith(prefix):
            prefix_parts = prefix.split("-")
            short_prefix = "-".join(prefix_parts[:3]) if len(prefix_parts) > 2 else prefix
            if not fname.startswith(short_prefix):
                continue
        
        candidates.append(url)

    if not candidates and urls:
        for url in candidates:
            fname = _cdn_filename(url)
            if not any(fname.startswith(p) for p in ["mapa-", "logo-", "icon-", "avatar-"]):
                candidates.append(url)

    by_filename: dict[str, tuple[int, str]] = {}
    for url in candidates:
        fname = _cdn_filename(url)
        m = re.search(r"scale_(\d+)", url)
        scale = int(m.group(1)) if m else 0
        if fname not in by_filename or scale > by_filename[fname][0]:
            by_filename[fname] = (scale, url)
            
    return [v[1] for v in by_filename.values()]

def _extract_to_id(url: str) -> str | None:
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

def discover_to_listing(url: str, fetcher: Fetcher) -> list[dict]:
    logger.info(f"Discovering TabelaOfert investments from URL: {url}")
    html = fetch_to_html(url, fetcher)
    if not html: return []
    
    offers = []
    seen_ids = set()

    matches = list(re.finditer(r'href="(/inwestycja/([^",]+),i(\d+))"', html))
    
    for m in matches:
        full_path, slug_part, to_id = m.groups()
        if to_id in seen_ids: continue
        seen_ids.add(to_id)
        
        full_url = f"https://tabelaofert.pl{full_path}"
        name = slug_part.replace("-", " ").title()
        
        start_search = max(0, m.start() - 2000)
        end_search = min(len(html), m.end() + 1000)
        window = html[start_search:end_search]
        
        img_matches = list(re.finditer(r'src="(https?://content\.tabelaofert\.pl/[^"]+\.(?:webp|jpg|png|jpeg))"', window))
        image_url = img_matches[-1].group(1) if img_matches else None

        dev_name = None
        dev_match = re.search(r'data-developer="([^"]+)"', window)
        if not dev_match:
            dev_match = re.search(r'<span>([^<]+)</span>', window)
        
        if dev_match:
            dev_name = dev_match.group(1).strip()

        offers.append({
            "id": to_id,
            "url": full_url,
            "name": name,
            "slug": slug_part,
            "image": image_url,
            "developer": dev_name
        })
            
    return offers

def discover_to_investments(dev_slug_or_id: str | None, fetcher: Fetcher, config: ScraperConfig) -> list[dict]:
    if not dev_slug_or_id:
        all_results = []
        seen_ids = set()
        for url in config.to_discovery_urls:
            batch = discover_to_listing(url, fetcher)
            for item in batch:
                if item["id"] not in seen_ids:
                    all_results.append(item)
                    seen_ids.add(item["id"])
        return all_results
        
    url = f"https://tabelaofert.pl/katalog-firm/deweloperzy/{dev_slug_or_id}"
    return discover_to_listing(url, fetcher)

def scrape_tabelaofert(url: str, dev_slug: str, inv_slug: str, fetcher: Fetcher) -> dict:
    logger.info(f"Scraping TabelaOfert: {url}")
    html = fetch_to_html(url, fetcher)
    if not html:
        return {"error": "Could not fetch HTML"}

    product = extract_to_data(html, url)
    
    brand_name = product.get("brand", {}).get("name", "") if isinstance(product.get("brand"), dict) else ""
    if dev_slug in ("unknown", "tabelaofert") and brand_name:
        from .utils.string import slugify
        resolved_dev_slug = slugify(brand_name)
        if resolved_dev_slug:
            dev_slug = resolved_dev_slug

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
    filtered_urls = filter_investment_images(gallery_urls, product)
    
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
        "developer_slug": dev_slug,
        "investment_slug": inv_slug,
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
