with open("CHANGELOG.md", "r", encoding="utf-8") as f:
    content = f.read()

new_content = """# Changelog

## [0.9.1] - 2026-06-03
- **Feature**: Added new dedicated transformers (`rp_extract_amenities`, `oto_extract_delivery`, `to_extract_amenities`) for fully declarative amenity and delivery date extraction.
- **Mapping**: Updated `portal_data_mapping.json` for all 3 portals to expose `amenities` and `delivery_date` using the new transformers, removing the need for manual loops in downstream apps.

""" + content[13:]

with open("CHANGELOG.md", "w", encoding="utf-8") as f:
    f.write(new_content)
