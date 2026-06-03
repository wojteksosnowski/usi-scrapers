with open("CLAUDE.md", "r", encoding="utf-8") as f:
    content = f.read()

mapping_docs = """
### 8. Unified Schema Mapping (portal_data_mapping)

The `usi-scrapers` package provides a declarative mapping engine to transform raw JSON records from different portals into a unified dictionary structure. This eliminates hardcoded nested property access (like `_get_val(raw, "features")`) from the downstream application (`usi-tracker`).

The mapping definitions are kept in `portal_data_mapping.json`.

```python
from usi_scrapers.mapping import transform_to_unified

# Assuming `raw_data` is the loaded raw_rp_123.json payload:
unified_data = transform_to_unified("rp", raw_data, "investment")

# → returns a flat dictionary based on portal_data_mapping.json keys
# {
#   "price": 500000.0,
#   "price_m2": 10000.0,
#   "segment": "apartments",
#   "transaction_type": "sale",
#   "city": "Warszawa",
#   "amenities": ["12", "14"],
#   ...
# }
```
"""

insert_pos = content.find("### Typical usi-tracker flow")
if insert_pos != -1:
    content = content[:insert_pos] + mapping_docs + "\n" + content[insert_pos:]
    with open("CLAUDE.md", "w", encoding="utf-8") as f:
        f.write(content)
