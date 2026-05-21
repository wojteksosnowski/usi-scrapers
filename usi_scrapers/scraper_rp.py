import logging
import json
import math
import re
from pathlib import Path
from typing import Optional
from .fetcher import Fetcher
from .models import ScraperConfig, DeveloperPage
from .utils.io import save_raw_json, save_dev_raw_json, lookup_developer_by_id, lookup_investment_by_id
from .utils.stage_detector import extract_groups_id, extract_stages
from .utils.portals import portal_api_url, portal_url, get_portal
from .utils.mapping import get_mapping, resolve_path
from .utils.scrapers import generic_discover_investments, generic_download_dev_json, extract_logo_from_dict

from . import get_logger

logger = get_logger(__name__)

def download_raw_rp_dev_json(vendor_id_or_slug: str, dev_slug: Optional[str], fetcher: Fetcher, config: ScraperConfig) -> Optional[str]:
    """
    Downloads raw JSON for an RP developer profile and saves it.
    Also downloads developer logo when found in the API response.
    Returns the resolved developer slug.
    """
    def extract_id(profile):
        rp_dev_mapping = get_mapping("rp", "developer")
        raw_id = resolve_path(profile, rp_dev_mapping.get("id"))
        portal_id = str(raw_id) if raw_id else None
        if not portal_id:
            if str(vendor_id_or_slug).isdigit():
                portal_id = vendor_id_or_slug
            else:
                portal_id = resolve_rp_vendor_id(vendor_id_or_slug, fetcher)
        return portal_id

    dev_url = portal_url("rp", "developer", slug=vendor_id_or_slug) if not str(vendor_id_or_slug).isdigit() else None
    
    return generic_download_dev_json(
        fetcher, config, vendor_id_or_slug, dev_slug, "rp",
        fetch_func=fetch_rp_developer_profile,
        extract_id_func=extract_id,
        extract_logo_func=extract_rp_dev_logo,
        source_url=dev_url
    )


def extract_rp_dev_logo(profile: dict) -> str | None:
    """Extracts logo URL from RP vendor API response."""
    candidates = ["logo", "logo_url", "image", "logo.url", "logo.src", "image.url", "image.src"]
    return extract_logo_from_dict(profile, candidates)

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

    url = portal_api_url("rp", "vendor_detail", vendor_id=vendor_id)
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

    # Resolve Investment Slug (ID-based lookup)
    existing_inv_slug = lookup_investment_by_id(config.public_dir, dev_slug, "rp", offer_id)
    if existing_inv_slug:
        inv_slug = existing_inv_slug
        logger.info(f"Matched investment ID {offer_id} to existing investment slug: {inv_slug}")

    return save_raw_json(details, config.public_dir, dev_slug, inv_slug, "rp", portal_id=offer_id)

def fetch_rp_details(offer_id: str, fetcher: Fetcher) -> dict:
    """
    Fetches investment details from RynekPierwotny.pl API v2.
    """
    url = portal_api_url("rp", "offer_detail", offer_id=offer_id)
    logger.info(f"Fetching RynekPierwotny details for ID: {offer_id} from {url}")
    return fetcher.fetch_json(url, use_scraperapi=False) or {}

def fetch_rp_gallery(offer_id: str, fetcher: Fetcher) -> list[str]:
    """
    Fetches image URLs from RynekPierwotny.pl gallery API.
    """
    url = portal_api_url("rp", "offer_gallery", offer_id=offer_id)
    logger.info(f"Fetching RynekPierwotny gallery for ID: {offer_id} from {url}")
    
    data = fetcher.fetch_json(url, use_scraperapi=False) or {}
    # Extract images from gallery
    images = []
    rp_mapping = get_mapping("rp", "investment")
    gallery = resolve_path(data, rp_mapping.get("gallery")) or []
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
    url = portal_url("rp", "developer", slug=slug)
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
    if identifier:
        vendor_id = identifier
        if not str(identifier).isdigit():
            vendor_id = resolve_rp_vendor_id(identifier, fetcher)
            if not vendor_id:
                logger.error(f"Could not resolve vendor ID for slug: {identifier}")
                return []
        
        url = portal_api_url("rp", "vendor_offer_list", vendor_id=vendor_id, page="1")
        return discover_rp_listing(config, fetcher, url, limit)
    else:
        # Global discovery
        urls = []
        if hasattr(config, "rp_discovery_urls") and config.rp_discovery_urls:
            urls = config.rp_discovery_urls
        else:
            urls = [portal_api_url("rp", "offer_list", page="1")]
            
        return generic_discover_investments(config, fetcher, urls, discover_rp_listing, limit)

def discover_rp_listing(config: ScraperConfig, fetcher: Fetcher, identifier: str = None, limit: int = None) -> list[dict]:
    """
    Discovers investments from a general RP API listing URL or vendor ID.
    """
    if not identifier:
        return []
        
    PAGE_SIZE = 30
    all_results = []
    seen_ids = set()
    
    url_template = identifier
    if "page=" not in url_template:
        connector = "&" if "?" in url_template else "?"
        url_template += f"{connector}page=1"
    
    page = 1
    while True:
        url = url_template.replace("page=1", f"page={page}").replace("page_size=100", f"page_size={PAGE_SIZE}")
        if "page_size=" not in url:
            url += f"&page_size={PAGE_SIZE}"
            
        logger.info(f"Discovering RP investments via query (page {page}): {url}")
        data = fetcher.fetch_json(url, use_scraperapi=False) or {}
        results = data.get("results", [])
        if not results:
            break
            
        batch = _parse_rp_results(results)
        for item in batch:
            if item["id"] not in seen_ids:
                all_results.append(item)
                seen_ids.add(item["id"])
                if limit and len(all_results) >= limit:
                    return all_results
                    
        if len(results) < PAGE_SIZE:
            break
        page += 1
        
    return all_results

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
                        "url": portal_url("rp", "stage", dev_slug=s_vendor_slug, inv_slug=s_slug, offer_id=s_id, stage_id=str(s_id_internal)),
                    })
        else:
            v_data = get_val(item, "vendor") or {}
            v_slug = v_data.get("slug") or v_slug_parent
            o_id = str(item.get("id"))
            o_slug = item.get("slug")
            
            offers.append({
                "id": o_id,
                "url": portal_url("rp", "investment", dev_slug=v_slug, inv_slug=o_slug, offer_id=o_id),
            })
            
    return offers

def scrape_rynek_pierwotny(offer_id: str, fetcher: Fetcher, url: str = None) -> dict:
    """
    Main function to scrape RynekPierwotny investment.
    """
    details = fetch_rp_details(offer_id, fetcher)
    if not details:
        return {"error": "Could not fetch details"}
        
    gallery_data = fetcher.fetch_json(portal_api_url("rp", "offer_gallery", offer_id=offer_id), use_scraperapi=False)
    if gallery_data:
        details["_raw_gallery"] = gallery_data

    gallery_urls = []
    if gallery_data:
        gallery = gallery_data.get("gallery", [])
        for item in gallery:
            img_url = item.get("image", {}).get("g_img_1500")
            if img_url:
                gallery_urls.append(img_url)
    
    rp_mapping = get_mapping("rp", "investment")
    
    main_image = resolve_path(details, rp_mapping.get("main_image"))
    if main_image:
        main_img_500 = main_image.get("m_img_500") if isinstance(main_image, dict) else None
        if main_img_500:
            gallery_urls.insert(0, main_img_500)
        
    def get_val(data, key, default=None):
        if not data or key not in data:
            return default
        val = data[key]
        if isinstance(val, dict) and "value" in val:
            return val["value"]
        return val

    vendor_id = resolve_path(details, rp_mapping.get("developer_id"))
    
    if not vendor_id:
        return {"error": f"Failed to resolve vendor ID from API for offer {offer_id}"}

    developer_slug = None

    # 1. ID-based lookup (highest priority)
    existing_slug = lookup_developer_by_id(fetcher.config.public_dir, "rp", vendor_id)
    if existing_slug:
        developer_slug = existing_slug
        logger.info(f"Matched vendor ID {vendor_id} to existing developer slug: {developer_slug}")

    # Resolve (if needed) and Update developer data using the internal API
    # If developer_slug is None, it will be resolved from the profile data
    developer_slug = download_raw_rp_dev_json(str(vendor_id), developer_slug, fetcher, fetcher.config)
    if developer_slug:
        logger.info(f"Resolved/Updated developer '{developer_slug}' data from RynekPierwotny.")

    if not developer_slug:
        return {"error": f"Failed to resolve developer_slug from API data for vendor ID {vendor_id}"}

    investment_slug = resolve_path(details, rp_mapping.get("slug"))
    if not investment_slug:
        return {"error": f"Failed to resolve investment_slug from API for offer {offer_id}"}

    # ID-based Investment Identification
    existing_inv_slug = lookup_investment_by_id(fetcher.config.public_dir, developer_slug, "rp", offer_id)
    if existing_inv_slug:
        investment_slug = existing_inv_slug
        logger.info(f"Matched investment ID {offer_id} to existing investment slug: {investment_slug}")

    if not url:
        url = portal_url("rp", "investment", dev_slug=developer_slug, inv_slug=investment_slug, offer_id=offer_id)
        
    details["url"] = url
    coords = resolve_path(details, rp_mapping.get("geo_point_coordinates"))
    
    const_upper = resolve_path(details, rp_mapping.get("construction_date_upper"))

    stages = extract_stages(details)
    groups_id = resolve_path(details, rp_mapping.get("groups_id"))
    groups_name = resolve_path(details, rp_mapping.get("groups_name"))

    stage_sort = None
    stage_is_current = None
    for s in stages:
        if str(s.get("offer_id")) == str(offer_id):
            stage_sort = s.get("sort")
            stage_is_current = s.get("current")
            break

    sibling_stages = stages
    sibling_stage_folders = [
        f"{developer_slug}/{s['slug']}"
        for s in stages
        if str(s["offer_id"]) != str(offer_id) and s["slug"]
    ]

    rp_mapping = get_mapping("rp", "investment")

    result = {
        "source": "rynekpierwotny.pl",
        "id": offer_id,
        "url": url,
        "developer_slug": developer_slug,
        "investment_slug": investment_slug,
        "name": resolve_path(details, rp_mapping.get("name")),
        "developer_name": resolve_path(details, rp_mapping.get("developer_name")),
        "address": resolve_path(details, rp_mapping.get("address")),
        "geo_point": coords,
        "latitude": coords[1] if coords and len(coords) > 1 else None,
        "longitude": coords[0] if coords and len(coords) > 0 else None,
        "construction_date_upper": const_upper,
        "website": resolve_path(details, rp_mapping.get("website")),
        "properties_count": resolve_path(details, rp_mapping.get("units_count")),
        "price_min": resolve_path(details, rp_mapping.get("price_min")),
        "price_max": resolve_path(details, rp_mapping.get("price_max")),
        "ceiling_height_min": resolve_path(details, rp_mapping.get("ceiling_height_min")),
        "ceiling_height_max": resolve_path(details, rp_mapping.get("ceiling_height_max")),
        "image_urls": gallery_urls,
        "groups_id": groups_id,
        "groups_name": groups_name,
        "stage_sort": stage_sort,
        "stage_is_current": stage_is_current,
        "sibling_stages": sibling_stages,
        "sibling_stage_folders": sibling_stage_folders,
        "raw_details": details,
    }

    return result


def discover_rp_developers(
    fetcher: Fetcher,
    page: int = 1,
    base_url: Optional[str] = None,
) -> DeveloperPage:
    """Pobiera jedną stronę listy deweloperów z RynekPierwotny."""
    api_url = portal_api_url("rp", "vendor_list", page=str(page))
    data = fetcher.fetch_json(api_url)
    if data and "results" in data:
        count = data.get("count", 0)
        total_pages = max(1, math.ceil(count / 30))
        developers = [
            {
                "url": portal_url("rp", "developer", slug=item["slug"]),
                "name": item.get("name"),
                "slug": item["slug"],
            }
            for item in data["results"]
            if item.get("slug")
        ]
        return DeveloperPage(developers=developers, total_pages=total_pages, page=page)

    # Fallback: HTML __NEXT_DATA__
    html_url = (base_url or get_portal("rp")["developer_list_url"]).format(page=page)
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
                "url": portal_url("rp", "developer", slug=item["slug"]),
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
