import pytest
import warnings
from unittest.mock import MagicMock, patch
from usi_scrapers.api import health_check, verify_consistency

def test_health_check_no_args():
    """Weryfikuje, że health_check można wywołać bez argumentów."""
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[]), \
         patch("usi_scrapers.api.discover_otodom_investments", return_value=[]), \
         patch("usi_scrapers.api.discover_to_listing", return_value=[]):
        
        # Wywołanie bez config i fetcher
        res = health_check(portals=["rp"])
        assert "ok" in res
        assert "portals" in res
        assert "rp" in res["portals"]

def test_verify_consistency_alias_and_warning():
    """Weryfikuje alias verify_consistency oraz emisję ostrzeżenia o deprecacji."""
    with patch("usi_scrapers.api.health_check", return_value={"ok": True}):
        with pytest.warns(DeprecationWarning, match=r"verify_consistency\(\) jest przestarzałe"):
            res = verify_consistency(portals=["rp"])
            assert res["ok"] is True

def test_health_check_auto_initialization():
    """Weryfikuje, czy parametry są automatycznie inicjowane, gdy ich brak."""
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[]) as mock_disc:
        health_check(portals=["rp"])
        # Sprawdzamy, czy do discovery przekazano obiekty config i fetcher
        # Wywołanie: discover_rp_investments(config, fetcher, None, limit=1)
        args, _ = mock_disc.call_args
        assert args[0].__class__.__name__ == "ScraperConfig"
        assert args[1].__class__.__name__ == "Fetcher"
