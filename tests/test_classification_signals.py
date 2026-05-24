import pytest
import json
from pathlib import Path
from usi_scrapers.mapping import resolve_path, get_mapping

# Helper to load a raw test file
def load_raw_test_file(filename):
    path = Path(__file__).parent.parent / "usi_scrapers" / "schemas" / "porta_data_mapping_tests" / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_otodom_signals_extraction_residential():
    data = load_raw_test_file("raw_oto_nowa-polnica.json")
    # In this file, the root object contains "ad"
    mapping = get_mapping("oto", "investment")
    signals_mapping = mapping.get("signals")
    
    signals = {k: resolve_path(data, v) for k, v in signals_mapping.items()}
    
    assert signals["apartments"] == "11"
    assert signals["houses"] is None
    assert signals["commercial"] is None
    assert "flats" in signals["investment"]

def test_rp_signals_extraction():
    data = load_raw_test_file("raw_rp_17812.json")
    mapping = get_mapping("rp", "investment")
    signals_mapping = mapping.get("signals")
    
    signals = {k: resolve_path(data, v) for k, v in signals_mapping.items()}
    
    # properties_count_for_sale is at the root in RP API
    assert signals["apartments"] == 100
    # commercial_rental
    assert signals["rental"] is False

def test_to_signals_extraction():
    data = load_raw_test_file("raw_to_i8975118.json")
    mapping = get_mapping("to", "investment")
    signals_mapping = mapping.get("signals")
    
    signals = {k: resolve_path(data, v) for k, v in signals_mapping.items()}
    
    # url contains "mieszkania-na-sprzedaz"
    assert signals["apartments"] == "mieszkania-na-sprzedaz"
    assert signals["houses"] is None
