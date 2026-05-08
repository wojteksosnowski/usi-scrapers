import logging
import json

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"

def geocode_address(address: str, api_key: str, fetcher=None) -> tuple[float, float] | tuple[None, None]:
    """Convert address string to (lat, lon) using HERE Geocoding API."""
    if not address or not api_key:
        return None, None
    
    try:
        url = f"{_GEOCODE_URL}?q={address}&apiKey={api_key}"
        
        if fetcher:
            res_text = fetcher.fetch(url)
        else:
            import requests
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            res_text = res.text

        if not res_text:
            return None, None
            
        data = json.loads(res_text)
        items = data.get("items", [])
        if items:
            pos = items[0].get("position", {})
            return pos.get("lat"), pos.get("lng")
    except Exception as e:
        logger.error(f"Geocoding error for {address}: {e}")
        
    return None, None
