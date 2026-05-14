import logging
import json
import math
import re
from pathlib import Path
from typing import Optional
from .fetcher import Fetcher
from .models import ScraperConfig, DeveloperPage
from .utils.io import save_raw_json, save_dev_raw_json
from .utils.stage_detector import extract_groups_id, extract_stages

from . import get_logger

logger = get_logger(__name__)

def download_raw_rp_dev_json(vendor_id_or_slug: str, dev_slug: str, fetcher: Fetcher, config: ScraperConfig) -> Path | None:
    """
    Downloads raw JSON for an RP developer profile and saves it.
    Also downloads developer logo when found in the API response.
    """
    from .utils.images import download_developer_logo
    profile = fetch_rp_developer_profile(vendor_id_or_slug, fetcher)
    if not profile:
        logger.error(f"Failed to fetch RP developer profile for {vendor_id_or_slug}")
        return None

    logo_url = extract_rp_dev_logo(profile)
    if logo_url:
        download_developer_logo(logo_url, dev_slug, config, portal_prefix="rp")
    else:
        logger.debug(f"No logo URL found in RP developer profile for {dev_slug}")

    return save_dev_raw_json(profile, config.public_dir, dev_slug, "rp")


def extract_rp_dev_logo(profile: dict) -> str | None:
    """Extracts logo URL from RP vendor API response."""
    for field in ("logo", "logo_url", "image"):
        val = profile.get(field)
        if isinstance(val, str) and val.startswith("http"):
            return val
        if isinstance(val, dict):
            url = val.get("url") or val.get("src")
            if url and isinstance(url, str) and url.startswith("http"):
                return url
    return None

def fetch_rp_developer_profile(vendor_id_or_slug: str, fetcher: Fetcher) -> dict:
    """
    Fetches developer profile from RynekPierwotny.pl API.
    """
    vendor_id = vendor_id_or_slug
    if not str(vendor_id_or_slug).isdigit():
        vendor_id = resolve_rp_vendor_id(vendor_id_or_slug, fetcher)
        if not vendor_id:
            logger.error(f"Could not resolve vendor ID for slug: {vendor_id_or_slug}")
            return {}

    url = f"https://rynekpierwotny.pl/api/v2/vendors/vendor/{vendor_id}/?s=vendor-detail"
    logger.info(f"Fetching RynekPierwotny developer profile for ID: {vendor_id} from {url}")
    return fetcher.fetch_json(url, use_scraperapi=False) or {}

def download_raw_rp_json(offer_id: str, dev_slug: str, inv_slug: str, fetcher: Fetcher, config: ScraperConfig) -> Path | None:
    """
    Downloads raw JSON for an RP investment (details + gallery) and saves it to the database.
    Does not process images or adapt data.
    """
    details = fetch_rp_details(offer_id, fetcher)
    if not details:
        logger.error(f"Failed to fetch RP details for ID {offer_id}")
        return None

    # Also fetch gallery to make the raw JSON complete
    gallery_data = fetcher.fetch_json(f"https://rynekpierwotny.pl/api/v2/offers/offer/{offer_id}/?s=offer-detail-gallery", use_scraperapi=False)
    if gallery_data:
        details["_raw_gallery"] = gallery_data

    return save_raw_json(details, config.public_dir, dev_slug, inv_slug, "rp")

def fetch_rp_details(offer_id: str, fetcher: Fetcher) -> dict:
    """
    Fetches investment details from RynekPierwotny.pl API v2.
    """
    url = f"https://rynekpierwotny.pl/api/v2/offers/offer/{offer_id}/?s=offer-detail"
    logger.info(f"Fetching RynekPierwotny details for ID: {offer_id} from {url}")
    return fetcher.fetch_json(url, use_scraperapi=False) or {}

def fetch_rp_gallery(offer_id: str, fetcher: Fetcher) -> list[str]:
    """
    Fetches image URLs from RynekPierwotny.pl gallery API.
    """
    url = f"https://rynekpierwotny.pl/api/v2/offers/offer/{offer_id}/?s=offer-detail-gallery"
    logger.info(f"Fetching RynekPierwotny gallery for ID: {offer_id} from {url}")
    
    data = fetcher.fetch_json(url, use_scraperapi=False) or {}
    # Extract images from gallery
    images = []
    gallery = data.get("gallery", [])
    for item in gallery:
        # Prefer 1500 resolution
        img_url = item.get("image", {}).get("g_img_1500")
        if img_url:
            images.append(img_url)
                
    return images

def resolve_rp_vendor_id(slug: str, fetcher: Fetcher) -> str | None:
    """
    Scrapes the developer profile page on RynekPierwotny.pl to find their vendor ID.
    """
    url = f"https://rynekpierwotny.pl/deweloperzy/{slug}/"
    logger.info(f"Resolving RP vendor ID for slug: {slug} from {url}")
    html = fetcher.fetch(url, use_scraperapi=False)
    if not html:
        return None
    
    # Look for "vendor": ID in the page source or API calls mentioned in scripts
    match = re.search(r'["\']vendor["\']:\s*(\d+)', html)
    if match:
        return match.group(1)
        
    match = re.search(r'"vendor_id":\s*(\d+)', html)
    if match:
        return match.group(1)
    
    match = re.search(r'vendor=(\d+)', html)
    if match:
        return match.group(1)

    # Fallback: Check if slug ends with numeric ID (e.g. dom-development-sa-955)
    slug_parts = slug.strip("/").split("-")
    if slug_parts and slug_parts[-1].isdigit():
        return slug_parts[-1]

    logger.warning(f"Could not resolve RP vendor ID for slug '{slug}' — all patterns failed")
    return None

def discover_rp_investments(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None) -> list[dict]:
    """
    Discovers investments on RynekPierwotny.pl.
    If identifier (vendor_id or slug) is provided, scans that developer.
    Otherwise, uses global offer-list queries with pagination.
    RP has a max page size of 30.
    """
    PAGE_SIZE = 30
    all_results = []
    seen_ids = set()

    def fetch_page(url_template, page):
        url = url_template.replace("page=1", f"page={page}").replace("page_size=100", f"page_size={PAGE_SIZE}")
        if "page=" not in url:
            connector = "&" if "?" in url else "?"
            url += f"{connector}page={page}&page_size={PAGE_SIZE}"
        
        logger.info(f"Discovering RP investments via query (page {page}): {url}")
        data = fetcher.fetch_json(url, use_scraperapi=False) or {}
        batch = _parse_rp_results(data.get("results", []))
        
        new_count = 0
        for item in batch:
            if item["id"] not in seen_ids:
                all_results.append(item)
                seen_ids.add(item["id"])
                new_count += 1
                if limit and len(all_results) >= limit:
                    return False
        
        # If batch is smaller than page size, we reached the end
        if len(batch) < PAGE_SIZE:
            return False
        return True

    if identifier:
        vendor_id = identifier
        if not str(identifier).isdigit():
            vendor_id = resolve_rp_vendor_id(identifier, fetcher)
            if not vendor_id:
                logger.error(f"Could not resolve vendor ID for slug: {identifier}")
                return []
        
        url_template = f"https://rynekpierwotny.pl/api/v2/offers/offer/?s=vendor-detail-offer-list&country=1&country=2&limited_presentation=false&page=1&page_size={PAGE_SIZE}&vendor={vendor_id}"
        page = 1
        while fetch_page(url_template, page):
            page += 1
    else:
        # Global discovery
        urls = []
        if hasattr(config, "rp_discovery_urls") and config.rp_discovery_urls:
            urls = config.rp_discovery_urls
        else:
            urls = ["https://rynekpierwotny.pl/api/v2/offers/offer/?s=offer-list&display_type=1&distance=5&for_sale=true&limited_presentation=false&page=1&page_size=30&show_on_listing=true&type=1"]
            
        for url_template in urls:
            page = 1
            while fetch_page(url_template, page):
                page += 1
            if limit and len(all_results) >= limit:
                break
                
    return all_results[:limit] if limit else all_results

def _parse_rp_results(results: list) -> list[dict]:
    """Helper to parse RP API results and flatten stages."""
    offers = []
    for item in results:
        def get_val(obj, key):
            if not obj or not isinstance(obj, dict): return None
            v = obj.get(key)
            if isinstance(v, dict) and "value" in v:
                return v["value"]
            return v

        parent_name = item.get("name")
        parent_id = str(item.get("id"))
        
        v_data_parent = get_val(item, "vendor") or {}
        v_name_parent = v_data_parent.get("name")
        v_slug_parent = v_data_parent.get("slug")

        parent_img = None
        main_img_data = item.get("main_image")
        if main_img_data:
            if isinstance(main_img_data, str): parent_img = main_img_data
            elif isinstance(main_img_data, dict):
                parent_img = main_img_data.get("m_img_1500") or main_img_data.get("m_img_500") or main_img_data.get("image")
        
        if not parent_img:
            gallery = item.get("gallery")
            if gallery and isinstance(gallery, list) and len(gallery) > 0:
                first_img = gallery[0].get("image")
                if isinstance(first_img, dict):
                    parent_img = first_img.get("g_img_1500") or first_img.get("g_img_500") or first_img.get("image")
                elif isinstance(first_img, str):
                    parent_img = first_img

        groups = get_val(item, "groups") or {}
        stages = get_val(groups, "stages") or []
        
        if stages:
            for stage in stages:
                s_id_internal = stage.get("id")
                s_offer_val = get_val(stage, "offer")
                
                if s_offer_val:
                    s_id = str(s_offer_val.get("id"))
                    s_name = s_offer_val.get("name")
                    s_slug = s_offer_val.get("slug")
                    s_vendor_val = get_val(s_offer_val, "vendor") or {}
                    s_vendor_slug = s_vendor_val.get("slug") or v_slug_parent
                    s_vendor_name = s_vendor_val.get("name") or v_name_parent
                    
                    s_img = None
                    s_main_photo = get_val(s_offer_val, "main_photo") or get_val(s_offer_val, "main_image")
                    if s_main_photo:
                        if isinstance(s_main_photo, str): s_img = s_main_photo
                        elif isinstance(s_main_photo, dict):
                            s_img = s_main_photo.get("image") or s_main_photo.get("m_img_1500")
                    
                    if not s_img:
                        s_img = parent_img
                    
                    offers.append({
                        "id": s_id,
                        "url": f"https://rynekpierwotny.pl/oferty/{s_vendor_slug}/{s_slug}-{s_id}/?show_sold_stage=true&stage={s_id_internal}",
                    })
        else:
            v_data = get_val(item, "vendor") or {}
            v_slug = v_data.get("slug") or v_slug_parent
            o_id = str(item.get("id"))
            o_slug = item.get("slug")
            
            offers.append({
                "id": o_id,
                "url": f"https://rynekpierwotny.pl/oferty/{v_slug}/{o_slug}-{o_id}/",
            })
            
    return offers

def scrape_rynek_pierwotny(offer_id: str, fetcher: Fetcher, url: str = None) -> dict:
    """
    Main function to scrape RynekPierwotny investment.
    """
    details = fetch_rp_details(offer_id, fetcher)
    if not details:
        return {"error": "Could not fetch details"}
        
    gallery_data = fetcher.fetch_json(f"https://rynekpierwotny.pl/api/v2/offers/offer/{offer_id}/?s=offer-detail-gallery", use_scraperapi=False)
    if gallery_data:
        details["_raw_gallery"] = gallery_data
        
    gallery_urls = []
    if gallery_data:
        gallery = gallery_data.get("gallery", [])
        for item in gallery:
            img_url = item.get("image", {}).get("g_img_1500")
            if img_url:
                gallery_urls.append(img_url)
    
    main_image = details.get("main_image", {}).get("m_img_500")
    if main_image:
        gallery_urls.insert(0, main_image)
        
    def get_val(data, key, default=None):
        if not data or key not in data:
            return default
        val = data[key]
        if isinstance(val, dict) and "value" in val:
            return val["value"]
        return val

    vendor_data = get_val(details, "vendor")
    developer_slug = get_val(vendor_data, "slug") if vendor_data else "unknown"
    vendor_id = vendor_data.get("id") if vendor_data else None
    investment_slug = details.get("slug", "unknown")

    # Add developer to database (save raw JSON)
    if vendor_id and developer_slug != "unknown":
        download_raw_rp_dev_json(str(vendor_id), developer_slug, fetcher, fetcher.config)
        logger.info(f"Added developer '{developer_slug}' to database from RynekPierwotny.")

    if not url and developer_slug != "unknown" and investment_slug != "unknown":
        url = f"https://rynekpierwotny.pl/oferty/{developer_slug}/{investment_slug}-{offer_id}/"
        
    details["url"] = url
    geo_point = get_val(details, "geo_point")
    coords = get_val(geo_point, "coordinates") if geo_point else None
    
    construction_date = get_val(details, "construction_date_range")
    const_upper = get_val(construction_date, "upper") if construction_date else None

    stages = extract_stages(details)
    groups_id = extract_groups_id(details)
    groups = details.get("groups") or {}

    stage_sort = None
    stage_is_current = None
    for s in stages:
        if str(s["offer_id"]) == str(offer_id):
            stage_sort = s["sort"]
            stage_is_current = s["current"]
            break

    details["image_urls"] = gallery_urls
    sibling_stages = stages
    sibling_stage_folders = [
        f"{developer_slug}/{s['slug']}"
        for s in stages
        if str(s["offer_id"]) != str(offer_id) and s["slug"]
    ]

    result = {
        "source": "rynekpierwotny.pl",
        "id": offer_id,
        "url": url,
        "developer_slug": developer_slug,
        "investment_slug": investment_slug,
        "name": details.get("name"),
        "address": details.get("address"),
        "geo_point": coords,
        "latitude": coords[1] if coords and len(coords) > 1 else None,
        "longitude": coords[0] if coords and len(coords) > 0 else None,
        "construction_date_upper": const_upper,
        "website": details.get("website"),
        "properties_count": details.get("properties"),
        "image_urls": gallery_urls,
        "groups_id": groups_id,
        "groups_name": groups.get("name"),
        "stage_sort": stage_sort,
        "stage_is_current": stage_is_current,
        "sibling_stages": sibling_stages,
        "sibling_stage_folders": sibling_stage_folders,
        "raw_details": details,
    }

    return result


_RP_DEVELOPER_LISTING_URL = "https://rynekpierwotny.pl/deweloperzy/?page={page}"
_RP_DEVELOPER_API_URL = "https://rynekpierwotny.pl/api/v2/vendors/vendor/?s=vendor-list&page={page}&page_size=30"


def discover_rp_developers(
    fetcher: Fetcher,
    page: int = 1,
    base_url: Optional[str] = None,
) -> DeveloperPage:
    """Pobiera jedną stronę listy deweloperów z RynekPierwotny."""
    api_url = _RP_DEVELOPER_API_URL.format(page=page)
    data = fetcher.fetch_json(api_url)
    if data and "results" in data:
        count = data.get("count", 0)
        total_pages = max(1, math.ceil(count / 30))
        developers = [
            {
                "url": f"https://rynekpierwotny.pl/deweloperzy/{item['slug']}/",
                "name": item.get("name"),
                "slug": item["slug"],
            }
            for item in data["results"]
            if item.get("slug")
        ]
        return DeveloperPage(developers=developers, total_pages=total_pages, page=page)

    # Fallback: HTML __NEXT_DATA__
    html_url = (base_url or _RP_DEVELOPER_LISTING_URL).format(page=page)
    if base_url and "page=" not in base_url:
        connector = "&" if "?" in base_url else "?"
        html_url = f"{base_url}{connector}page={page}"
    logger.info(f"RP API unavailable, falling back to HTML: {html_url}")
    html = fetcher.fetch(html_url)
    if not html:
        logger.error(f"Failed to fetch RP developer listing: {html_url}")
        return DeveloperPage(developers=[], total_pages=1, page=page)

    # Extract __NEXT_DATA__
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)
    if not m:
        logger.error("RP developer listing: __NEXT_DATA__ not found in HTML")
        return DeveloperPage(developers=[], total_pages=1, page=page)
    try:
        next_data = json.loads(m.group(1))
        props = next_data.get("props", {}).get("pageProps", {})
        vendors_data = props.get("vendors") or props.get("data", {}).get("vendors", {})
        if not vendors_data:
            logger.warning(f"RP developer listing: no vendors key in pageProps. Keys: {list(props.keys())}")
            return DeveloperPage(developers=[], total_pages=1, page=page)
        items = vendors_data.get("items", vendors_data.get("results", []))
        pagination = vendors_data.get("pagination", {})
        total_pages = pagination.get("totalPages", 1)
        developers = [
            {
                "url": f"https://rynekpierwotny.pl/deweloperzy/{item['slug']}/",
                "name": item.get("name"),
                "slug": item["slug"],
            }
            for item in items
            if item.get("slug")
        ]
        return DeveloperPage(developers=developers, total_pages=total_pages, page=page)
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"RP developer listing: failed to parse __NEXT_DATA__: {e}")
        return DeveloperPage(developers=[], total_pages=1, page=page)
