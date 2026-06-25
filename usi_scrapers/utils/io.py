import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from usi_scrapers.logger import get_logger
from .portals import portal_base_url

logger = get_logger(__name__)


def save_raw_json(
    data: dict,
    target_dir: Path,
    portal_prefix: str,
    portal_id: str,
    fetch_vector: Optional[str] = None,
) -> Path:
    """
    Saves raw JSON data using centralized path resolution.
    portal_id is required — ID-only naming enforced (no slug fallback).
    PURE-RAW: Saves the exact data provided, no meta injection.
    """
    if not portal_id:
        raise ValueError(
            f"save_raw_json: portal_id is required for {portal_prefix}. "
            "Slug-based fallback is not allowed (ID-only policy)."
        )

    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"raw_{portal_prefix}_{portal_id}.json"
    file_path = target_dir / filename

    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_filename = f"raw_{portal_prefix}_{portal_id}_{ts}.json"
        archived_path = target_dir / archived_filename
        file_path.rename(archived_path)
        logger.info(f"Archived existing raw file: {archived_filename}")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved raw JSON: {file_path}")
    
    # Section 3.5: [TIMESTAMP] {dev_slug}/{inv_slug} - {Zdarzenie}
    dev_slug = target_dir.parent.name
    inv_slug = target_dir.name
    msg = f"Saved raw data via {fetch_vector if fetch_vector else 'unknown'}"
    append_processing_log(target_dir.parent.parent.parent, dev_slug, inv_slug, msg)
    
    return file_path


def save_raw_html(
    html: str,
    target_dir: Path,
    portal_prefix: str,
    portal_id: str | None = None,
) -> Path:
    """
    Saves raw HTML for an investment.
    Filename: raw_{portal}_{id}.html
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"raw_{portal_prefix}_{portal_id}.html"
    file_path = target_dir / filename

    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_filename = f"raw_{portal_prefix}_{portal_id}_{ts}.html"
        archived_path = target_dir / archived_filename
        file_path.rename(archived_path)
        logger.info(f"Archived existing raw HTML file: {archived_filename}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"Saved raw HTML: {file_path}")
    return file_path


def save_dev_raw_json(
    data: dict,
    target_dir: Path,
    portal_prefix: str,
    portal_id: str,
    source_url: str | None = None,
    fetch_vector: Optional[str] = None,
) -> Path:
    """
    Saves raw developer profile JSON using centralized path resolution.
    portal_id is required — ID-only naming enforced (no slug fallback).
    Filename: raw_{portal}_{portal_id}.json
    PURE-RAW: Saves the exact data provided, no meta injection.
    """
    if not portal_id:
        raise ValueError(
            f"save_dev_raw_json: portal_id is required for {portal_prefix}. "
            "Slug-based fallback is not allowed (ID-only policy)."
        )

    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"raw_{portal_prefix}_{portal_id}.json"
    file_path = target_dir / filename

    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_filename = f"raw_{portal_prefix}_{portal_id}_{ts}.json"
        archived_path = target_dir / archived_filename
        file_path.rename(archived_path)
        logger.info(f"Archived existing raw developer file: {archived_filename}")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved raw developer JSON: {file_path}")
    
    # Section 4: dev_log_{portal}_{portal_id}.txt (append-only JSONL)
    dev_slug = target_dir.name
    msg = f"Saved raw developer data via {fetch_vector if fetch_vector else 'unknown'}"
    append_dev_log(target_dir.parent.parent, dev_slug, portal_prefix, portal_id, msg)
    
    return file_path


def append_processing_log(public_dir: Path, dev_slug: str, inv_slug: str, message: str):
    """
    Logs an event to processing_log_{inv_slug}.txt.
    Format: [TIMESTAMP] {dev_slug}/{inv_slug} - {message}
    """
    log_dir = Path(public_dir) / "USIdata" / dev_slug / inv_slug
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"processing_log_{inv_slug}.txt"
    
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{ts}] {dev_slug}/{inv_slug} - {message}\n"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry)


def append_dev_log(public_dir: Path, dev_slug: str, portal_prefix: str, portal_id: str, message: str):
    """
    Logs an event to dev_log_{portal}_{id}.txt (append-only JSONL).
    """
    log_dir = Path(public_dir) / "USIdev" / dev_slug
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"dev_log_{portal_prefix}_{portal_id}.txt"
    
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": message,
        "portal": portal_prefix,
        "portal_id": portal_id
    }
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def lookup_developer_by_id(public_dir: Path, portal_prefix: str, portal_id: str | int) -> str | None:
    """
    Scans USIdev directory to find a developer_slug that matches the given portal_id.
    PURE-RAW: Matches against filename pattern raw_{portal}_{id}.json ONLY.
    """
    from ..models import ScraperConfig
    from ..storage import get_resolver
    config = ScraperConfig(public_dir=public_dir)
    resolver = get_resolver(config)
    return resolver.lookup_developer(portal_prefix, str(portal_id))


def lookup_investment_by_id(public_dir: Path, dev_slug: str, portal_prefix: str, portal_id: str | int) -> str | None:
    """
    Scans USIdata/{dev_slug} directory to find an investment_slug that matches the given portal_id.
    PURE-RAW: Matches against filename pattern raw_{portal}_{id}.json ONLY.
    """
    from ..models import ScraperConfig
    from ..storage import get_resolver
    config = ScraperConfig(public_dir=public_dir)
    resolver = get_resolver(config)
    result = resolver.lookup_investment(portal_prefix, str(portal_id))
    if result:
        # returns (dev_slug, inv_slug), but lookup_investment_by_id historically returned just inv_slug or verified it against dev_slug
        # Actually lookup_investment_by_id takes dev_slug as argument, so we just verify it matches
        stored_dev_slug, stored_inv_slug = result
        if stored_dev_slug == dev_slug:
            return stored_inv_slug
    return None


def save_meta_json(data: dict, public_dir: Path, dev_slug: str, inv_slug: str, portal_prefix: str, portal_id: str) -> Path:
    """
    Saves meta JSON (Coda ratings) for an investment.
    portal_id is required — ID-only naming enforced (no slug fallback).
    """
    if not portal_id:
        raise ValueError(
            f"save_meta_json: portal_id is required for {portal_prefix}/{dev_slug}/{inv_slug}. "
            "Slug-based fallback is not allowed (ID-only policy)."
        )
    inv_dir = get_investment_dir(dev_slug, inv_slug, public_dir)
    inv_dir.mkdir(parents=True, exist_ok=True)
    filename = f"meta_{portal_prefix}_{portal_id}.json"
    file_path = inv_dir / filename
    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path.rename(inv_dir / f"meta_{portal_prefix}_{portal_id}_{ts}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved meta JSON: {file_path}")
    return file_path

def get_investment_dir(dev_slug: str, inv_slug: str, public_dir: Path) -> Path:
    """
    Returns the absolute path to the investment directory:
    {public_dir}/USIdata/{dev_slug}/{inv_slug}/
    """
    return Path(public_dir) / "USIdata" / dev_slug / inv_slug

def get_image_dir(dev_slug: str, inv_slug: str, public_dir: Path) -> Path:
    """
    Returns the absolute path to the image directory:
    {public_dir}/USI/{dev_slug}/{inv_slug}/
    """
    return Path(public_dir) / "USI" / dev_slug / inv_slug
