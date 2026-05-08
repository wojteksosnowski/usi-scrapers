import json
import re
import logging
from pathlib import Path
from .fetcher import Fetcher
from .models import ScraperConfig
from .utils.io import save_raw_json, save_dev_raw_json

logger = logging.getLogger(__name__)

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

def discover_otodom_investments(agency_id: str, fetcher: Fetcher) -> list[dict]:
    """
    Discovers investments for a given agency ID on Otodom.pl.
    """
    url = f"https://www.otodom.pl/pl/firmy/deweloperzy/deweloper-ID{agency_id}"
    logger.info(f"Discovering Otodom investments for agency ID: {agency_id}")

    html = fetch_otodom_html(url, fetcher)
    if not html:
        return []

    data = extract_next_data(html)
    if not data:
        return []

    offers = []
    try:
        search_ads = data.get("data", {}).get("searchAds", {})
        if not search_ads:
            search_ads = data.get("searchAds", {})
            
        items = search_ads.get("items", [])

        for item in items:
            full_slug = item.get("slug")
            if full_slug:
                clean_slug = full_slug
                hash_id = None
                
                if "-ID" in full_slug:
                    parts = full_slug.split("-ID")
                    clean_slug = parts[0]
                    hash_id = parts[1]
                elif "ID" in full_slug:
                    parts = full_slug.split("ID")
                    clean_slug = parts[0]
                    hash_id = parts[1]

                img_data = item.get("images", [])
                img_url = img_data[0].get("medium") if img_data else None
                
                agency_name = item.get("agency", {}).get("name")
                if not agency_name:
                    agency_name = item.get("advertiser", {}).get("name")

                offers.append({
                    "id": item.get("id"), 
                    "hash_id": hash_id,   
                    "url": f"https://www.otodom.pl/pl/oferta/{full_slug}",
                    "name": item.get("title"),
                    "slug": clean_slug,   
                    "full_slug": full_slug,
                    "image": img_url,
                    "developer": agency_name
                })
    except Exception as e:
        logger.error(f"Error parsing Otodom discovery data: {e}")

    return offers

def discover_otodom_listing(url: str, fetcher: Fetcher) -> list[dict]:
    """
    Discovers investments from a general Otodom listing URL (HTML with __NEXT_DATA__).
    """
    logger.info(f"Discovering Otodom investments from listing: {url}")
    html = fetch_otodom_html(url, fetcher)
    if not html:
        return []

    data = extract_next_data(html)
    if not data:
        return []

    offers = []
    try:
        search_ads = data.get("data", {}).get("searchAds", {})
        if not search_ads:
            search_ads = data.get("searchAds", {})
            
        items = search_ads.get("items", [])
        for item in items:
            full_slug = item.get("slug")
            if full_slug:
                clean_slug = full_slug
                hash_id = None
                
                if "-ID" in full_slug:
                    parts = full_slug.split("-ID")
                    clean_slug = parts[0]
                    hash_id = parts[1]
                elif "ID" in full_slug:
                    parts = full_slug.split("ID")
                    clean_slug = parts[0]
                    hash_id = parts[1]

                img_data = item.get("images", [])
                img_url = img_data[0].get("medium") if img_data else None

                agency_name = item.get("agency", {}).get("name")
                if not agency_name:
                    agency_name = item.get("advertiser", {}).get("name")

                offers.append({
                    "id": item.get("id"), 
                    "hash_id": hash_id,   
                    "url": f"https://www.otodom.pl/pl/inwestycja/{full_slug}",
                    "name": item.get("title"),
                    "slug": clean_slug,   
                    "full_slug": full_slug,
                    "image": img_url,
                    "developer": agency_name
                })
    except Exception as e:
        logger.error(f"Error parsing Otodom listing discovery data: {e}")

    return offers

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
                except Exception:
                    pass
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
