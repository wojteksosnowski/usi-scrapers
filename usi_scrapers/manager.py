import logging
from pathlib import Path
from typing import Optional, List
from .models import ScraperConfig
from .fetcher import Fetcher
from .utils.io import get_investment_dir, get_image_dir, save_raw_json
# Upewniamy się, że clean_filename jest dostępny do transformacji adresów na nazwy lokalne
from .utils.images import save_images, clean_filename 
from .storage import StorageResolver

from usi_scrapers.logger import get_logger

logger = get_logger(__name__)

class TechnicalDataManager:
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.resolver = StorageResolver(config)

    def get_investment_path(self, portal_prefix: str, portal_id: str) -> Optional[Path]:
        res = self.resolver.lookup_investment(portal_prefix, portal_id)
        if res:
            dev_slug, inv_slug = res
            return get_investment_dir(dev_slug, inv_slug, self.config.public_dir)
        return None

    def get_image_path(self, portal_prefix: str, portal_id: str) -> Optional[Path]:
        res = self.resolver.lookup_investment(portal_prefix, portal_id)
        if res:
            dev_slug, inv_slug = res
            return get_image_dir(dev_slug, inv_slug, self.config.public_dir)
        return None

    def get_raw_filename(self, portal_prefix: str, portal_id: Optional[str] = None) -> str:
        if portal_id:
            return f"raw_{portal_prefix}_{portal_id}.json"
        return f"raw_{portal_prefix}.json"

    def download_and_localize_images(self, urls: List[str], dev_slug: str, inv_slug: str) -> List[str]:
        """
        Pobiera obrazy i zwraca listę LOKALNYCH nazw plików, 
        które powinny trafić do bazy danych zamiast zewnętrznych URL.
        """
        if not urls:
            return []
        
        target_img_dir = get_image_dir(dev_slug, inv_slug, self.config.public_dir)
        # Fizyczne pobranie plików na dysk
        saved_files = save_images(urls, target_img_dir, self.config)
        
        # Zwracamy wyłącznie nazwy plików, które pomyślnie zapisano lub już istniały
        return saved_files

    def save_raw_data(self, data: dict, portal_prefix: str) -> Optional[Path]:
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
            portal_id = to_id if to_id else None
        else:
            portal_id = None
        
        dev_slug = data.get("developer_slug")
        inv_slug = data.get("investment_slug")
        if not dev_slug or not inv_slug or str(dev_slug).lower() == "unknown":
            logger.error(f"save_raw_data: missing dev_slug or inv_slug in data for {portal_prefix}. Aborting.")
            return None

        # --- POPRAWKA WYCIEKU ---
        # Jeżeli w przekazanych danych przetrzymywane są wyekstrahowane adresy URL galeryjnych obrazów,
        # należy je przechwycić, pobrać i nadpisać lokalnymi ścieżkami relatywnymi/nazwami plików.
        if "image_urls" in data and isinstance(data["image_urls"], list):
            logger.info(f"Localizing {len(data['image_urls'])} images for investment {inv_slug}")
            local_images = self.download_and_localize_images(data["image_urls"], dev_slug, inv_slug)
            
            # Zapisujemy bezwzględne ścieżki do pobranych plików w kluczu `image_paths`
            target_dir = get_image_dir(dev_slug, inv_slug, self.config.public_dir)
            data["image_paths"] = [str((target_dir / fname).absolute()) for fname in local_images]
            
            # Klucz `image_urls` pozostawiamy nienaruszony (jako listę oryginalnych adresów URL)

        from .utils.io import save_raw_json, get_investment_dir
        target_dir = get_investment_dir(dev_slug, inv_slug, self.config.public_dir)
        fetch_vector = data.get("fetch_vector")
        file_path = save_raw_json(raw_details, target_dir, portal_prefix, portal_id=portal_id, fetch_vector=fetch_vector)
        
        if file_path and portal_id:
            self.resolver.update_investment_index(portal_prefix, portal_id, dev_slug, inv_slug)
            
        return file_path
