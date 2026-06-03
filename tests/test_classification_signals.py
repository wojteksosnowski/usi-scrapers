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
    mapping = get_mapping("oto", "investment")
    
    segment = resolve_path(data, mapping.get("segment"))
    transaction_type = resolve_path(data, mapping.get("transaction_type"))
    
    assert segment == "apartments"
    assert transaction_type == "sale"

def test_rp_signals_extraction():
    data = load_raw_test_file("raw_rp_17812.json")
    mapping = get_mapping("rp", "investment")
    
    segment = resolve_path(data, mapping.get("segment"))
    transaction_type = resolve_path(data, mapping.get("transaction_type"))
    
    assert segment == "apartments"
    assert transaction_type == "sale"

from usi_scrapers import classify_segment

def test_to_signals_extraction():
    data = load_raw_test_file("raw_to_i8975118.json")
    mapping = get_mapping("to", "investment")
    
    segment = resolve_path(data, mapping.get("segment"))
    transaction_type = resolve_path(data, mapping.get("transaction_type"))
    
    assert segment == "apartments"
    assert transaction_type == "sale"

def test_classify_segment_logic():
    # PRS priority
    assert classify_segment({"rental": True}) == "prs"
    assert classify_segment({"rental": "rent"}) == "prs"
    
    # Houses
    assert classify_segment({"houses": 1400}) == "segmenty i domy"
    assert classify_segment({"houses": "10"}) == "segmenty i domy"
    
    # Commercial
    assert classify_segment({"commercial": 5}) == "lokale usługowe"
    
    # Investment units
    assert classify_segment({"investment": ["apartments"]}) == "lokale inwestycyjne"
    assert classify_segment({"investment": "apartamenty-inwestycyjne"}) == "lokale inwestycyjne"
    
    # Residential
    assert classify_segment({"apartments": 100}) == "mieszkania deweloperskie"
    
    # Fallback null
    assert classify_segment({}) is None
    assert classify_segment({"apartments": 0, "houses": 0}) is None
    assert classify_segment(None) is None
