import json
import re
import logging
from pathlib import Path
from .fetcher import Fetcher
from .models import ScraperConfig
from .utils.io import save_raw_json, save_dev_raw_json

logger = logging.getLogger(__name__)


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
    full_slug = item.get("slug")
    if not full_slug:
        return None
    clean_slug, hash_id = _parse_otodom_slug(full_slug)
    img_data = item.get("images", [])
    img_url = img_data[0].get("medium") if img_data else None
    agency_name = item.get("agency", {}).get("name") or item.get("advertiser", {}).get("name")
    return {
        "id": offer_id or item.get("id"),
        "hash_id": hash_id,
        "url": f"https://www.otodom.pl/pl/oferta/{full_slug}",
        "name": item.get("title"),
        "slug": clean_slug,
        "full_slug": full_slug,
        "image": img_url,
        "developer": agency_name,
    }


def download_raw_otodom_dev_json(url: str, dev_slug: str, fetcher: Fetcher, config: ScraperConfig) -> Path | None:
    """
    Downloads raw JSON for an Otodom developer profile and saves it.
    """
    html = fetch_otodom_html(url, fetcher)
    if not html:
        logger.error(f"Failed to fetch Otodom HTML for {url}")
        return None
        
    page_props = extract_next_data(html)
    if not page_props:
        logger.error(f"Failed to extract __NEXT_DATA__ for {url}")
        return None

    page_props["url"] = url
    return save_dev_raw_json(page_props, config.public_dir, dev_slug, "oto")

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

    page_props["url"] = url
    return save_raw_json(page_props, config.public_dir, dev_slug, inv_slug, "oto")

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
        all_results = []
        seen_ids = set()
        for url in config.otodom_discovery_urls:
            batch = discover_otodom_listing(config, fetcher, identifier=url, limit=limit)
            for item in batch:
                if item["id"] not in seen_ids:
                    all_results.append(item)
                    seen_ids.add(item["id"])
                    if limit and len(all_results) >= limit:
                        return all_results
        return all_results

    base_url = f"https://www.otodom.pl/pl/firmy/deweloperzy/deweloper-ID{identifier}"
    logger.info(f"Discovering Otodom investments for agency ID: {identifier}")

    offers = []
    seen_ids = set()
    current_page = 1

    while True:
        url = base_url if current_page == 1 else f"{base_url}?currentPage={current_page}"
        html = fetch_otodom_html(url, fetcher)
        if not html:
            break

        data = extract_next_data(html)
        if not data:
            break

        try:
            search_ads = data.get("searchAds") or data.get("data", {}).get("searchAds", {})
            items = search_ads.get("items", [])
            if not items:
                break

            for item in items:
                offer_id = item.get("id")
                if offer_id in seen_ids:
                    continue
                seen_ids.add(offer_id)
                parsed = _parse_otodom_item(item)
                if parsed:
                    offers.append(parsed)
                    if limit and len(offers) >= limit:
                        return offers

            pagination = search_ads.get("pagination", {})
            if current_page >= pagination.get("totalPages", 1):
                break
            current_page += 1
        except Exception as e:
            logger.error(f"Error parsing Otodom discovery data: {e}")
            break

    return offers

def discover_otodom_listing(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None) -> list[dict]:
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
        if "page=" in page_url:
            page_url = re.sub(r'page=\d+', f'page={current_page}', page_url)
        else:
            connector = "&" if "?" in page_url else "?"
            page_url += f"{connector}page={current_page}"

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
    
    ad_data = data.get("ad", {})
    if not ad_data:
        ad_data = data.get("data", {}).get("searchAds", {})
    
    if not ad_data:
        return None
        
    return ad_data.get("agency", {}).get("name") if ad_data.get("agency") else None

def scrape_otodom(url: str, developer_slug: str, investment_slug: str, fetcher: Fetcher) -> dict:
    """
    Main function to scrape Otodom investment and save images.
    """
    html = fetch_otodom_html(url, fetcher)
    if not html:
        return {"error": "Could not fetch HTML"}
        
    page_props = extract_next_data(html)
    if not page_props:
        return {"error": "Could not extract __NEXT_DATA__ JSON"}
        
    ad_data = page_props.get("ad", {})
    if not ad_data:
        # Fallback for search-based data
        ad_data = page_props.get("data", {}).get("searchAds", {})
        
    if not ad_data:
        return {"error": "Could not find investment data in page properties"}
        
    images = []
    images_raw = ad_data.get("images", [])
    for img in images_raw:
        img_url = img.get("large")
        if img_url:
            images.append(img_url)
            
    agency_data = ad_data.get("agency") or {}
    agency_url = agency_data.get("url", "")
    agency_name = agency_data.get("name", "")
    
    # If no agency but it is private/unknown, try to use owner name
    if not agency_name:
        owner_data = ad_data.get("owner") or {}
        agency_name = owner_data.get("name") or "Nieznany Deweloper"

    if agency_url:
        dev_match = re.search(r'(?<=/)[^/]+(?=-ID)', agency_url)
        if dev_match:
            developer_slug = dev_match.group(0)
            logger.info(f"Extracted developer slug from Otodom: {developer_slug}")
        elif developer_slug in ("otodom", "unknown") and agency_name:
            from .utils.string import slugify
            developer_slug = slugify(agency_name)
            logger.info(f"Resolved developer slug from Otodom agency name: {developer_slug}")
    elif developer_slug in ("otodom", "unknown") and agency_name:
        from .utils.string import slugify
        developer_slug = slugify(agency_name)
        logger.info(f"Resolved developer slug from Otodom agency name: {developer_slug}")
            
    coords = ad_data.get("location", {}).get("coordinates") or {}
    lat = coords.get("latitude")
    lng = coords.get("longitude")

    delivery_quarter = None
    delivery_year = None
    for item in ad_data.get("topInformation", []):
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
        old_delivery = ad_data.get("investmentEstimatedDelivery") or {}
        delivery_quarter = old_delivery.get("quarter")
        delivery_year = old_delivery.get("year")

    ad_data["url"] = url
    ad_data["image_urls"] = images
    
    result = {
        "source": "otodom.pl",
        "url": url,
        "developer_slug": developer_slug,
        "investment_slug": investment_slug,
        "title": ad_data.get("title"),
        "agency_name": agency_name,
        "agency_id": agency_data.get("id"),
        "latitude": lat,
        "longitude": lng,
        "delivery_quarter": delivery_quarter,
        "delivery_year": delivery_year,
        "image_urls": images,
        "raw_details": ad_data
    }
    
    return result
