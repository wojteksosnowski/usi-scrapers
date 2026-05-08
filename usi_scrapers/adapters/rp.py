import re
import logging
from datetime import datetime
from .base import BaseAdapter
from .utils import get_val

logger = logging.getLogger(__name__)

class RPAdapter(BaseAdapter):
    @staticmethod
    def transform(raw_data: dict, investment_slug: str, developer_slug: str) -> dict:
        # Handle top-level Coda wrapper if present
        if isinstance(raw_data, dict) and "value" in raw_data:
            raw_data = raw_data["value"]

        # Extract specifications
        upper_date = get_val(raw_data, "construction_date_upper")
        if not upper_date:
            range_val = get_val(raw_data, "construction_date_range")
            upper_date = get_val(range_val, "upper") if isinstance(range_val, dict) else None
        
        delivery_str, dq, dy = None, None, None
        if upper_date:
            try:
                dt = datetime.fromisoformat(upper_date.split("T")[0])
                dq = (dt.month - 1) // 3 + 1
                dy = dt.year
                delivery_str = f"{dq} kw. {dy}"
            except:
                delivery_str = str(upper_date)

        # Extract financial data (handle RP v2 fields inside 'stats' or top level)
        stats = raw_data.get("stats", {})
        
        # Price per m2
        p_m2_min = get_val(raw_data, "ranges_price_m2_min") or get_val(stats, "ranges_price_m2_min")
        p_m2_max = get_val(raw_data, "ranges_price_m2_max") or get_val(stats, "ranges_price_m2_max")
        
        # Total price
        p_min = get_val(raw_data, "ranges_price_min") or get_val(stats, "ranges_price_min")
        p_max = get_val(raw_data, "ranges_price_max") or get_val(stats, "ranges_price_max")
        
        # Fallback to price_m2_range object if v2 fields are missing
        price_m2_range = get_val(raw_data, "price_m2_range")
        if isinstance(price_m2_range, dict):
            p_m2_min = p_m2_min or get_val(price_m2_range, "lower")
            p_m2_max = p_m2_max or get_val(price_m2_range, "upper")
            p_avg = get_val(price_m2_range, "average")
        else:
            p_avg = None
        
        if not p_avg and p_m2_min and p_m2_max:
            try:
                p_avg = (float(p_m2_min) + float(p_m2_max)) / 2
            except: pass

        # Extract images from gallery if present
        image_urls = []
        gallery_data = raw_data.get("_raw_gallery") or raw_data.get("gallery")
        if isinstance(gallery_data, dict):
            gallery_items = gallery_data.get("gallery", [])
            for item in gallery_items:
                img_data = item.get("image", {})
                if not isinstance(img_data, dict): continue
                
                # Find highest g_img_X resolution
                g_keys = [k for k in img_data.keys() if k.startswith("g_img_")]
                if g_keys:
                    sorted_keys = sorted(g_keys, key=lambda x: int(re.search(r"\d+", x).group() or 0), reverse=True)
                    img_url = img_data.get(sorted_keys[0])
                else:
                    img_url = img_data.get("url")
                
                if img_url:
                    image_urls.append(img_url)
        
        # Add main image if not in gallery
        main_img_data = get_val(raw_data, "main_image", {})
        if isinstance(main_img_data, dict):
            m_keys = [k for k in main_img_data.keys() if k.startswith("m_img_")]
            if m_keys:
                sorted_m = sorted(m_keys, key=lambda x: int(re.search(r"\d+", x).group() or 0), reverse=True)
                main_image = main_img_data.get(sorted_m[0])
            else:
                main_image = main_img_data.get("url")
            
            if main_image and main_image not in image_urls:
                image_urls.insert(0, main_image)

        # Geo point extraction
        geo = get_val(raw_data, "geo_point")
        coords = get_val(geo, "coordinates") if isinstance(geo, dict) else None
        lat_lng = [None, None]
        if isinstance(coords, list) and len(coords) >= 2:
            lat_lng = [coords[1], coords[0]]

        # Location extraction from region object
        region = raw_data.get("region", {})
        city = None
        district = None
        if isinstance(region, dict):
            city_data = region.get("stats", {}).get("region_type_city")
            if isinstance(city_data, dict):
                city = city_data.get("name")
            elif region.get("type") == 5:
                city = region.get("name")
            
            district_data = region.get("stats", {}).get("region_type_district")
            if isinstance(district_data, dict):
                district = district_data.get("name")
            elif not city and region.get("type") == 6:
                district = region.get("name")

        # Fallback for city from address
        raw_address = get_val(raw_data, "address")
        if not city and raw_address:
            parts = [p.strip() for p in raw_address.split(",")]
            if len(parts) >= 1:
                city = parts[0]

        return {
            "investment_slug": investment_slug,
            "developer_slug": developer_slug,
            "name": get_val(raw_data, "name"),
            "developer": get_val(get_val(raw_data, "vendor"), "name"),
            "status": "Brak",
            "sources": {
                "rp": {
                    "id": str(get_val(raw_data, "id")),
                    "url": get_val(raw_data, "url"),
                    "last_sync": datetime.now().isoformat()
                }
            },
            "location": {
                "coords": lat_lng,
                "address": raw_address,
                "city": city,
                "district": district
            },
            "specifications": {
                "units_count": get_val(raw_data, "properties"),
                "delivery_date": delivery_str,
                "delivery_quarter": dq,
                "delivery_year": dy
            },
            "financials": {
                "price_min": p_min,
                "price_max": p_max,
                "price_avg": p_avg,
                "price_m2_min": p_m2_min,
                "price_m2_max": p_m2_max
            },
            "amenities": {
                "labels": [], 
                "raw_codes": get_val(raw_data, "facilities", [])
            },
            "images_count": len(image_urls),
            "image_urls": image_urls
        }
