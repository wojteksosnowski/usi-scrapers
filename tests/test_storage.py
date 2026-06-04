import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from usi_scrapers.models import ScraperConfig
from usi_scrapers.storage import StorageResolver, get_resolver

@pytest.fixture
def temp_public_dir(tmp_path):
    # Create USIdev and USIdata structure
    dev_dir = tmp_path / "USIdev" / "test-dev"
    dev_dir.mkdir(parents=True)
    (dev_dir / "raw_rp_123.json").touch()
    
    inv_dir = tmp_path / "USIdata" / "test-dev" / "test-inv"
    inv_dir.mkdir(parents=True)
    (inv_dir / "raw_rp_456.json").touch()
    
    return tmp_path

def test_storage_resolver_build_index(temp_public_dir):
    config = ScraperConfig(public_dir=str(temp_public_dir))
    resolver = StorageResolver(config)
    
    resolver.build_index()
    
    # Check dev cache
    assert resolver.lookup_developer("rp", "123") == "test-dev"
    assert resolver.lookup_developer("rp", "999") is None
    
    # Check inv cache
    assert resolver.lookup_investment("rp", "456") == ("test-dev", "test-inv")
    assert resolver.lookup_investment("rp", "999") is None

def test_storage_resolver_update_index(temp_public_dir):
    config = ScraperConfig(public_dir=str(temp_public_dir))
    resolver = StorageResolver(config)
    resolver.build_index()
    
    resolver.update_developer_index("oto", "777", "new-dev")
    assert resolver.lookup_developer("oto", "777") == "new-dev"
    
    resolver.update_investment_index("oto", "888", "new-dev", "new-inv")
    assert resolver.lookup_investment("oto", "888") == ("new-dev", "new-inv")

def test_get_resolver_singleton(temp_public_dir):
    config1 = ScraperConfig(public_dir=str(temp_public_dir))
    config2 = ScraperConfig(public_dir=str(temp_public_dir))
    
    resolver1 = get_resolver(config1)
    resolver2 = get_resolver(config2)
    
    assert resolver1 is resolver2
