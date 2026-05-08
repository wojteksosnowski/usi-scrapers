import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

def save_raw_json(data: dict, public_dir: Path, dev_slug: str, inv_slug: str, portal_prefix: str) -> Path:
    """
    Saves raw JSON data using centralized path resolution.
    """
    inv_dir = get_investment_dir(dev_slug, inv_slug, public_dir)
    inv_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"raw_{portal_prefix}_{inv_slug}.json"
    file_path = inv_dir / filename
    
    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_filename = f"raw_{portal_prefix}_{inv_slug}_{ts}.json"
        archived_path = inv_dir / archived_filename
        file_path.rename(archived_path)
        logger.info(f"Archived existing raw file: {archived_filename}")
        
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved raw JSON: {file_path}")
    return file_path


def save_dev_raw_json(data: dict, public_dir: Path, dev_slug: str, portal_prefix: str) -> Path:
    """
    Saves raw developer profile JSON using centralized path resolution.
    """
    dev_raw_dir = Path(public_dir) / "USIdev" / "raw"
    dev_raw_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"raw_{portal_prefix}_{dev_slug}.json"
    file_path = dev_raw_dir / filename
    
    if file_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_filename = f"raw_{portal_prefix}_{dev_slug}_{ts}.json"
        archived_path = dev_raw_dir / archived_filename
        file_path.rename(archived_path)
        logger.info(f"Archived existing raw developer file: {archived_filename}")
        
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved raw developer JSON: {file_path}")
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
