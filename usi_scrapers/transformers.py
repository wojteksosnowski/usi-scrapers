"""
Data Transformers for the Mapping Engine.
Allows applying specific logic to parsed values.
"""
import re
from typing import Any, Callable

_TRANSFORMERS: dict[str, Callable[[Any], Any]] = {}

def register_transformer(name: str):
    def decorator(func: Callable[[Any], Any]):
        _TRANSFORMERS[name] = func
        return func
    return decorator

def apply_transformer(name: str, value: Any) -> Any:
    if value is None:
        return None
    if name not in _TRANSFORMERS:
        raise ValueError(f"Unknown transformer: {name}")
    try:
        return _TRANSFORMERS[name](value)
    except Exception:
        return value

@register_transformer("cm_to_m")
def _cm_to_m(value: Any) -> float | None:
    """Converts a cm value (string or numeric) to meters."""
    try:
        if isinstance(value, str):
            # Extract just digits and dots/commas
            value = value.replace(",", ".")
            m = re.search(r"(\d+(?:\.\d+)?)", value)
            if not m:
                return None
            num = float(m.group(1))
        else:
            num = float(value)
        # Assuming typical ceiling heights, if it's over 100, it's likely cm.
        if num > 100:
            return round(num / 100, 2)
        return round(num, 2)
    except (ValueError, TypeError):
        return None

@register_transformer("date_to_quarter")
def _date_to_quarter(value: Any) -> int | None:
    """Converts a date string like '2025-01' to a quarter number (1-4)."""
    try:
        if isinstance(value, str):
            parts = value.split("-")
            if len(parts) >= 2:
                month = int(parts[1])
                return (month - 1) // 3 + 1
        return None
    except (ValueError, TypeError):
        return None

@register_transformer("rp_gallery_to_flat_list")
def _rp_gallery_to_flat_list(value: Any) -> list[str]:
    """
    Takes the root JSON object for RynekPierwotny and extracts main_image and gallery
    into a single flat list of high-resolution URLs.
    """
    if not isinstance(value, dict):
        return []

    images = []

    def extract_best_url(img_obj: dict) -> str | None:
        if not isinstance(img_obj, dict):
            return None
        # the actual data is sometimes nested under 'value'
        data = img_obj.get("value", img_obj)
        if not isinstance(data, dict):
            return None
        # Prefer highest resolutions
        for key in ["g_img_2000", "g_img_1500", "g_img_1000", "m_img_1500", "m_img_983x552", "m_img_750", "v_log_159x120"]:
            if key in data and data[key]:
                return data[key]
        # fallback to the first string value found
        for k, v in data.items():
            if isinstance(v, str) and v.startswith("http"):
                return v
        return None

    main_img = extract_best_url(value.get("main_image", {}))
    if main_img:
        images.append(main_img)

    # try gallery or _raw_gallery
    gallery = value.get("gallery")
    if not gallery:
        gallery = value.get("_raw_gallery", {}).get("gallery")
    
    # if gallery is dict, it might be {"type": "arr", "value": [...]}
    if isinstance(gallery, dict) and "value" in gallery:
        gallery = gallery["value"]
    
    if isinstance(gallery, list):
        for img_obj in gallery:
            img_url = extract_best_url(img_obj)
            if img_url and img_url not in images:
                images.append(img_url)

    return images

@register_transformer("oto_gallery_to_flat_list")
def _oto_gallery_to_flat_list(value: Any) -> list[str]:
    """
    Takes the Otodom images array and extracts the 'large' resolution URLs.
    """
    if not isinstance(value, list):
        return []
    
    images = []
    for item in value:
        if isinstance(item, dict):
            url = item.get("large") or item.get("medium") or item.get("small")
            if url and url not in images:
                images.append(url)
                
    return images

