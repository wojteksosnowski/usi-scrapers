import requests
import shutil
import re
import logging
from pathlib import Path
from urllib.parse import unquote
from ..models import ScraperConfig

from .. import get_logger

logger = get_logger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

def clean_filename(url: str) -> str:
    """
    Ekstrakcja nazwy pliku dokładnie taka, jakiej oczekuje baza danych,
    usuwając jedynie techniczne parametry CDN (query, fragmenty, średniki).
    """
    # 1. Odcinamy parametry korygujące (średniki, pytajniki, hashe)
    base_url = re.split(r'[;?#]', url)[0]
    
    # 2. Wyciągamy ostatni segment ścieżki
    filename = unquote(base_url.split("/")[-1])
    
    # 3. Jeśli to plik Otodom (często Base64 bez rozszerzenia), wymuszamy .webp
    if "otodom.pl" in url or "/files/" in url:
        # Usuwamy ewentualne stare rozszerzenie, aby nie było podwójnych kropek
        name_only = re.sub(r'\.(jpg|jpeg|png|webp)$', '', filename, flags=re.IGNORECASE)
        return f"{name_only}.webp"
        
    return filename

def download_image(url: str, target_dir: Path, force_download: bool) -> tuple[str, bool]:
    """
    Downloads image from URL and saves it to {target_dir}/{filename}.
    Returns a tuple: (filename if successful or empty string otherwise, was_skipped boolean).
    """
    filename = clean_filename(url)
    
    if not filename:
        logger.warning(f"Could not extract filename from URL: {url}")
        return "", False
        
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.debug(f"Permission denied creating/accessing directory {target_dir}, proceeding anyway")
        
    target_path = target_dir / filename
    
    try:
        if not force_download and target_path.exists():
            # Skip if already exists and is not a tiny placeholder
            if target_path.stat().st_size > 1024:
                return filename, True
    except PermissionError:
        logger.debug(f"Permission denied checking existence of {target_path}")
        
    try:
        logger.info(f"Downloading image: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        
        with open(target_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
            
        return filename, False
    except Exception as e:
        logger.error(f"Error downloading image {url}: {e}")
        return "", False

def download_developer_logo(url: str, target_dir: Path, portal_prefix: str = "raw", portal_id: str | None = None) -> str:
    """
    Downloads developer logo and saves to {target_dir}/logo_{portal_prefix}_{portal_id}.{ext}.
    portal_id is required — ID-only naming enforced (no slug fallback).
    Returns filename if successful, empty string otherwise.
    """
    if not portal_id:
        raise ValueError(
            f"download_developer_logo: portal_id is required for {portal_prefix}. "
            "Slug-based fallback is not allowed (ID-only policy)."
        )

    base = url.split("?")[0].split("#")[0]
    suffix = Path(base).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        suffix = ".jpg"
    
    filename = f"logo_{portal_prefix}_{portal_id}{suffix}"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.debug(f"Permission denied creating directory {target_dir}")

    target_path = target_dir / filename
    try:
        if target_path.exists() and target_path.stat().st_size > 1024:
            return filename
    except PermissionError:
        pass

    try:
        logger.info(f"Downloading developer logo: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        with open(target_path, "wb") as f:
            shutil.copyfileobj(response.raw, f)
        return filename
    except Exception as e:
        logger.error(f"Error downloading developer logo {url}: {e}")
        return ""


def save_images(urls: list[str], target_dir: Path, config: ScraperConfig) -> list[str]:
    """
    Downloads and saves a list of images.
    Returns list of successful filenames.
    """
    saved_filenames = []
    skipped_count = 0
    unique_urls = [u for u in set(urls) if u and u.strip()]
    
    for url in unique_urls:
        fname, was_skipped = download_image(url, target_dir, config.force_image_download)
        if fname:
            saved_filenames.append(fname)
            if was_skipped:
                skipped_count += 1
            
    downloaded_count = len(saved_filenames) - skipped_count
    if downloaded_count > 0:
        logger.info(f"Successfully downloaded {downloaded_count} images (skipped {skipped_count} existing) for {target_dir.name}")
    elif skipped_count > 0:
        logger.info(f"Skipped {skipped_count} existing images for {target_dir.name}")
    else:
        logger.info(f"No valid images to process for {target_dir.name}")
        
    return saved_filenames
