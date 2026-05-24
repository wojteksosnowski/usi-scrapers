import json
import pytest
from pathlib import Path
from usi_scrapers import get_mapping, resolve_path

TEST_DIR = Path(__file__).parent.parent / "usi_scrapers" / "schemas" / "porta_data_mapping_tests"

def get_test_files():
    if not TEST_DIR.exists():
        return []
    return list(TEST_DIR.glob("raw_*.json"))

@pytest.mark.parametrize("file_path", get_test_files(), ids=lambda p: p.name)
def test_portal_mapping(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    name = file_path.name
    if name.startswith("raw_rp_"):
        portal_prefix = "rp"
    elif name.startswith("raw_oto_"):
        portal_prefix = "oto"
    elif name.startswith("raw_to_"):
        portal_prefix = "to"
    else:
        pytest.fail(f"Unknown portal for file: {name}")

    # Test investment mapping
    inv_mapping = get_mapping(portal_prefix, "investment")
    assert inv_mapping is not None, f"No investment mapping for {portal_prefix}"
    
    for key, path_def in inv_mapping.items():
        # Just verify that mapping doesn't crash and returns expected types if possible
        # We don't enforce specific values here as these are raw samples
        resolve_path(data, path_def)
    
    # Test developer mapping
    dev_mapping = get_mapping(portal_prefix, "developer")
    if dev_mapping:
        for key, path_def in dev_mapping.items():
            resolve_path(data, path_def)
