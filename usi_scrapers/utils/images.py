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
    Extracts and cleans filename from URL, removing parameters and ensuring correct extension.
    Handles TabelaOfert and Otodom CDN patterns.
    """
    # 1. Otodom CDN: .../v1/files/{unique_id}/image;s=...
    m_oto = re.search(r'/([^/]+)/image[;?]', url)
    if m_oto:
        return m_oto.group(1) + '.jpg'

    # 2. TabelaOfert CDN: .../quality_N,scale_N,ID-filename.ext or .../ID-filename.ext
    m_to = re.search(r'ID-([^/?#]+)', url)
    if m_to:
        filename = m_to.group(1)
        # Ensure it has an extension if it was stripped
        if not any(filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
            # Check if there's an extension in the original URL after ID-
            ext_match = re.search(r'\.([a-z0-9]+)(?:[?#]|$)', url, re.I)
            if ext_match:
                filename += "." + ext_match.group(1)
            else:
                filename += ".jpg" # Fallback
        return filename

    # 3. Standard extraction
    # Remove URL parameters and fragments
    base_url = url.split("?")[0].split("#")[0]
    filename = unquote(base_url.split("/")[-1])
    
    # Extract something like file.jpg, file.png, etc.
    # Strip cache-buster/hash suffix like photo_e94b5737.webp → photo.webp
    filename = re.sub(r'_[a-f0-9]{8}\.', '.', filename)

    match = re.search(r'([^\/]+\.(?:jpg|jpeg|png|webp))', filename, re.IGNORECASE)
    if match:
        return match.group(1)

    for ext in IMAGE_EXTENSIONS:
        if ext in filename.lower():
            idx = filename.lower().find(ext)
            return filename[:idx + len(ext)]

    return filename

def download_image(url: str, developer_slug: str, investment_slug: str, config: ScraperConfig) -> tuple[str, bool]:
    """
    Downloads image from URL and saves it to {public_dir}/USI/{dev_slug}/{inv_slug}/{filename}.
    Returns a tuple: (filename if successful or empty string otherwise, was_skipped boolean).
    """
    filename = clean_filename(url)
    
    if not filename:
        logger.warning(f"Could not extract filename from URL: {url}")
        return "", False
        
    # Standardize image directory path
    usi_root = config.public_dir / "USI"
    target_dir = usi_root / developer_slug / investment_slug
    
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # macOS drive permission issues
        logger.debug(f"Permission denied creating/accessing directory {target_dir}, proceeding anyway")
        
    target_path = target_dir / filename
    
    try:
        if not config.force_image_download and target_path.exists():
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

def download_developer_logo(url: str, dev_slug: str, config: ScraperConfig, portal_prefix: str = "raw", portal_id: str | None = None) -> str:
    """
    Downloads developer logo and saves to {public_dir}/USIdev/{dev_slug}/logo_{portal_prefix}_{portal_id}.{ext}.
    portal_id is required — ID-only naming enforced (no slug fallback).
    Returns filename if successful, empty string otherwise.
    """
    if not portal_id:
        raise ValueError(
            f"download_developer_logo: portal_id is required for {portal_prefix}/{dev_slug}. "
            "Slug-based fallback is not allowed (ID-only policy)."
        )

    base = url.split("?")[0].split("#")[0]
    suffix = Path(base).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        suffix = ".jpg"
    
    filename = f"logo_{portal_prefix}_{portal_id}{suffix}"

    target_dir = config.public_dir / "USIdev" / dev_slug
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


def save_images(urls: list[str], developer_slug: str, investment_slug: str, config: ScraperConfig) -> list[str]:
    """
    Downloads and saves a list of images.
    Returns list of successful filenames.
    """
    saved_filenames = []
    skipped_count = 0
    unique_urls = [u for u in set(urls) if u and u.strip()]
    
    for url in unique_urls:
        fname, was_skipped = download_image(url, developer_slug, investment_slug, config)
        if fname:
            saved_filenames.append(fname)
            if was_skipped:
                skipped_count += 1
            
    downloaded_count = len(saved_filenames) - skipped_count
    if downloaded_count > 0:
        logger.info(f"Successfully downloaded {downloaded_count} images (skipped {skipped_count} existing) for {investment_slug}")
    elif skipped_count > 0:
        logger.info(f"Skipped {skipped_count} existing images for {investment_slug}")
    else:
        logger.info(f"No valid images to process for {investment_slug}")
        
    return saved_filenames
