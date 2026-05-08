import pytest
from datetime import datetime
from usi_scrapers.adapters import RPAdapter, OtodomAdapter, TOAdapter, Merger

def test_rp_adapter_transform():
    raw_data = {
        "id": 12345,
        "name": "Test RP Investment",
        "vendor": {"name": "Test Developer"},
        "geo_point": {"coordinates": [21.0, 52.0]}, # [lng, lat] in RP
        "construction_date_upper": "2025-12-31T00:00:00",
        "properties": 100,
        "price_m2_range": {"lower": 10000, "upper": 15000, "average": 12500},
        "facilities": [1, 2, 3]
    }
    unified = RPAdapter.transform(raw_data, "test-inv", "test-dev")
    
    assert unified["investment_slug"] == "test-inv"
    assert unified["name"] == "Test RP Investment"
    assert unified["location"]["coords"] == [52.0, 21.0] # [lat, lng] in USI
    assert unified["specifications"]["delivery_quarter"] == 4
    assert unified["specifications"]["delivery_year"] == 2025
    assert unified["sources"]["rp"]["id"] == "12345"
    assert unified["financials"]["price_m2_min"] == 10000
    assert unified["financials"]["price_m2_max"] == 15000
    assert unified["financials"]["price_avg"] == 12500

def test_otodom_adapter_transform():
    raw_data = {
        "id": 67890,
        "title": "Test Otodom Investment",
        "agency": {"name": "Test Agency"},
        "url": "https://otodom.pl/test",
        "location": {
            "coordinates": {"latitude": 52.1, "longitude": 21.1},
            "address": {"street": {"name": "Testowa"}, "city": {"name": "Warszawa"}}
        },
        "investmentEstimatedDelivery": {"quarter": "Q1", "year": 2026},
        "characteristics": [
            {"key": "number_of_properties", "value": "50"},
            {"key": "price_per_m_from", "value": "11000"}
        ]
    }
    unified = OtodomAdapter.transform(raw_data, "test-inv", "test-dev")
    
    assert unified["name"] == "Test Otodom Investment"
    assert unified["location"]["coords"] == [52.1, 21.1]
    assert unified["specifications"]["units_count"] == 50
    assert unified["sources"]["oto"]["id"] == "67890"
    assert unified["financials"]["price_m2_min"] == 11000

def test_to_adapter_transform():
    raw_data = {
        "name": "Test TO Investment",
        "brand": {"name": "Test TO Brand"},
        "offers": {
            "offerCount": 30,
            "lowPrice": "500000.00",
            "highPrice": "800000.00",
            "offers": [{
                "itemOffered": {
                    "geo": {"latitude": "52.2", "longitude": "21.2"},
                    "address": {"streetAddress": "Polna 1", "addressLocality": "Kraków"}
                }
            }]
        },
        "additionalProperty": [
            {"name": "Termin oddania", "value": "II kwartał 2024"}
        ]
    }
    unified = TOAdapter.transform(raw_data, "test-inv", "test-dev")
    
    assert unified["name"] == "Test TO Investment"
    assert unified["location"]["coords"] == [52.2, 21.2]
    assert unified["specifications"]["delivery_quarter"] == 2
    assert unified["specifications"]["delivery_year"] == 2024
    assert unified["financials"]["price_min"] == 500000.0

def test_merger_merge_all():
    rp_data = {"name": "RP Name", "location": {"coords": [None, None]}, "amenities": {"labels": ["A"]}, "sources": {"rp": {"id": "1"}}}
    oto_data = {"name": "Oto Name", "location": {"coords": [52.0, 21.0]}, "amenities": {"labels": ["B"]}, "sources": {"oto": {"id": "2"}}}
    to_data = {"name": "TO Name", "location": {"coords": [52.1, 21.1]}, "amenities": {"labels": ["C"]}, "sources": {"to": {"id": "3"}}}
    
    merged = Merger.merge(rp_data, oto_data, to_data)
    
    assert merged["name"] == "RP Name" # RP priority
    assert merged["location"]["coords"] == [52.0, 21.0] # Taken from Otodom as RP has None
    assert set(merged["amenities"]["labels"]) == {"A", "B", "C"}
    assert "rp" in merged["sources"]
    assert "oto" in merged["sources"]
    assert "to" in merged["sources"]

def test_merger_priority():
    oto_data = {"name": "Oto Name", "developer": "Oto Dev", "sources": {"oto": {"id": "oto1"}}}
    to_data = {"name": "TO Name", "developer": "TO Dev", "sources": {"to": {"id": "to1"}}}
    
    merged = Merger.merge(rp_data=None, oto_data=oto_data, to_data=to_data)
    assert merged["name"] == "Oto Name"
    assert merged["developer"] == "Oto Dev"
    
    merged_to_only = Merger.merge(rp_data=None, oto_data=None, to_data=to_data)
    assert merged_to_only["name"] == "TO Name"

def test_merger_audit_history_creation():
    existing = {
        "investment_slug": "test",
        "name": "Test",
        "financials": {"price_avg": 10000},
        "audit": {"created_at": "2024-01-01T00:00:00", "history": []},
        "sources": {"rp": {"id": "1"}}
    }
    new_data = {
        "financials": {"price_avg": 12000},
        "sources": {"rp": {"id": "1"}}
    }
    
    merged = Merger.merge(rp_data=new_data, existing_data=existing, event="Test Event")
    
    assert merged["audit"]["created_at"] == "2024-01-01T00:00:00"
    assert len(merged["audit"]["history"]) == 1
    assert merged["audit"]["history"][0]["event"] == "Test Event"
    assert merged["audit"]["history"][0]["changes"][0]["field"] == "financials.price_avg"
    assert merged["audit"]["history"][0]["changes"][0]["old"] == 10000
    assert merged["audit"]["history"][0]["changes"][0]["new"] == 12000

def test_merger_no_changes_no_log_unless_event():
    existing = {
        "investment_slug": "test",
        "financials": {"price_avg": 10000},
        "status": "Brak",
        "images_count": 0,
        "audit": {"history": []},
        "sources": {"rp": {"id": "1"}}
    }
    new_data = {
        "financials": {"price_avg": 10000},
        "status": "Brak",
        "images_count": 0,
        "sources": {"rp": {"id": "1"}}
    }
    
    # No changes, no event -> no log
    merged = Merger.merge(rp_data=new_data, existing_data=existing)
    assert len(merged["audit"]["history"]) == 0
    
    # No changes, but event passed -> should log
    merged_with_event = Merger.merge(rp_data=new_data, existing_data=existing, event="Sync Completed")
    assert len(merged_with_event["audit"]["history"]) == 1
    assert merged_with_event["audit"]["history"][0]["event"] == "Sync Completed"
    assert len(merged_with_event["audit"]["history"][0]["changes"]) == 0
