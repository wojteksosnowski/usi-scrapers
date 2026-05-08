from datetime import datetime
from .base import BaseAdapter
from .utils import get_val

class OtodomAdapter(BaseAdapter):
    @staticmethod
    def transform(raw_data: dict, investment_slug: str, developer_slug: str) -> dict:
        if isinstance(raw_data, dict) and "value" in raw_data:
            raw_data = raw_data["value"]
            
        if isinstance(raw_data, dict) and "ad" in raw_data:
            raw_data = raw_data["ad"]

        # Otodom stores lat/lon in location.coordinates
        loc = get_val(raw_data, "location", {})
        coords = get_val(loc, "coordinates", {})
        lat = get_val(coords, "latitude")
        lng = get_val(coords, "longitude")
        
        # Fallback to mapDetails if coordinates not present
        if not lat or not lng:
            map_details = get_val(loc, "mapDetails", {})
            lat = get_val(map_details, "lat")
            lng = get_val(map_details, "lon")
            
        lat_lng = [lat, lng]

        # Delivery
        delivery = get_val(raw_data, "investmentEstimatedDelivery", {})
        dq = get_val(delivery, "quarter")
        dy = get_val(delivery, "year")
        delivery_str = f"{dq} kw. {dy}" if dq and dy else None

        # Address
        address_obj = get_val(loc, "address", {})
        street = get_val(get_val(address_obj, "street", {}), "name", "")
        city = get_val(get_val(address_obj, "city", {}), "name", "")
        district = get_val(get_val(address_obj, "district", {}), "name", "")
        address = f"{street}, {city}" if street and city else street or city or None

        # Characteristics
        characteristics = get_val(raw_data, "characteristics", [])
        char_dict = {c.get("key"): c.get("value") for c in characteristics if isinstance(c, dict)}
        
        # Robust extraction from 'target' block (often has cleaner values)
        target = get_val(raw_data, "target", {})
        
        try:
            units_count = int(char_dict.get("number_of_properties")) if char_dict.get("number_of_properties") else None
            if not units_count and target.get("Number_of_properties"):
                units_count = int(target["Number_of_properties"])
        except (ValueError, TypeError):
            units_count = None
            
        # Financials
        try:
            # Price per m2
            p_m2_min = float(char_dict.get("price_per_m_from")) if char_dict.get("price_per_m_from") else None
            if not p_m2_min and target.get("Price_per_m_from"):
                p_m2_min = float(target["Price_per_m_from"])
            
            p_m2_max = float(char_dict.get("price_per_m_to")) if char_dict.get("price_per_m_to") else None
            if not p_m2_max and target.get("Price_per_m_to"):
                p_m2_max = float(target["Price_per_m_to"])

            # Total price
            price_min = float(char_dict.get("price_from")) if char_dict.get("price_from") else None
            if not price_min and target.get("Price_from"):
                price_min = float(target["Price_from"])
                
            price_max = float(char_dict.get("price_to")) if char_dict.get("price_to") else None
            if not price_max and target.get("Price_to"):
                price_max = float(target["Price_to"])

        except (ValueError, TypeError):
            p_m2_min = None
            p_m2_max = None
            price_min = None
            price_max = None

        # Delivery - handle "ready" state from target.State
        if not delivery_str:
            state = target.get("State", [])
            if isinstance(state, list) and "ready" in state:
                delivery_str = "Gotowe"
            elif isinstance(state, str) and state == "ready":
                delivery_str = "Gotowe"

        # Extract images
        image_urls = []
        images_raw = get_val(raw_data, "images", [])
        if isinstance(images_raw, list):
            for img in images_raw:
                if not isinstance(img, dict): continue
                # Common Otodom keys: large, medium, small, thumbnail
                # Prefer large, then generic url, then whatever is first
                img_url = img.get("large") or img.get("medium") or img.get("url")
                if not img_url:
                    # Take first available value that looks like a URL
                    for val in img.values():
                        if isinstance(val, str) and val.startswith("http"):
                            img_url = val
                            break
                if img_url:
                    image_urls.append(img_url)

        # Identification - extract Hash ID from slug if possible (Coda compatibility)
        full_slug = get_val(raw_data, "slug", "")
        numeric_id = str(get_val(raw_data, "id"))
        oto_id = numeric_id
        
        if "-ID" in full_slug:
            oto_id = full_slug.split("-ID")[-1]
        elif "ID" in full_slug:
            oto_id = full_slug.split("ID")[-1]

        return {
            "investment_slug": investment_slug,
            "developer_slug": developer_slug,
            "name": get_val(raw_data, "title"),
            "developer": get_val(get_val(raw_data, "agency"), "name"),
            "status": "Brak",
            "sources": {
                "oto": {
                    "id": oto_id,
                    "numeric_id": numeric_id,
                    "url": get_val(raw_data, "url"),
                    "last_sync": datetime.now().isoformat()
                }
            },
            "location": {
                "coords": lat_lng,
                "address": address,
                "city": city,
                "district": district
            },
            "specifications": {
                "units_count": units_count,
                "delivery_date": delivery_str,
                "delivery_quarter": dq,
                "delivery_year": dy
            },
            "financials": {
                "price_min": price_min,
                "price_max": price_max,
                "price_avg": None,
                "price_m2_min": p_m2_min,
                "price_m2_max": p_m2_max
            },
            "amenities": {
                "labels": get_val(raw_data, "features", []),
                "matched": []
            },
            "images_count": get_val(raw_data, "images_count", len(image_urls)),
            "image_paths": get_val(raw_data, "image_paths", []),
            "image_urls": image_urls
        }
