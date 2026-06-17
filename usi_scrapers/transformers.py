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

@register_transformer("extract_quarter_from_qformat")
def _extract_quarter_from_qformat(value: Any) -> int | None:
    """Wyciąga numer kwartału z formatu YYYY-QX lub daty ISO."""
    if not isinstance(value, str):
        return None
    # Obsługa formatu YYYY-QX
    match_q = re.search(r'-Q([1-4])', value, re.IGNORECASE)
    if match_q:
        return int(match_q.group(1))
    # Obsługa formatu ISO YYYY-MM-DD
    match_date = re.search(r'^\d{4}-([0-1]\d)', value)
    if match_date:
        month = int(match_date.group(1))
        return (month - 1) // 3 + 1
    return None

@register_transformer("extract_year_from_qformat")
def _extract_year_from_qformat(value: Any) -> int | None:
    """Wyciąga rok z formatu YYYY-QX lub daty ISO."""
    if not isinstance(value, str):
        return None
    match = re.search(r'^(\d{4})', value)
    if match:
        return int(match.group(1))
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
        # the actual data is sometimes nested under 'value' or 'image'
        data = img_obj.get("image") or img_obj.get("value") or img_obj
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

@register_transformer("oto_extract_coords_as_array")
def _oto_extract_coords_as_array(value: Any) -> list[float] | None:
    """
    Extracts [latitude, longitude] from the root Otodom data object.
    Looks for nested coordinates under ad.location.coordinates.
    Returns [lat, lon] or None when not found.
    """
    if not isinstance(value, dict):
        return None

    # Try direct nested path: ad.location.coordinates
    ad = value.get("ad") or value.get("props", {}).get("pageProps", {}).get("ad", {})
    if isinstance(ad, dict):
        coords = ad.get("location", {}).get("coordinates", {})
        if isinstance(coords, dict):
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is not None and lon is not None:
                try:
                    return [float(lat), float(lon)]
                except (ValueError, TypeError):
                    pass

    # Fallback: raw_details
    raw = value.get("raw_details", {})
    if isinstance(raw, dict):
        lat = raw.get("latitude")
        lon = raw.get("longitude")
        if lat is not None and lon is not None:
            try:
                return [float(lat), float(lon)]
            except (ValueError, TypeError):
                pass

    return None

@register_transformer("clean_street")
def _clean_street(value: Any) -> str | None:
    """Removes 'ul. ' or 'al. ' prefixes from street names."""
    if isinstance(value, str):
        value = value.strip()
        lower_val = value.lower()
        if lower_val.startswith("ul. "):
            return value[4:].strip()
        if lower_val.startswith("ul."):
            return value[3:].strip()
        if lower_val.startswith("al. "):
            return value[4:].strip()
        if lower_val.startswith("al."):
            return value[3:].strip()
        return value
    return None

@register_transformer("rp_extract_city")
def _rp_extract_city(value: Any) -> str | None:
    """Extracts city from RynekPierwotny address string: 'Kraków, Czyżyny, ul. Akacjowa' -> 'Kraków'"""
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        if len(parts) >= 1:
            return parts[0]
    return None

@register_transformer("rp_extract_region")
def _rp_extract_region(value: Any) -> str | None:
    """Extracts region/district from RP address string: 'Kraków, Czyżyny, ul. Akacjowa' -> 'Czyżyny'"""
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        if len(parts) >= 3:
            return parts[1]
    return None

@register_transformer("rp_extract_street")
def _rp_extract_street(value: Any) -> str | None:
    """Extracts and cleans street from RP address string: 'Kraków, Czyżyny, ul. Akacjowa' -> 'Akacjowa'"""
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        if len(parts) >= 2:
            return _clean_street(parts[-1])
        if len(parts) == 1:
            # Only city name provided
            return None
    return None



@register_transformer("rp_extract_amenities")
def _rp_extract_amenities(value: Any) -> list[str]:
    """
    Extracts amenity IDs from RynekPierwotny features list.
    """
    if not isinstance(value, list):
        return []
    return [str(item.get("id")) for item in value if isinstance(item, dict) and item.get("id") is not None]

@register_transformer("oto_extract_delivery")
def _oto_extract_delivery(value: Any) -> str | None:
    """
    Extracts project finish date from Otodom topInformation.
    """
    if not isinstance(value, list):
        return None
    for item in value:
        if isinstance(item, dict) and item.get("label") == "project_finish_date":
            vals = item.get("values")
            if isinstance(vals, list) and len(vals) > 0:
                return str(vals[0])
            elif isinstance(vals, str):
                return vals
    return None

@register_transformer("to_extract_amenities")
def _to_extract_amenities(value: Any) -> list[str]:
    """
    Extracts amenities strings from TabelaOfert additionalProperty list.
    """
    if not isinstance(value, list):
        return []
    amenities = []
    for item in value:
        if isinstance(item, dict):
            name = item.get("name")
            val = item.get("value")
            if name and val:
                val_str = str(val).strip().lower()
                if val_str == "tak":
                    amenities.append(str(name))
                elif val_str not in ["nie", "brak", "false", "0"]:
                    amenities.append(f"{name}: {val}")
    return amenities

@register_transformer("to_float")
def _to_float(value: Any) -> float | None:
    """Safely converts a value to float."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", ".")
        return float(value)
    except (ValueError, TypeError):
        return None

@register_transformer("oto_delivery_date")
def _oto_delivery_date(value: Any) -> str | None:
    """Extracts project finish date from Otodom topInformation and converts to YYYY-QX."""
    if not isinstance(value, list):
        return None
    val_str = None
    for item in value:
        if isinstance(item, dict) and item.get("label") == "project_finish_date":
            vals = item.get("values")
            if isinstance(vals, list) and len(vals) > 0:
                val_str = str(vals[0])
            elif isinstance(vals, str):
                val_str = vals
            break
            
    if val_str:
        try:
            parts = val_str.split("-")
            if len(parts) >= 2:
                dy = int(parts[0])
                dq = (int(parts[1]) - 1) // 3 + 1
                return f"{dy}-Q{dq}"
        except (ValueError, TypeError):
            pass
    return None

@register_transformer("strip_html")
def _strip_html(value: Any) -> str | None:
    """Removes HTML tags and normalizes whitespace from a string."""
    if not isinstance(value, str):
        return None
    # Replace <br> and <p> with newlines
    value = re.sub(r'<br\s*/?>|</?p>', '\n', value, flags=re.IGNORECASE)
    # Remove all other HTML tags
    clean = re.sub(r'<[^>]+>', '', value)
    # Normalize multiple newlines and spaces
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    clean = re.sub(r' {2,}', ' ', clean)
    return clean.strip() or None

@register_transformer("clean_phone")
def _clean_phone(value: Any) -> str | None:
    """Cleans phone numbers, removing spaces and standardizing format."""
    if not isinstance(value, str):
        if isinstance(value, list) and len(value) > 0:
            value = str(value[0])
        else:
            return None
            
    # Keep only digits and '+'
    cleaned = re.sub(r'[^\d\+]', '', value)
    
    if not cleaned:
        return None
        
    return cleaned

@register_transformer("extract_first_item")
def _extract_first_item(value: Any) -> Any:
    """Extracts the first item from a list, or returns the value if not a list."""
    if isinstance(value, list):
        return value[0] if len(value) > 0 else None
    return value

@register_transformer("extract_facebook")
def _extract_facebook(value: Any) -> str | None:
    """Extracts Facebook URL from a list or string."""
    return _extract_social(value, "facebook")

@register_transformer("extract_instagram")
def _extract_instagram(value: Any) -> str | None:
    """Extracts Instagram URL from a list or string."""
    return _extract_social(value, "instagram")

@register_transformer("extract_youtube")
def _extract_youtube(value: Any) -> str | None:
    """Extracts YouTube URL from a list or string."""
    return _extract_social(value, "youtube")

@register_transformer("extract_linkedin")
def _extract_linkedin(value: Any) -> str | None:
    """Extracts LinkedIn URL from a list or string."""
    return _extract_social(value, "linkedin")

def _extract_social(value: Any, platform: str) -> str | None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                # Check if any value or key matches the platform
                is_platform = False
                for k, v in item.items():
                    if platform in str(k).lower() or platform in str(v).lower():
                        is_platform = True
                if is_platform:
                    # Find the URL
                    for v in item.values():
                        if isinstance(v, str) and (v.startswith("http") or "www." in v):
                            return v
                # Specific check if dict has url/link field and it matches platform
                url = item.get("url") or item.get("link") or item.get("value")
                if isinstance(url, str) and platform in url.lower():
                    return url
            elif isinstance(item, str):
                if platform in item.lower():
                    return item
    elif isinstance(value, str):
        if platform in value.lower():
            return value
    return None
