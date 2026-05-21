import json
import sys
from pathlib import Path

# Add the project root to the sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from usi_scrapers import get_mapping, resolve_path

TEST_DIR = Path(__file__).parent.parent / "usi_scrapers" / "schemas" / "porta_data_mapping_tests"

def test_portal(portal_prefix, file_path):
    print(f"\n--- Testing {portal_prefix} with {file_path.name} ---")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Test investment mapping
    inv_mapping = get_mapping(portal_prefix, "investment")
    if inv_mapping:
        print("Investment Data:")
        # For Otodom, mapping is now relative to the root page_props (the file itself)
        inv_data = data
        for key, path_def in inv_mapping.items():
            if key in ["id", "hash_id", "slug", "name", "developer_id", "developer_slug", "developer_name", "units_count", "price_min", "price_max", "ceiling_height_min", "ceiling_height_max"]:
                val = resolve_path(inv_data, path_def)
                print(f"  {key}: {val}")
    
    # Test developer mapping
    dev_mapping = get_mapping(portal_prefix, "developer")
    if dev_mapping:
        print("Developer Data:")
        for key, path_def in dev_mapping.items():
            if key in ["id", "slug", "name"]:
                val = resolve_path(data, path_def)
                print(f"  {key}: {val}")

def main():
    if not TEST_DIR.exists():
        print(f"Test directory not found: {TEST_DIR}")
        return

    for file_path in TEST_DIR.glob("raw_*.json"):
        name = file_path.name
        if name.startswith("raw_rp_"):
            test_portal("rp", file_path)
        elif name.startswith("raw_oto_"):
            test_portal("oto", file_path)
        elif name.startswith("raw_to_"):
            test_portal("to", file_path)
        else:
            print(f"Unknown portal for file: {name}")

if __name__ == "__main__":
    main()
