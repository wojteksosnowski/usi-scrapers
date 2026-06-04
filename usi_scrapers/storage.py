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
    """
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.public_dir = Path(config.public_dir)
        self._dev_cache: Dict[str, Dict[str, str]] = {}  # {portal_prefix: {portal_id: dev_slug}}
        self._inv_cache: Dict[str, Dict[str, Tuple[str, str]]] = {}  # {portal_prefix: {portal_id: (dev_slug, inv_slug)}}
        self._initialized = False
        self._lock = Lock()

    def build_index(self):
        """Scans the USIdata and USIdev directories to build the in-memory cache."""
        with self._lock:
            if self._initialized:
                return

            self._dev_cache.clear()
            self._inv_cache.clear()

            dev_raw_root = self.public_dir / "USIdev"
            if dev_raw_root.exists() and dev_raw_root.is_dir():
                for dev_dir in dev_raw_root.iterdir():
                    if not dev_dir.is_dir():
                        continue
                    dev_slug = dev_dir.name
                    for file_path in dev_dir.glob("raw_*_*.json"):
                        # expected format: raw_{portal_prefix}_{portal_id}.json
                        # Note: we might have _timestamp.json archived files, so we check parts
                        parts = file_path.stem.split("_")
                        if len(parts) >= 3 and parts[0] == "raw":
                            portal_prefix = parts[1]
                            # Combine remaining parts in case portal_id has underscores, but ignore timestamp suffix if present
                            # Better approach: check if it matches exactly raw_{prefix}_{id}.json without timestamp
                            # timestamp is 15 chars e.g. 20260604_135717 -> so length of parts would be 4 and last is 6 chars.
                            # We just avoid files with more than 3 parts if they look like timestamp.
                            if len(parts) > 3 and parts[-1].isdigit() and len(parts[-1]) == 6 and len(parts[-2]) == 8 and parts[-2].isdigit():
                                continue # It's an archive file
                                
                            portal_id = "_".join(parts[2:])
                            if portal_prefix not in self._dev_cache:
                                self._dev_cache[portal_prefix] = {}
                            self._dev_cache[portal_prefix][portal_id] = dev_slug

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
                                    continue # It's an archive file
                                    
                                portal_id = "_".join(parts[2:])
                                if portal_prefix not in self._inv_cache:
                                    self._inv_cache[portal_prefix] = {}
                                self._inv_cache[portal_prefix][portal_id] = (dev_slug, inv_slug)

            self._initialized = True
            logger.debug(f"StorageResolver index built. Dev records: {sum(len(v) for v in self._dev_cache.values())}, Inv records: {sum(len(v) for v in self._inv_cache.values())}")

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

    def force_rebuild(self):
        with self._lock:
            self._initialized = False
        self.build_index()

_default_resolver: Optional[StorageResolver] = None

def get_resolver(config: ScraperConfig) -> StorageResolver:
    global _default_resolver
    if _default_resolver is None or _default_resolver.config.public_dir != config.public_dir:
        _default_resolver = StorageResolver(config)
    return _default_resolver
