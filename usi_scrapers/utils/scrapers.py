import logging
from pathlib import Path
from typing import Any, Callable, List, Optional, TypeVar

from ..models import ScraperConfig
from ..fetcher import Fetcher
from .io import save_dev_raw_json
from .images import download_developer_logo

from .. import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

def generic_discover_investments(
    config: ScraperConfig,
    fetcher: Fetcher,
    discovery_urls: List[str],
    discover_func: Callable[[ScraperConfig, Fetcher, str, Optional[int]], List[dict]],
    limit: Optional[int] = None
) -> List[dict]:
    """
    Generic loop for discovering investments across multiple URLs.
    """
    all_results = []
    seen_ids = set()
    
    for url in discovery_urls:
        remaining_limit = (limit - len(all_results)) if limit else None
        if limit and remaining_limit <= 0:
            break
            
        batch = discover_func(config, fetcher, url, remaining_limit)
        for item in batch:
            item_id = item.get("id")
            if item_id and item_id not in seen_ids:
                all_results.append(item)
                seen_ids.add(item_id)
                if limit and len(all_results) >= limit:
                    return all_results
                    
    return all_results

def generic_download_dev_json(
    fetcher: Fetcher,
    config: ScraperConfig,
    url_or_id: str,
    dev_slug: str,
    portal_prefix: str,
    fetch_func: Callable[[str, Fetcher], Any],
    extract_id_func: Callable[[Any], Optional[str]],
    extract_logo_func: Callable[[Any], Optional[str]],
    source_url: Optional[str] = None
) -> Optional[Path]:
    """
    Generic flow for downloading and saving developer profile data.
    """
    data = fetch_func(url_or_id, fetcher)
    if not data:
        logger.error(f"Failed to fetch {portal_prefix} developer data for {url_or_id}")
        return None

    portal_id = extract_id_func(data)
    if not portal_id:
        logger.error(f"Could not extract {portal_prefix} ID for {dev_slug} from {url_or_id}")
        return None

    logo_url = extract_logo_func(data)
    if logo_url:
        download_developer_logo(logo_url, dev_slug, config, portal_prefix=portal_prefix, portal_id=portal_id)
    else:
        logger.debug(f"No logo URL found for {portal_prefix} developer {dev_slug}")

    return save_dev_raw_json(
        data if isinstance(data, dict) else {"content": data}, 
        config.public_dir, 
        dev_slug, 
        portal_prefix, 
        portal_id=portal_id, 
        source_url=source_url or (url_or_id if url_or_id.startswith("http") else None)
    )

def extract_logo_from_dict(data: dict, candidates: List[str]) -> Optional[str]:
    """
    Helper to extract logo URL from a dictionary based on candidate keys/paths.
    """
    for path in candidates:
        val = data
        for part in path.split("."):
            if isinstance(val, dict):
                val = val.get(part)
            else:
                val = None
                break
        if isinstance(val, str) and val.startswith("http"):
            return val
            
    # Shallow scan for any key containing 'logo'
    for key, val in data.items():
        if "logo" in key.lower() and isinstance(val, str) and val.startswith("http"):
            return val
        if isinstance(val, dict):
            for subkey, subval in val.items():
                if "logo" in subkey.lower() and isinstance(subval, str) and subval.startswith("http"):
                    return subval
    return None
