import logging
from pathlib import Path
from .models import ScraperConfig
from .fetcher import Fetcher
from .utils.io import get_investment_dir, get_image_dir, save_raw_json
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

    def get_investment_path(self, dev_slug: str, inv_slug: str) -> Path:
        """Centralized path for usi_*.json and raw_*.json"""
        return get_investment_dir(dev_slug, inv_slug, self.config.public_dir)

    def get_image_path(self, dev_slug: str, inv_slug: str) -> Path:
        """Centralized path for USI images"""
        return get_image_dir(dev_slug, inv_slug, self.config.public_dir)

    def save_raw_data(self, data: dict, dev_slug: str, inv_slug: str, portal_prefix: str) -> Path:
        """Saves raw JSON for an investment"""
        return save_raw_json(data, self.config.public_dir, dev_slug, inv_slug, portal_prefix)

    def sync_images(self, urls: list[str], dev_slug: str, inv_slug: str) -> list[str]:
        """Downloads and saves images, returns list of filenames"""
        return save_images(urls, dev_slug, inv_slug, self.config)

    def get_usi_json_path(self, dev_slug: str, inv_slug: str) -> Path:
        """Returns the full path to the final usi_{slug}.json file"""
        dir_path = self.get_investment_path(dev_slug, inv_slug)
        return dir_path / f"usi_{inv_slug}.json"
