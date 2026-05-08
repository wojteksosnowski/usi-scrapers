import re
import logging
from datetime import datetime
from .base import BaseAdapter
from .utils import get_val
from ..utils.geocoder import geocode_address
from ..utils.string import slugify

logger = logging.getLogger(__name__)

class TOAdapter(BaseAdapter):
    @staticmethod
    def transform(raw_data: dict, investment_slug: str, developer_slug: str) -> dict:
        # TabelaOfert raw_data is the schema.org Product dict
        brand = raw_data.get("brand", {})
        developer_name = brand.get("name") if isinstance(brand, dict) else None
        
        # Address and Coordinates from first offer
        offers_list = raw_data.get("offers", {}).get("offers", [])
        first_offer = offers_list[0] if isinstance(offers_list, list) and len(offers_list) > 0 else {}
        item_offered = first_offer.get("itemOffered", {})
        address_obj = item_offered.get("address", {})
        
        street = address_obj.get("streetAddress")
        city = address_obj.get("addressLocality")
        district = address_obj.get("addressRegion")

        # Fallback to extracted data from scraper
        ext_loc = raw_data.get("_extracted_location", {})
        if not street: street = ext_loc.get("address") # Scraper address includes city usually
        if not city: city = ext_loc.get("city")
        if not district: district = ext_loc.get("region")

        address = ", ".join(filter(None, [street, city])) or None
        if street and city and city in street: address = street # Avoid "Street, City, City"
        
        geo = item_offered.get("geo", {})
        lat = geo.get("latitude")
        lng = geo.get("longitude")

        if lat is None: lat = ext_loc.get("latitude")
        if lng is None: lng = ext_loc.get("longitude")
        
        if (lat is None or lng is None) and address:
            logger.info(f"Missing coordinates for {investment_slug}, attempting geocoding for: {address}")
            # Note: In the new architecture, we should ideally pass the API key from config
            # For now we'll assume it's available or handled by the caller if we refactor further
            # But let's keep it simple for the adapter: it tries if it can.
            from ..config import ScraperConfig
            config = ScraperConfig()
            lat, lng = geocode_address(address, config.here_api_key)
            if lat:
                logger.info(f"Geocoded {address} to {lat}, {lng}")

        lat_lng = [float(lat) if lat else None, float(lng) if lng else None]

        # Name cleaning
        name = raw_data.get("name")
        if not name:
            name = investment_slug.replace("-", " ").title()

        # Delivery Date
        delivery_str = None
        dq, dy = None, None
        for prop in raw_data.get("additionalProperty", []):
            if prop.get("name") == "Termin oddania":
                delivery_str = prop.get("value")
                if delivery_str:
                    m = re.search(r"([IVX]+)\s+kwarta.\s+(\d{4})", delivery_str, re.IGNORECASE)
                    if m:
                        roman = m.group(1).upper()
                        roman_map = {"I": 1, "II": 2, "III": 3, "IV": 4}
                        dq = roman_map.get(roman)
                        dy = int(m.group(2))
                break

        # Price
        agg_offers = raw_data.get("offers", {})
        try:
            price_min = float(agg_offers.get("lowPrice") or 0) or None
            price_max = float(agg_offers.get("highPrice") or 0) or None
        except:
            price_min, price_max = None, None
            
        # Price per m2 from additionalProperty
        p_m2_min, p_m2_max = None, None
        for prop in raw_data.get("additionalProperty", []):
            if prop.get("name") == "Cena za m2 od":
                try: 
                    val = prop.get("value", "").replace(" ", "").replace(",", ".")
                    p_m2_min = float(re.sub(r"[^\d.]", "", val))
                except: pass
            if prop.get("name") == "Cena za m2 do":
                try: 
                    val = prop.get("value", "").replace(" ", "").replace(",", ".")
                    p_m2_max = float(re.sub(r"[^\d.]", "", val))
                except: pass
        
        # Fallback: calculate from individual offers if missing
        if p_m2_min is None or p_m2_max is None:
            m2_prices = []
            for off in offers_list:
                try:
                    price = float(str(off.get("price") or 0).replace(" ", "").replace(",", "."))
                    size = float(str(off.get("itemOffered", {}).get("floorSize", {}).get("value") or 0).replace(" ", "").replace(",", "."))
                    if price > 0 and size > 0:
                        m2_prices.append(price / size)
                except:
                    continue
            
            if m2_prices:
                if p_m2_min is None: p_m2_min = min(m2_prices)
                if p_m2_max is None: p_m2_max = max(m2_prices)

        # Extract images
        raw_urls = raw_data.get("_raw_gallery_urls", [])
        image_urls = []
        
        if raw_urls:
            from ..utils.images import clean_filename
            by_filename = {}
            for url in raw_urls:
                fname = clean_filename(url)
                # For TabelaOfert we still want to prefer 'scale' if available in URL
                # to get the highest resolution.
                m = re.search(r"scale_(\d+)", url)
                scale = int(m.group(1)) if m else 0
                
                if fname not in by_filename or scale > by_filename[fname][0]:
                    by_filename[fname] = (scale, url)
            
            image_urls = [v[1] for v in by_filename.values()]

        return {
            "investment_slug": investment_slug,
            "developer_slug": developer_slug,
            "name": raw_data.get("name"),
            "developer": developer_name,
            "status": "Brak",
            "sources": {
                "to": {
                    "id": None,
                    "url": raw_data.get("url"),
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
                "units_count": agg_offers.get("offerCount"),
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
                "labels": [],
                "raw_codes": [p.get("name") for p in raw_data.get("additionalProperty", [])]
            },
            "images_count": raw_data.get("images_count", len(image_urls)),
            "image_paths": raw_data.get("image_paths", []),
            "image_urls": image_urls
        }
