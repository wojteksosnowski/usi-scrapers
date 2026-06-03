import json

with open("usi_scrapers/schemas/portal_data_mapping.json", "r", encoding="utf-8") as f:
    mapping = json.load(f)

# RP amenities
mapping["portals"]["rp"]["investment"]["amenities"] = {
    "path": "features",
    "transform": "rp_extract_amenities"
}

# OTO delivery_date
mapping["portals"]["oto"]["investment"]["delivery_date"] = {
    "path": "ad.topInformation",
    "transform": "oto_extract_delivery"
}

# TO amenities
mapping["portals"]["to"]["investment"]["amenities"] = {
    "path": "additionalProperty",
    "transform": "to_extract_amenities"
}

with open("usi_scrapers/schemas/portal_data_mapping.json", "w", encoding="utf-8") as f:
    json.dump(mapping, f, indent=2, ensure_ascii=False)
