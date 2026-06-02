import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from .. import get_logger
from .portals import portal_base_url

logger = get_logger(__name__)


def save_raw_json(
    data: dict,
    public_dir: Path,
    dev_slug: str,
    inv_slug: str,
    portal_prefix: str,
    portal_id: str,
) -> Path:
    """
    Saves raw JSON data using centralized path resolution.
    portal_id is required — ID-only naming enforced (no slug fallback).
    PURE-RAW: Saves the exact data provided, no meta injection.
    """
    if not portal_id:
        raise ValueError(
            f"save_raw_json: portal_id is required for {portal_prefix}/{dev_slug}/{inv_slug}. "
            "Slug-based fallback is not allowed (ID-only policy)."
        )

    inv_dir = get_investment_dir(dev_slug, inv_slug, public_dir)
    inv_dir.mkdir(parents=True, exist_ok=True)

    filename = f"raw_{portal_prefix}_{portal_id}.json"
    file_path = inv_dir / filename

    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_filename = f"raw_{portal_prefix}_{portal_id}_{ts}.json"
        archived_path = inv_dir / archived_filename
        file_path.rename(archived_path)
        logger.info(f"Archived existing raw file: {archived_filename}")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved raw JSON: {file_path}")
    return file_path


def save_raw_html(
    html: str,
    public_dir: Path,
    dev_slug: str,
    inv_slug: str,
    portal_prefix: str,
    portal_id: str | None = None,
) -> Path:
    """
    Saves raw HTML for an investment.
    Filename: raw_{portal}_{slug|id}.html
    """
    inv_dir = get_investment_dir(dev_slug, inv_slug, public_dir)
    inv_dir.mkdir(parents=True, exist_ok=True)

    filename = f"raw_{portal_prefix}_{portal_id or inv_slug}.html"
    file_path = inv_dir / filename

    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_filename = f"raw_{portal_prefix}_{portal_id or inv_slug}_{ts}.html"
        archived_path = inv_dir / archived_filename
        file_path.rename(archived_path)
        logger.info(f"Archived existing raw HTML file: {archived_filename}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"Saved raw HTML: {file_path}")
    return file_path


def save_dev_raw_json(
    data: dict,
    public_dir: Path,
    dev_slug: str,
    portal_prefix: str,
    portal_id: str,
    source_url: str | None = None,
) -> Path:
    """
    Saves raw developer profile JSON using centralized path resolution.
    portal_id is required — ID-only naming enforced (no slug fallback).
    Filename: raw_{portal}_{portal_id}.json
    PURE-RAW: Saves the exact data provided, no meta injection.
    """
    if not portal_id:
        raise ValueError(
            f"save_dev_raw_json: portal_id is required for {portal_prefix}/{dev_slug}. "
            "Slug-based fallback is not allowed (ID-only policy)."
        )

    dev_raw_dir = Path(public_dir) / "USIdev" / dev_slug
    dev_raw_dir.mkdir(parents=True, exist_ok=True)

    filename = f"raw_{portal_prefix}_{portal_id}.json"
    file_path = dev_raw_dir / filename

    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_filename = f"raw_{portal_prefix}_{portal_id}_{ts}.json"
        archived_path = dev_raw_dir / archived_filename
        file_path.rename(archived_path)
        logger.info(f"Archived existing raw developer file: {archived_filename}")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved raw developer JSON: {file_path}")
    return file_path


def lookup_developer_by_id(public_dir: Path, portal_prefix: str, portal_id: str | int) -> str | None:
    """
    Scans USIdev directory to find a developer_slug that matches the given portal_id.
    PURE-RAW: Matches against filename pattern raw_{portal}_{id}.json ONLY.
    """
    dev_raw_root = Path(public_dir) / "USIdev"
    if not dev_raw_root.exists():
        return None

    str_portal_id = str(portal_id)
    
    # Iterate over developer slug directories
    for dev_dir in dev_raw_root.iterdir():
        if not dev_dir.is_dir():
            continue
        
        # Fast check: filename match raw_{portal}_{portal_id}.json
        fast_file = dev_dir / f"raw_{portal_prefix}_{str_portal_id}.json"
        if fast_file.exists():
            return dev_dir.name
                
    return None


def lookup_investment_by_id(public_dir: Path, dev_slug: str, portal_prefix: str, portal_id: str | int) -> str | None:
    """
    Scans USIdata/{dev_slug} directory to find an investment_slug that matches the given portal_id.
    PURE-RAW: Matches against filename pattern raw_{portal}_{id}.json ONLY.
    """
    dev_data_root = Path(public_dir) / "USIdata" / dev_slug
    if not dev_data_root.exists():
        return None

    str_portal_id = str(portal_id)

    # Iterate over investment slug directories
    for inv_dir in dev_data_root.iterdir():
        if not inv_dir.is_dir():
            continue

        # Fast check: filename match raw_{portal}_{portal_id}.json
        fast_file = inv_dir / f"raw_{portal_prefix}_{str_portal_id}.json"
        if fast_file.exists():
            return inv_dir.name

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
