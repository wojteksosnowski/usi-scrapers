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

def test_find_image_path(temp_public_dir):
    config = ScraperConfig(public_dir=str(temp_public_dir))
    resolver = StorageResolver(config)
    
    # Create a test image file
    img_dir = temp_public_dir / "USIdata" / "test-dev" / "test-inv"
    img_dir.mkdir(parents=True, exist_ok=True)
    img_path = img_dir / "test_image123.jpg"
    img_path.touch()
    
    # Should find the image
    found_path = resolver.find_image_path("test_image123.jpg")
    assert found_path == str(img_path)
    
    # Should not find non-existent image
    not_found = resolver.find_image_path("nonexistent.jpg")
    assert not_found is None


# ── OTO dual-ID support tests ─────────────────────────────────────────────────

import json

@pytest.fixture
def oto_dual_id_dir(tmp_path):
    """Tworzy strukturę z plikiem raw_oto_{alphanum}.json zawierającym ad.id (numeryczny)."""
    inv_dir = tmp_path / "USIdata" / "test-dev" / "test-inv"
    inv_dir.mkdir(parents=True)
    raw = {"ad": {"id": 65110911, "features": ["Balkon"]}}
    (inv_dir / "raw_oto_4pcjZ.json").write_text(json.dumps(raw), encoding="utf-8")

    dev_dir = tmp_path / "USIdev" / "test-dev"
    dev_dir.mkdir(parents=True)
    dev_raw = {"id": 9867181, "name": "Test Dev"}
    (dev_dir / "raw_oto_4pcjZ.json").write_text(json.dumps(dev_raw), encoding="utf-8")

    return tmp_path


def test_oto_lookup_investment_by_alphanum(oto_dual_id_dir):
    """Lookup po alfanumerycznym ID (kanoniczny) działa jak dotychczas."""
    config = ScraperConfig(public_dir=str(oto_dual_id_dir))
    resolver = StorageResolver(config)
    result = resolver.lookup_investment("oto", "4pcjZ")
    assert result == ("test-dev", "test-inv")


def test_oto_lookup_investment_by_numeric(oto_dual_id_dir):
    """Lookup po numerycznym ad.id zwraca ten sam wynik co alfanumeryczny."""
    config = ScraperConfig(public_dir=str(oto_dual_id_dir))
    resolver = StorageResolver(config)
    result = resolver.lookup_investment("oto", "65110911")
    assert result == ("test-dev", "test-inv")


def test_oto_resolve_canonical_inv_id(oto_dual_id_dir):
    """resolve_oto_inv_canonical_id zwraca alfanumeryczny ID dla numerycznego."""
    config = ScraperConfig(public_dir=str(oto_dual_id_dir))
    resolver = StorageResolver(config)
    assert resolver.resolve_oto_inv_canonical_id("65110911") == "4pcjZ"
    # Alfanumeryczny ID pozostaje niezmieniony
    assert resolver.resolve_oto_inv_canonical_id("4pcjZ") == "4pcjZ"


def test_oto_lookup_developer_by_numeric(oto_dual_id_dir):
    """Lookup dewelopera po numerycznym id (z pliku raw OTO) działa poprawnie."""
    config = ScraperConfig(public_dir=str(oto_dual_id_dir))
    resolver = StorageResolver(config)
    assert resolver.lookup_developer("oto", "9867181") == "test-dev"
    assert resolver.lookup_developer("oto", "4pcjZ") == "test-dev"


def test_has_local_raw_oto_numeric(oto_dual_id_dir):
    """has_local_raw akceptuje numeryczny OTO ID i zwraca True gdy plik istnieje."""
    from usi_scrapers.api import has_local_raw
    from usi_scrapers import storage as _storage
    _storage._default_resolver = None

    config = ScraperConfig(public_dir=str(oto_dual_id_dir))

    assert has_local_raw(config, "oto", "65110911") is True
    assert has_local_raw(config, "oto", "4pcjZ") is True
    assert has_local_raw(config, "oto", "9999999") is False

    _storage._default_resolver = None  # cleanup


def test_load_raw_oto_numeric(oto_dual_id_dir):
    """load_raw wczytuje plik raw_oto_4pcjZ.json gdy zapytany z numerycznym ID."""
    from usi_scrapers.api import load_raw
    from usi_scrapers import storage as _storage
    _storage._default_resolver = None

    config = ScraperConfig(public_dir=str(oto_dual_id_dir))

    # Zapytanie po numerycznym ID
    data_numeric = load_raw(config, "oto", "65110911")
    # Zapytanie po alfanumerycznym ID
    data_alphanum = load_raw(config, "oto", "4pcjZ")

    assert data_numeric is not None
    assert data_alphanum is not None
    # Oba powinny zwrócić ten sam JSON
    assert data_numeric == data_alphanum
    assert data_numeric["ad"]["id"] == 65110911

    _storage._default_resolver = None  # cleanup
