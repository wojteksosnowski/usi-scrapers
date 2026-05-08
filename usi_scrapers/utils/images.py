import requests
import shutil
import re
from pathlib import Path
from urllib.parse import unquote
import logging

logger = logging.getLogger("usi_scrapers.utils.images")

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".avif", ".heic"]

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
    
    # Strip cache-buster/hash suffix like _e94b5737.webp or _a789f3d8.webp before matching
    filename = re.sub(r'_[a-f0-9]{8}\.', '.', filename)
    
    # Extract something like file.jpg, file.png, etc.
    match = re.search(r'([^\/]+\.(?:jpg|jpeg|png|webp|avif|heic))', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Fallback: check if there's any of the extensions in the filename
    for ext in IMAGE_EXTENSIONS:
        if ext in filename.lower():
            idx = filename.lower().find(ext)
            return filename[:idx + len(ext)]

    return filename

def download_image(url: str, public_dir: Path, developer_slug: str, investment_slug: str) -> str:
    """
    Downloads image from URL and saves it to <public_dir>/USI/{dev_slug}/{inv_slug}/{filename}.
    Returns filename if successful, empty string otherwise.
    """
    filename = clean_filename(url)
    
    if not filename:
        logger.warning(f"Could not extract filename from URL: {url}")
        return ""
        
    target_dir = public_dir / "USI" / developer_slug / investment_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    
    if target_path.exists():
        # Optional: check if file is too small (incomplete download)
        if target_path.stat().st_size > 1024:
            return filename
        
    try:
        logger.info(f"Downloading image: {url}")
        # Use a real User-Agent to avoid being blocked
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        
        with open(target_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
            
        return filename
    except Exception as e:
        logger.error(f"Error downloading image {url}: {e}")
        return ""

def save_images(urls: list[str], public_dir: Path, developer_slug: str, investment_slug: str) -> list[str]:
    """
    Downloads and saves a list of images.
    Returns list of successful filenames.
    """
    saved_filenames = []
    # Use set to avoid duplicate URLs
    unique_urls = [u for u in set(urls) if u and u.strip()]
    
    for url in unique_urls:
        fname = download_image(url, public_dir, developer_slug, investment_slug)
        if fname:
            saved_filenames.append(fname)
            
    logger.info(f"Successfully saved {len(saved_filenames)} images for {investment_slug} in {public_dir}")
    return saved_filenames
