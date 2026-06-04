import logging
from pathlib import Path
from typing import Optional
from .models import ScraperConfig
from .fetcher import Fetcher
from .utils.io import get_investment_dir, get_image_dir, save_raw_json
from .utils.images import save_images
from .storage import StorageResolver

from . import get_logger

logger = get_logger(__name__)

class TechnicalDataManager:
    """
    Handles technical I/O operations: path resolution, image saving, and raw JSON storage.
    Delegates semantic merging and ratings to the tracker.
    """
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.resolver = StorageResolver(config)

    def get_investment_path(self, portal_prefix: str, portal_id: str) -> Optional[Path]:
        """Resolves investment directory path using portal ID (O(1) via index)."""
        res = self.resolver.lookup_investment(portal_prefix, portal_id)
        if res:
            dev_slug, inv_slug = res
            return get_investment_dir(dev_slug, inv_slug, self.config.public_dir)
        return None

    def get_image_path(self, portal_prefix: str, portal_id: str) -> Optional[Path]:
        """Resolves image directory path using portal ID."""
        res = self.resolver.lookup_investment(portal_prefix, portal_id)
        if res:
            dev_slug, inv_slug = res
            return get_image_dir(dev_slug, inv_slug, self.config.public_dir)
        return None

    def get_raw_filename(self, portal_prefix: str, portal_id: Optional[str] = None) -> str:
        """Returns standardized raw JSON filename."""
        if portal_id:
            return f"raw_{portal_prefix}_{portal_id}.json"
        return f"raw_{portal_prefix}.json"

    def save_raw_data(self, data: dict, portal_prefix: str) -> Optional[Path]:
        """Saves virgin raw JSON for an investment"""
        from .utils.integrity import check_evolution
        evolution = check_evolution(data, portal_prefix)
        if evolution.get("status") == "changed":
            logger.warning(f"Schema change detected for {portal_prefix}: %s", evolution)

        raw_details = data.get("raw_details")
        if not raw_details:
            logger.error(f"save_raw_data: missing 'raw_details' for {portal_prefix}. Aborting save.")
            return None

        if portal_prefix == "rp":
            portal_id = str(data.get("id", "")) or None
        elif portal_prefix == "oto":
            portal_id = data.get("oto_url_id")
        elif portal_prefix == "to":
            to_id = data.get("to_id", "")
            portal_id = f"i{to_id}" if to_id else None
        else:
            portal_id = None
        
        dev_slug = data.get("developer_slug")
        inv_slug = data.get("investment_slug")
        if not dev_slug or not inv_slug or str(dev_slug).lower() == "unknown":
            logger.error(f"save_raw_data: missing dev_slug or inv_slug in data for {portal_prefix}. Aborting.")
            return None

        from .utils.io import save_raw_json, get_investment_dir
        target_dir = get_investment_dir(dev_slug, inv_slug, self.config.public_dir)
        file_path = save_raw_json(raw_details, target_dir, portal_prefix, portal_id=portal_id)
        
        # Update the index after saving new raw data
        if file_path and portal_id:
            self.resolver.update_investment_index(portal_prefix, portal_id, dev_slug, inv_slug)
            
        return file_path

    def sync_images(self, urls: list[str], target_image_dir: Path) -> list[str]:
        """Downloads and saves images, returns list of filenames"""
        from .utils.images import save_images
        return save_images(urls, target_image_dir, self.config)
