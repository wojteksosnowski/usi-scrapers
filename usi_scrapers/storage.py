import json
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
from threading import Lock

from .models import ScraperConfig

logger = logging.getLogger(__name__)

class StorageResolver:
    """
    In-memory index and path resolver for USIdata and USIdev.
    Caches the mapping from portal_id to dev_slug and inv_slug.

    OTO dual-ID support
    -------------------
    Otodom pliki są zapisywane pod alfanumerycznym ID z URL (np. "4mLbK"),
    ale usi-tracker może pytać także po numerycznym ad.id (np. "65110911").
    Podczas build_index dla każdego pliku raw_oto_*.json odczytywany jest
    ad.id (inwestycja) lub agency.id (deweloper) z zawartości pliku
    i rejestrowany jako alias wskazujący na ten sam (dev_slug, inv_slug).
    Dzięki temu lookup_investment/lookup_developer akceptuje oba formaty.
    """
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.public_dir = Path(config.public_dir)
        self._dev_cache: Dict[str, Dict[str, str]] = {}  # {portal_prefix: {portal_id: dev_slug}}
        self._inv_cache: Dict[str, Dict[str, Tuple[str, str]]] = {}  # {portal_prefix: {portal_id: (dev_slug, inv_slug)}}
        # OTO: mapowanie numeric_id -> canonical_alphanum_id (do resolucji nazwy pliku)
        self._oto_inv_canonical: Dict[str, str] = {}   # numeric_id -> alphanum_id
        self._oto_dev_canonical: Dict[str, str] = {}   # numeric_id -> alphanum_id
        self._initialized = False
        self._lock = Lock()

    def build_index(self):
        """Scans the USIdata and USIdev directories to build the in-memory cache."""
        with self._lock:
            if self._initialized:
                return

            self._dev_cache.clear()
            self._inv_cache.clear()
            self._oto_inv_canonical.clear()
            self._oto_dev_canonical.clear()

            dev_raw_root = self.public_dir / "USIdev"
            if dev_raw_root.exists() and dev_raw_root.is_dir():
                for dev_dir in dev_raw_root.iterdir():
                    if not dev_dir.is_dir():
                        continue
                    dev_slug = dev_dir.name
                    for file_path in dev_dir.glob("raw_*_*.json"):
                        parts = file_path.stem.split("_")
                        if len(parts) >= 3 and parts[0] == "raw":
                            portal_prefix = parts[1]
                            if len(parts) > 3 and parts[-1].isdigit() and len(parts[-1]) == 6 and len(parts[-2]) == 8 and parts[-2].isdigit():
                                continue  # archiwum
                            portal_id = "_".join(parts[2:])
                            if portal_prefix not in self._dev_cache:
                                self._dev_cache[portal_prefix] = {}
                            self._dev_cache[portal_prefix][portal_id] = dev_slug

                            # OTO: dodaj alias po numerycznym agency.id
                            if portal_prefix == "oto":
                                numeric_id = self._read_oto_dev_numeric_id(file_path)
                                if numeric_id and numeric_id != portal_id:
                                    self._dev_cache["oto"][numeric_id] = dev_slug
                                    self._oto_dev_canonical[numeric_id] = portal_id

            data_raw_root = self.public_dir / "USIdata"
            if data_raw_root.exists() and data_raw_root.is_dir():
                for dev_dir in data_raw_root.iterdir():
                    if not dev_dir.is_dir():
                        continue
                    dev_slug = dev_dir.name
                    for inv_dir in dev_dir.iterdir():
                        if not inv_dir.is_dir():
                            continue
                        inv_slug = inv_dir.name
                        for file_path in inv_dir.glob("raw_*_*.json"):
                            parts = file_path.stem.split("_")
                            if len(parts) >= 3 and parts[0] == "raw":
                                portal_prefix = parts[1]
                                if len(parts) > 3 and parts[-1].isdigit() and len(parts[-1]) == 6 and len(parts[-2]) == 8 and parts[-2].isdigit():
                                    continue  # archiwum
                                portal_id = "_".join(parts[2:])
                                if portal_prefix not in self._inv_cache:
                                    self._inv_cache[portal_prefix] = {}
                                self._inv_cache[portal_prefix][portal_id] = (dev_slug, inv_slug)

                                # OTO: dodaj alias po numerycznym ad.id
                                if portal_prefix == "oto":
                                    numeric_id = self._read_oto_inv_numeric_id(file_path)
                                    if numeric_id and numeric_id != portal_id:
                                        self._inv_cache["oto"][numeric_id] = (dev_slug, inv_slug)
                                        self._oto_inv_canonical[numeric_id] = portal_id

            self._initialized = True
            logger.debug(
                f"StorageResolver index built. "
                f"Dev records: {sum(len(v) for v in self._dev_cache.values())}, "
                f"Inv records: {sum(len(v) for v in self._inv_cache.values())}"
            )

    @staticmethod
    def _read_oto_inv_numeric_id(file_path: Path) -> Optional[str]:
        """Odczytuje numeryczne ad.id z pliku raw_oto_*.json. Zwraca string lub None."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ad_id = (data.get("ad") or {}).get("id")
            if ad_id is not None:
                return str(ad_id)
        except Exception:
            pass
        return None

    @staticmethod
    def _read_oto_dev_numeric_id(file_path: Path) -> Optional[str]:
        """Odczytuje numeryczne agency.id z pliku raw_oto_*.json (deweloper). Zwraca string lub None."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Plik dewelopera OTO: id dewelopera jest bezpośrednio w root lub w pageProps.ad.agency
            root_id = data.get("id") or data.get("agency_id")
            if root_id is not None:
                return str(root_id)
            ad_id = ((data.get("ad") or {}).get("agency") or {}).get("id")
            if ad_id is not None:
                return str(ad_id)
        except Exception:
            pass
        return None

    def resolve_oto_inv_canonical_id(self, portal_id: str) -> str:
        """
        Dla OTO: zwraca kanoniczny alfanumeryczny ID (używany w nazwie pliku)
        na podstawie dowolnego przekazanego ID (alfanumerycznego lub numerycznego).
        Jeśli portal_id jest już kanoniczny, zwraca go bez zmian.
        """
        if not self._initialized:
            self.build_index()
        return self._oto_inv_canonical.get(portal_id, portal_id)

    def resolve_oto_dev_canonical_id(self, portal_id: str) -> str:
        """Jak resolve_oto_inv_canonical_id, ale dla deweloperów."""
        if not self._initialized:
            self.build_index()
        return self._oto_dev_canonical.get(portal_id, portal_id)


    def lookup_developer(self, portal_prefix: str, portal_id: str) -> Optional[str]:
        if not self._initialized:
            self.build_index()
        str_portal_id = str(portal_id)
        return self._dev_cache.get(portal_prefix, {}).get(str_portal_id)

    def lookup_investment(self, portal_prefix: str, portal_id: str) -> Optional[Tuple[str, str]]:
        if not self._initialized:
            self.build_index()
        str_portal_id = str(portal_id)
        return self._inv_cache.get(portal_prefix, {}).get(str_portal_id)

    def update_developer_index(self, portal_prefix: str, portal_id: str, dev_slug: str):
        with self._lock:
            if portal_prefix not in self._dev_cache:
                self._dev_cache[portal_prefix] = {}
            self._dev_cache[portal_prefix][str(portal_id)] = dev_slug

    def update_investment_index(self, portal_prefix: str, portal_id: str, dev_slug: str, inv_slug: str):
        with self._lock:
            if portal_prefix not in self._inv_cache:
                self._inv_cache[portal_prefix] = {}
            self._inv_cache[portal_prefix][str(portal_id)] = (dev_slug, inv_slug)

    def register_oto_inv_alias(self, numeric_id: str, canonical_id: str, dev_slug: str, inv_slug: str):
        """Rejestruje numeryczne ad.id Otodom jako alias kanonicznego ID (jak build_index, ale bez skanu)."""
        if numeric_id == canonical_id:
            return
        self.update_investment_index("oto", numeric_id, dev_slug, inv_slug)
        with self._lock:
            self._oto_inv_canonical[numeric_id] = canonical_id

    def force_rebuild(self):
        with self._lock:
            self._initialized = False
        self.build_index()

    def find_image_path(self, filename: str) -> Optional[str]:
        """Wyszukuje plik obrazu w drzewie USI po jego nazwie używając rglob."""
        for path in self.public_dir.rglob(filename):
            if path.is_file():
                return str(path)
        return None

    def get_investment_metadata(self, portal_prefix: str, portal_id: str) -> Optional[Dict[str, str]]:
        """
        Pobiera metadane inwestycji (np. source_url) ładując surowy JSON z dysku.
        Dla OTO obsługuje zarówno alfanumeryczne jak i numeryczne portal_id.
        """
        res = self.lookup_investment(portal_prefix, portal_id)
        if not res:
            return None
        dev_slug, inv_slug = res
        from .utils.io import get_investment_dir
        target_dir = get_investment_dir(dev_slug, inv_slug, self.public_dir)

        # Dla OTO: nazwa pliku używa kanonicznego alfanumerycznego ID, nie numerycznego
        canonical_id = (
            self.resolve_oto_inv_canonical_id(portal_id)
            if portal_prefix == "oto"
            else portal_id
        )
        file_path = target_dir / f"raw_{portal_prefix}_{canonical_id}.json"
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            # Stosujemy adapter normalizacyjny przed odczytem metadanych
            from .utils.integrity import normalize_to_legacy_props
            data = normalize_to_legacy_props(raw_data, portal_prefix)

            source_url = None
            if portal_prefix == "oto":
                source_url = data.get("ad", {}).get("url") or data.get("url")
            elif portal_prefix == "to":
                source_url = data.get("url")

            return {
                "source_url": source_url,
                "dev_slug": dev_slug,
                "inv_slug": inv_slug
            }
        except Exception as e:
            logger.error(f"Failed to read metadata for {portal_prefix} {portal_id}: {e}")
            return None

_default_resolver: Optional[StorageResolver] = None

def get_resolver(config: ScraperConfig) -> StorageResolver:
    global _default_resolver
    if _default_resolver is None or _default_resolver.config.public_dir != config.public_dir:
        _default_resolver = StorageResolver(config)
    return _default_resolver
