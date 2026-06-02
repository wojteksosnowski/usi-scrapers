import json
import re
import logging
from pathlib import Path
from typing import Optional
from .fetcher import Fetcher
from .models import ScraperConfig, DeveloperPage
from .utils.io import save_raw_json, save_dev_raw_json, lookup_developer_by_id, lookup_investment_by_id
from .utils.portals import portal_url, get_portal
from .mapping import get_mapping, resolve_path
from .utils.url_parser import parse_url
from .utils.scrapers import generic_discover_investments, generic_download_dev_json, extract_logo_from_dict

from . import get_logger

logger = get_logger(__name__)


def _parse_otodom_slug(full_slug: str) -> tuple[str, str | None]:
    """Returns (clean_slug, hash_id) by stripping the Otodom -ID<hash> suffix."""
    if "-ID" in full_slug:
        parts = full_slug.split("-ID", 1)
        return parts[0], parts[1]
    if "ID" in full_slug:
        parts = full_slug.split("ID", 1)
        return parts[0], parts[1]
    return full_slug, None


def _parse_otodom_item(item: dict, offer_id=None) -> dict | None:
    """Extracts a normalised offer dict from an Otodom search result item."""
    oto_mapping = get_mapping("oto", "investment")
    
    # Use raw slug for URL to avoid redirects
    raw_slug = item.get("slug")
    if not raw_slug:
        return None
        
    _, hash_id = _parse_otodom_slug(raw_slug)
    # Prefer hash_id (e.g. 4fS6R) over numeric offer_id
    portal_id = hash_id or offer_id or resolve_path({"ad": item}, oto_mapping.get("id")) or item.get("id")
    
    return {
        "id": portal_id,
        "url": portal_url("oto", "investment", full_slug=raw_slug),
    }


def download_raw_otodom_dev_json(url: str, dev_slug: Optional[str], fetcher: Fetcher, config: ScraperConfig) -> Optional[str]:
    """
    Downloads raw JSON for an Otodom developer profile and saves it.
    Also downloads developer logo when found in __NEXT_DATA__.
    Returns the resolved developer slug.
    """
    def fetch_oto_props(u, f):
        html = fetch_otodom_html(u, f)
        return extract_next_data(html)

    def extract_id(props):
        advertiser = props.get("advertiser") or {}
        agency = props.get("agency") or {}
        owner = props.get("owner") or {}
        found_id = advertiser.get("id") or agency.get("id") or owner.get("id")
        if found_id:
            return found_id
            
        # Fallback for search-results style
        items = props.get("data", {}).get("searchAds", {}).get("items", [])
        if items and isinstance(items, list):
            return items[0].get("agency", {}).get("id")
        return None

    if not dev_slug and url:
        from .utils.url_parser import parse_url
        parsed = parse_url(url)
        dev_slug = parsed.get("developer_slug")

    data = fetch_oto_props(url, fetcher)
    if not data:
        logger.error(f"Failed to fetch Otodom developer data from {url}")
        return None

    if not dev_slug:
        dev_mapping = get_mapping("oto", "developer")
        slug_path = dev_mapping.get("slug")
        if slug_path:
            dev_slug = resolve_path(data, slug_path)
            
        if not dev_slug:
            # Fallback for search-results style
            items = data.get("data", {}).get("searchAds", {}).get("items", [])
            if items and isinstance(items, list):
                dev_slug = items[0].get("agency", {}).get("slug")
                
    return generic_download_dev_json(
        fetcher, config, url, dev_slug, "oto",
        fetch_func=lambda u, f: data, # reuse already fetched data
        extract_id_func=extract_id,
        extract_logo_func=extract_otodom_dev_logo,
        source_url=url
    )


def extract_otodom_dev_logo(page_props: dict) -> str | None:
    """Extracts logo URL from Otodom developer page __NEXT_DATA__ pageProps."""
    candidates = [
        "advertiser.logoUrl",
        "advertiser.logo",
        "agency.logo.url",
        "agency.logoUrl",
    ]
    logo = extract_logo_from_dict(page_props, candidates)
    if logo:
        return logo
        
    # Search in items (for search-results style developer pages)
    items = page_props.get("data", {}).get("searchAds", {}).get("items", [])
    if items and isinstance(items, list):
        agency = items[0].get("agency") or {}
        return agency.get("imageUrl") or agency.get("logoUrl")
        
    return None

def download_raw_otodom_json(url: str, dev_slug: str, inv_slug: str, fetcher: Fetcher, config: ScraperConfig) -> Path | None:
    """
    Downloads raw JSON for an Otodom investment and saves it to the database.
    Does not process images or adapt data.
    """
    html = fetch_otodom_html(url, fetcher)
    if not html:
        logger.error(f"Failed to fetch Otodom HTML for {url}")
        return None
        
    page_props = extract_next_data(html)
    if not page_props:
        logger.error(f"Failed to extract __NEXT_DATA__ for {url}")
        return None

    # Filter out non-developer offers
    owner_type = page_props.get("ad", {}).get("owner", {}).get("type")
    if owner_type in ("agency", "private"):
        logger.info(f"Skipping {url}: ad.owner.type is '{owner_type}' (only developer offers are allowed).")
        return None

    oto_mapping = get_mapping("oto", "investment")
    ad_url = resolve_path(page_props, oto_mapping.get("url")) or ""
    ad_slug = ad_url.rstrip("/").rsplit("/", 1)[-1] if ad_url else ""
    _, hash_part = _parse_otodom_slug(ad_slug)
    
    oto_portal_id = resolve_path(page_props, oto_mapping.get("id"))
    if not oto_portal_id and hash_part:
        oto_portal_id = f"ID{hash_part}"

    # Resolve Investment Slug (ID-based lookup)
    if oto_portal_id:
        existing_inv_slug = lookup_investment_by_id(config.public_dir, dev_slug, "oto", oto_portal_id)
        if existing_inv_slug:
            inv_slug = existing_inv_slug
            logger.info(f"Matched investment ID {oto_portal_id} to existing investment slug: {inv_slug}")

    return save_raw_json(page_props, config.public_dir, dev_slug, inv_slug, "oto", portal_id=oto_portal_id)

def fetch_otodom_html(url: str, fetcher: Fetcher) -> str:
    """Fetches the Otodom URL using the centralized Fetcher."""
    return fetcher.fetch(url) or ""

def extract_next_data(html: str) -> dict:
    """
    Extracts __NEXT_DATA__ JSON from the HTML source.
    """
    pattern = r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    
    if not match:
        logger.warning("Could not find __NEXT_DATA__ in Otodom HTML.")
        return {}
        
    try:
        data = json.loads(match.group(1))
        return data.get("props", {}).get("pageProps", {})
    except Exception as e:
        logger.error(f"Error parsing __NEXT_DATA__ JSON: {e}")
        return {}

def discover_otodom_investments(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None) -> list[dict]:
    """
    Discovers investments for a given agency ID on Otodom.pl.
    If identifier (agency_id) is None, performs global discovery using config.otodom_discovery_urls.
    Paginates via ?currentPage=N (page= and p= do not trigger SSR pagination).
    """
    if not identifier:
        logger.info("Performing global Otodom discovery via config URLs")
        return generic_discover_investments(
            config, fetcher, config.otodom_discovery_urls, discover_otodom_listing, limit=limit
        )

    base_url = f"https://www.otodom.pl/pl/firmy/deweloperzy/deweloper-ID{identifier}"
    logger.info(f"Discovering Otodom investments for agency ID: {identifier}")
    
    # Use discover_otodom_listing but with currentPage pagination
    return discover_otodom_listing(config, fetcher, base_url, limit, pagination_param="currentPage")

def discover_otodom_listing(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None, pagination_param: str = "page") -> list[dict]:
    """
    Discovers investments from a general Otodom listing URL (HTML with __NEXT_DATA__).
    Supports pagination. Max page size for Otodom is 72.
    """
    if not identifier:
        logger.error("discover_otodom_listing requires an identifier (URL)")
        return []

    url = identifier
    PAGE_SIZE = 72
    all_offers = []
    seen_ids = set()
    
    base_url = url
    if "limit=" not in base_url:
        connector = "&" if "?" in base_url else "?"
        base_url += f"{connector}limit={PAGE_SIZE}"
    else:
        base_url = re.sub(r'limit=\d+', f'limit={PAGE_SIZE}', base_url)

    current_page = 1
    
    while True:
        page_url = base_url
        if f"{pagination_param}=" in page_url:
            page_url = re.sub(rf'{pagination_param}=\d+', f'{pagination_param}={current_page}', page_url)
        else:
            connector = "&" if "?" in page_url else "?"
            page_url += f"{connector}{pagination_param}={current_page}"


        logger.info(f"Discovering Otodom investments from listing (page {current_page}): {page_url}")
        html = fetch_otodom_html(page_url, fetcher)
        if not html:
            break

        data = extract_next_data(html)
        if not data:
            break

        try:
            search_ads = data.get("data", {}).get("searchAds", {})
            if not search_ads:
                search_ads = data.get("searchAds", {})
                
            items = search_ads.get("items", [])
            if not items:
                logger.warning(f"discover_otodom_listing: no items on page {current_page} for {page_url}")
                break

            for item in items:
                offer_id = item.get("id")
                if offer_id in seen_ids:
                    continue
                seen_ids.add(offer_id)

                parsed = _parse_otodom_item(item, offer_id=offer_id)
                if parsed:
                    all_offers.append(parsed)
                    
                    if limit and len(all_offers) >= limit:
                        return all_offers

            # Check if there are more pages
            total_pages = search_ads.get("pagination", {}).get("totalPages", 0)
            if current_page >= total_pages:
                break
            
            current_page += 1
            
        except Exception as e:
            logger.error(f"Error parsing Otodom listing discovery data: {e}")
            break

    return all_offers

def fetch_otodom_agency_name(url: str, fetcher: Fetcher) -> str | None:
    """
    Fetches only the agency/developer name from Otodom detail page.
    """
    html = fetch_otodom_html(url, fetcher)
    if not html:
        return None
    data = extract_next_data(html)
    if not data:
        return None
    oto_mapping = get_mapping("oto", "investment")
    dev_name = resolve_path(data, oto_mapping.get("developer_name"))
    if dev_name:
        return dev_name
    
    search_ads = data.get("data", {}).get("searchAds", {})
    return search_ads.get("agency", {}).get("name") if search_ads.get("agency") else None

def scrape_otodom(url: str, fetcher: Fetcher) -> dict:
    """
    Main function to scrape Otodom investment and save images.
    """
    html = fetch_otodom_html(url, fetcher)
    if not html:
        return {"error": "Could not fetch HTML"}
        
    page_props = extract_next_data(html)
    if not page_props:
        return {"error": "Could not extract __NEXT_DATA__ JSON"}

    parsed = parse_url(url)
    investment_slug = parsed.get("investment_slug")
    hash_part = parsed.get("otodom_id")
    
    if not investment_slug:
        # Emergency fallback for URL parsing
        match = re.search(r'/(inwestycja|oferta)/([^/]+)', url)
        if match:
            full_slug = match.group(2)
            investment_slug, hash_part = _parse_otodom_slug(full_slug)
            
    if not investment_slug:
        return {"error": f"Could not determine investment_slug from URL: {url}"}
        
    developer_slug = None
        
    ad_data = page_props.get("ad", {})
    if not ad_data:
        # Fallback for search-based data
        ad_data = page_props.get("data", {}).get("searchAds", {})
        
    if not ad_data:
        return {"error": "Could not find investment data in page properties"}

    oto_mapping = get_mapping("oto", "investment")
    
    # ID resolution via mapping (Standardized on alphanumeric hash as primary ID)
    hash_id = resolve_path(page_props, oto_mapping.get("id"))
    numeric_id = resolve_path(page_props, oto_mapping.get("numeric_id"))
    investment_slug = resolve_path(page_props, oto_mapping.get("slug"))
    
    # Fallback to URL parsing if mapping fails (e.g. unexpected structure)
    if not investment_slug or not hash_id:
        parsed = parse_url(url)
        investment_slug = investment_slug or parsed.get("investment_slug")
        hash_id = hash_id or parsed.get("otodom_id")

    # Primary oto_portal_id used for lookups (Standardized on alphanumeric hash)
    oto_portal_id = hash_id or (f"ID{numeric_id}" if numeric_id else None)

    # Safeguard: Do not process inactive/archived listings to prevent overwriting images
    status = str(resolve_path(page_props, oto_mapping.get("status")) or "active").lower()
    if status not in ("active", "actual", "none", ""):
        logger.warning(f"Otodom listing is {status}: {url}. Skipping to protect local data.")
        return {"error": f"Listing is inactive (status: {status})"}
        
    images = []
    images_raw = resolve_path(page_props, oto_mapping.get("images")) or []
    for img in images_raw:
        img_url = img.get("large")
        if img_url:
            images.append(img_url)
            
    agency_url = resolve_path(page_props, oto_mapping.get("developer_url")) or ""
    agency_name = resolve_path(page_props, oto_mapping.get("developer_name")) or ""
    
    if not agency_name:
        agency_name = resolve_path(page_props, oto_mapping.get("owner_name")) or ""
        
    agency_id = resolve_path(page_props, oto_mapping.get("developer_id"))
    if not agency_id:
        dev_mapping = get_mapping("oto", "developer")
        agency_id = resolve_path(page_props, dev_mapping.get("id"))
    
    # ID-based lookup (highest priority)
    if agency_id:
        existing_slug = lookup_developer_by_id(fetcher.config.public_dir, "oto", agency_id)
        if existing_slug:
            developer_slug = existing_slug
            logger.info(f"Matched agency ID {agency_id} to existing developer slug: {developer_slug}")

    if agency_url:
        full_agency_url = agency_url if agency_url.startswith("http") else f"https://www.otodom.pl{agency_url}"
        
        # Resolve (if needed) and Update developer data using the internal API
        # If developer_slug is None, it will be resolved from the profile data
        fetched_slug = download_raw_otodom_dev_json(full_agency_url, developer_slug, fetcher, fetcher.config)
        if fetched_slug:
            developer_slug = fetched_slug
            logger.info(f"Resolved/Updated developer '{developer_slug}' data from Otodom.")
        else:
            logger.warning(f"Failed to extract slug from developer URL: {full_agency_url}")

    if not developer_slug:
        # Fallback to generating slug from agency_name if we have the ID and name
        if agency_name and agency_id:
            from .utils.string import slugify
            developer_slug = slugify(agency_name)
            logger.info(f"Fallback: Generated slug '{developer_slug}' from agency name '{agency_name}' (ID: {agency_id}).")
        elif not agency_id and not agency_url and agency_name:
             # Private seller / owner
             developer_slug = "private-seller"
        else:
             err_msg = (
                 f"Developer resolution failed for Otodom agency '{agency_name}' (ID: {agency_id}). "
                 f"Local ID lookup failed, and API download from developer URL '{full_agency_url if agency_url else 'None'}' did not yield a valid slug."
             )
             return {"error": err_msg}
            
    # Resolve Investment Slug (ID-based lookup)
    if oto_portal_id:
        existing_inv_slug = lookup_investment_by_id(fetcher.config.public_dir, developer_slug, "oto", oto_portal_id)
        if existing_inv_slug:
            investment_slug = existing_inv_slug
            logger.info(f"Matched investment ID {oto_portal_id} to existing investment slug: {investment_slug}")

    lat = resolve_path(page_props, oto_mapping.get("latitude"))
    lng = resolve_path(page_props, oto_mapping.get("longitude"))

    delivery_quarter = None
    delivery_year = None
    top_info = resolve_path(page_props, oto_mapping.get("delivery_raw")) or []
    for item in top_info:
        if item.get("label") == "project_finish_date":
            values = item.get("values", [])
            if values:
                try:
                    parts = values[0].split("-")
                    delivery_year = int(parts[0])
                    delivery_quarter = (int(parts[1]) - 1) // 3 + 1
                except Exception as e:
                    logger.warning(f"Could not parse project_finish_date '{values[0]}': {e}")
            break
            
    if delivery_quarter is None:
        delivery_quarter = resolve_path(page_props, oto_mapping.get("delivery_fallback_quarter"))
        delivery_year = resolve_path(page_props, oto_mapping.get("delivery_fallback_year"))

    # Extract agnostic signals
    signals = {}
    signal_mapping = oto_mapping.get("signals", {})
    for key, path in signal_mapping.items():
        signals[key] = resolve_path(page_props, path)

    result = {
        "source": "otodom.pl",
        "id": hash_id,
        "numeric_id": numeric_id,
        "url": url,
        "developer_slug": developer_slug,
        "investment_slug": investment_slug,
        "oto_url_id": oto_portal_id,
        "title": resolve_path(page_props, oto_mapping.get("name")),
        "agency_name": agency_name,
        "agency_id": agency_id,
        "latitude": lat,
        "longitude": lng,
        "delivery_quarter": delivery_quarter,
        "delivery_year": delivery_year,
        "properties_count": resolve_path(page_props, oto_mapping.get("units_count")),
        "price_min": resolve_path(page_props, oto_mapping.get("price_min")),
        "ceiling_height_min": resolve_path(page_props, oto_mapping.get("ceiling_height_min")),
        "ceiling_height_max": resolve_path(page_props, oto_mapping.get("ceiling_height_max")),
        "image_urls": images,
        "signals": signals,
        "raw_details": ad_data
    }

    return result


def discover_otodom_developers(
    fetcher: Fetcher,
    page: int = 1,
    base_url: Optional[str] = None,
) -> DeveloperPage:
    """Pobiera jedną stronę listy deweloperów z Otodom.

    Strona /firmy/deweloperzy/ to legacy PHP (brak __NEXT_DATA__) — parsujemy HTML.
    URL deweloperów: https://www.otodom.pl/pl/firmy/deweloperzy/{slug}-ID{id}
    """
    listing_url = base_url or get_portal("oto")["developer_list_url"].format(page=page)
    if base_url:
        if "page=" in listing_url:
            listing_url = re.sub(r'page=\d+', f'page={page}', listing_url)
        else:
            connector = "&" if "?" in listing_url else "?"
            listing_url = f"{listing_url}{connector}page={page}"

    html = fetch_otodom_html(listing_url, fetcher)
    if not html:
        logger.error(f"Failed to fetch Otodom developer listing: {listing_url}")
        return DeveloperPage(developers=[], total_pages=1, page=page)

    # Extract developer links + names from legacy HTML
    # Pattern: href="https://www.otodom.pl/pl/firmy/deweloperzy/{slug}-ID{id}">Name<
    seen_urls: set[str] = set()
    developers = []
    for m in re.finditer(
        r'href="(https://www\.otodom\.pl/pl/firmy/deweloperzy/([^"]+)-ID(\d+))"[^>]*>\s*([^<]+?)\s*<',
        html,
    ):
        url, slug, agency_id, name = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        if url in seen_urls:
            continue
        seen_urls.add(url)
        developers.append({
            "url": url,
            "name": name or None,
            "slug": slug,
        })

    # Determine total_pages from paginator ?page=N links
    page_nums = [int(n) for n in re.findall(r'[?&]page=(\d+)', html)]
    total_pages = max(page_nums) if page_nums else page

    if not developers:
        logger.warning(f"Otodom developer listing: no developers found on page {page} ({listing_url})")

    return DeveloperPage(developers=developers, total_pages=total_pages, page=page)
