import pytest
from usi_scrapers.utils.integrity import normalize_to_legacy_props
from usi_scrapers.mapping import transform_to_unified

def test_normalize_to_legacy_props_oto():
    # Full __NEXT_DATA__ structure
    full_data = {
        "props": {
            "pageProps": {
                "ad": {"id": 123},
                "data": "some_data"
            }
        },
        "query": {}
    }
    normalized = normalize_to_legacy_props(full_data, "oto")
    assert normalized == {"ad": {"id": 123}, "data": "some_data"}
    
    # Already legacy format
    legacy_data = {"ad": {"id": 456}}
    assert normalize_to_legacy_props(legacy_data, "oto") == legacy_data

def test_normalize_to_legacy_props_rp():
    # RP should be passed through for now
    data = {"vendor": {"id": 1}}
    assert normalize_to_legacy_props(data, "rp") == data

def test_transform_to_unified_with_adapter_oto():
    import usi_scrapers.mapping
    original_get_mapping = usi_scrapers.mapping.get_mapping
    
    def fake_get_mapping(portal, entity):
        if portal == "oto":
            return {"ad_id": {"path": "ad.id"}}
        return {}
        
    usi_scrapers.mapping.get_mapping = fake_get_mapping
    
    try:
        # Full data
        full_data = {
            "props": {
                "pageProps": {
                    "ad": {"id": 123}
                }
            }
        }
        unified = transform_to_unified("oto", full_data)
        assert unified.get("ad_id") == 123
        
        # Legacy data
        legacy_data = {"ad": {"id": 456}}
        unified_legacy = transform_to_unified("oto", legacy_data)
        assert unified_legacy.get("ad_id") == 456
    finally:
        usi_scrapers.mapping.get_mapping = original_get_mapping
