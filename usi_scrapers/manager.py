import json
import logging
from pathlib import Path
from typing import Optional, List
from .models import ScraperConfig
from .fetcher import Fetcher
from .utils.io import get_investment_dir, get_image_dir, save_raw_json
# Upewniamy się, że clean_filename jest dostępny do transformacji adresów na nazwy lokalne
from .utils.images import save_images, clean_filename, IMAGE_EXTENSIONS
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

    @staticmethod
    def collect_disk_image_filenames(img_dir: Path) -> List[str]:
        """
        Zwraca posortowaną listę nazw plików obrazów już zapisanych na dysku
        w katalogu inwestycji (USI/{dev_slug}/{inv_slug}/). Uwzględnia tylko
        pliki o znanych rozszerzeniach graficznych o rozmiarze > 1 KB.
        """
        if not img_dir.exists():
            return []
        return sorted(
            f.name
            for f in img_dir.iterdir()
            if f.is_file()
            and f.suffix.lower() in IMAGE_EXTENSIONS
            and f.stat().st_size > 1024
        )

    @staticmethod
    def collect_archived_image_urls(
        inv_dir: Path, portal_prefix: str, portal_id: str
    ) -> List[str]:
        """
        Skanuje zarchiwizowane kopie pliku raw_{portal}_{id}_*.json w katalogu
        inwestycji i zbiera wszystkie wcześniej zapisane adresy URL obrazów.
        Obsługuje różne klucze natywne dla każdego portalu:
          - OTO: ad.images[].large / ad.images[].medium
          - RP:  _raw_gallery.gallery (przetwarzane przez rp_gallery_to_flat_list)
          - TO:  _raw_gallery_urls
        Zwraca deduplikowaną listę URL-ów.
        """
        pattern = f"raw_{portal_prefix}_{portal_id}_*.json"
        archived_files = sorted(inv_dir.glob(pattern))
        urls: list[str] = []

        for arc_file in archived_files:
            try:
                with open(arc_file, "r", encoding="utf-8") as f:
                    arc_data = json.load(f)
            except Exception as exc:
                logger.warning(f"collect_archived_image_urls: cannot read {arc_file.name}: {exc}")
                continue

            if portal_prefix == "oto":
                # OTO: images are under ad.images[]
                ad = arc_data.get("ad", {})
                for img in ad.get("images", []) if isinstance(ad, dict) else []:
                    if isinstance(img, dict):
                        url = img.get("large") or img.get("medium") or img.get("small")
                        if url:
                            urls.append(url)
            elif portal_prefix == "rp":
                # RP: gallery is in _raw_gallery.gallery
                try:
                    from .transformers import apply_transformer
                    gallery_urls = apply_transformer("rp_gallery_to_flat_list", arc_data)
                    if isinstance(gallery_urls, list):
                        urls.extend(gallery_urls)
                except Exception as exc:
                    logger.warning(f"collect_archived_image_urls RP: {exc}")
            elif portal_prefix == "to":
                # TO: _raw_gallery_urls is a flat list
                raw_urls = arc_data.get("_raw_gallery_urls", [])
                if isinstance(raw_urls, list):
                    urls.extend(u for u in raw_urls if isinstance(u, str))

        # Deduplicate while preserving order of first appearance
        seen: set[str] = set()
        deduped: list[str] = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return deduped

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

        # --- POPRAWKA WYCIEKU + AGREGACJA HISTORYCZNYCH OBRAZÓW ---
        # Jeżeli w przekazanych danych przetrzymywane są wyekstrahowane adresy URL galeryjnych obrazów,
        # należy je przechwycić, pobrać i nadpisać lokalnymi ścieżkami relatywnymi/nazwami plików.
        # Oprócz bieżącego scrapowania zbieramy URL-e z poprzednich zarchiwizowanych kopii raw JSON
        # oraz wszystkie pliki obrazów już istniejące na dysku dla tej inwestycji.
        if "image_urls" in data and isinstance(data["image_urls"], list):
            public_dir_path = Path(self.config.public_dir)
            inv_dir = get_investment_dir(dev_slug, inv_slug, public_dir_path)
            img_dir = get_image_dir(dev_slug, inv_slug, public_dir_path)

            # 1. Zbieramy URL-e z poprzednich zarchiwizowanych kopii raw JSON
            archived_urls: List[str] = []
            if portal_id:
                archived_urls = self.collect_archived_image_urls(inv_dir, portal_prefix, portal_id)
            if archived_urls:
                logger.info(
                    f"Found {len(archived_urls)} image URL(s) from archived raw files for {inv_slug}"
                )

            # 2. Łączymy bieżące URL-e z archiwalnymi, deduplikując kolejność
            current_urls: List[str] = data["image_urls"]
            seen_urls: set[str] = set(current_urls)
            combined_urls: List[str] = list(current_urls)
            for u in archived_urls:
                if u not in seen_urls:
                    seen_urls.add(u)
                    combined_urls.append(u)

            logger.info(f"Localizing {len(combined_urls)} image URL(s) for investment {inv_slug}")
            local_images_from_urls = self.download_and_localize_images(combined_urls, dev_slug, inv_slug)

            # 3. Uzupełniamy o pliki obrazów już istniejące na dysku (np. pobrane podczas poprzednich
            #    sesji, których URL nie pojawia się już w bieżącym scrapowaniu)
            disk_filenames = self.collect_disk_image_filenames(img_dir)
            seen_fnames: set[str] = set(local_images_from_urls)
            for fname in disk_filenames:
                if fname not in seen_fnames:
                    local_images_from_urls.append(fname)
                    seen_fnames.add(fname)

            # Aktualizujemy image_urls o pełną listę URL-ów (bieżące + archiwalne)
            data["image_urls"] = combined_urls

            # Zapisujemy relatywne ścieżki (względem public_dir) do pobranych plików w kluczu `image_paths`
            # Przykład: /Public/USI/developer/investment/file.webp
            if public_dir_path.name == "Public":
                rel_dir = img_dir.relative_to(public_dir_path.parent)
                data["image_paths"] = [f"/{rel_dir}/{fname}" for fname in local_images_from_urls]
            else:
                rel_dir = img_dir.relative_to(public_dir_path)
                data["image_paths"] = [f"/Public/{rel_dir}/{fname}" for fname in local_images_from_urls]

        target_dir = get_investment_dir(dev_slug, inv_slug, self.config.public_dir)
        fetch_vector = data.get("fetch_vector")
        file_path = save_raw_json(raw_details, target_dir, portal_prefix, portal_id=portal_id, fetch_vector=fetch_vector)
        
        if file_path and portal_id:
            self.resolver.update_investment_index(portal_prefix, portal_id, dev_slug, inv_slug)
            
        return file_path
