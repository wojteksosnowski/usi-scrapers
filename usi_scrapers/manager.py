import logging
from pathlib import Path
from typing import Optional
from .models import ScraperConfig
from .fetcher import Fetcher
from .utils.io import save_raw_json
from .utils.images import save_images

from . import get_logger

logger = get_logger(__name__)

class TechnicalDataManager:
    """
    Handles technical I/O operations: path resolution, image saving, and raw JSON storage.
    Delegates semantic merging and ratings to the tracker.
    """
    def __init__(self, config: ScraperConfig):
        self.config = config


    def save_raw_data(self, data: dict, target_dir: Path, portal_prefix: str) -> Optional[Path]:
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
        
        return save_raw_json(raw_details, target_dir, portal_prefix, portal_id=portal_id)

    def sync_images(self, urls: list[str], images_dir: Path) -> list[str]:
        """Downloads and saves images, returns list of filenames"""
        return save_images(urls, images_dir, self.config)

