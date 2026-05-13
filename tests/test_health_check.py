import pytest
import warnings
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from usi_scrapers.api import health_check, verify_consistency, _check_fields

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

RP_ITEM = {"id": "123", "url": "https://rynekpierwotny.pl/oferty/dev/x-123/", "slug": "x"}
OTO_ITEM = {"id": "456", "url": "https://www.otodom.pl/pl/oferta/x", "slug": "x"}
TO_ITEM = {"id": "789", "url": "https://tabelaofert.pl/inwestycja/x,i789", "slug": "x"}

RP_DATA = {"name": "X", "latitude": 52.2, "longitude": 21.0, "image_urls": ["u"]}
OTO_DATA = {"title": "X", "latitude": 52.2, "longitude": 21.0, "image_urls": ["u"]}
TO_DATA = {"name": "X", "latitude": 52.2, "longitude": 21.0, "image_urls": ["u"]}

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
        args, _ = mock_disc.call_args
        assert args[0].__class__.__name__ == "ScraperConfig"
        assert args[1].__class__.__name__ == "Fetcher"


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_health_check_return_keys():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[]):
        res = health_check(portals=["rp"])
    assert set(res.keys()) >= {"ok", "portals", "checked_at"}


def test_health_check_checked_at_is_iso_utc():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[]):
        res = health_check(portals=["rp"])
    dt = datetime.fromisoformat(res["checked_at"])
    assert dt.tzinfo is not None


def test_health_check_per_portal_keys():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[]):
        res = health_check(portals=["rp"])
    entry = res["portals"]["rp"]
    assert set(entry.keys()) >= {"ok", "discovery_count", "scrape_url", "scrape_fields_ok", "scrape_fields_missing", "error"}


# ---------------------------------------------------------------------------
# Portal filter
# ---------------------------------------------------------------------------

def test_health_check_portals_filter():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[]) as mock_rp, \
         patch("usi_scrapers.api.discover_otodom_investments") as mock_oto, \
         patch("usi_scrapers.api.discover_to_listing") as mock_to:
        health_check(portals=["rp"])
    mock_rp.assert_called_once()
    mock_oto.assert_not_called()
    mock_to.assert_not_called()


def test_health_check_portals_defaults_to_all_three():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[]) as mock_rp, \
         patch("usi_scrapers.api.discover_otodom_investments", return_value=[]) as mock_oto, \
         patch("usi_scrapers.api.discover_to_listing", return_value=[]) as mock_to:
        res = health_check()
    assert set(res["portals"].keys()) == {"rp", "otodom", "tabelaofert"}
    mock_rp.assert_called_once()
    mock_oto.assert_called_once()
    mock_to.assert_called_once()


# ---------------------------------------------------------------------------
# Success scenarios
# ---------------------------------------------------------------------------

def test_health_check_all_portals_ok():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[RP_ITEM]), \
         patch("usi_scrapers.api.discover_otodom_investments", return_value=[OTO_ITEM]), \
         patch("usi_scrapers.api.discover_to_listing", return_value=[TO_ITEM]), \
         patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=RP_DATA), \
         patch("usi_scrapers.api.scrape_otodom", return_value=OTO_DATA), \
         patch("usi_scrapers.api.scrape_tabelaofert", return_value=TO_DATA):
        res = health_check()

    assert res["ok"] is True
    for portal_entry in res["portals"].values():
        assert portal_entry["ok"] is True
        assert portal_entry["scrape_fields_missing"] == []
        assert portal_entry["error"] is None


def test_health_check_rp_scrape_fields_ok():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[RP_ITEM]), \
         patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=RP_DATA):
        res = health_check(portals=["rp"])
    entry = res["portals"]["rp"]
    assert entry["ok"] is True
    assert entry["discovery_count"] == 1
    assert entry["scrape_url"] == RP_ITEM["url"]


def test_health_check_otodom_uses_title_field():
    """Otodom wymaga pola 'title', nie 'name'."""
    with patch("usi_scrapers.api.discover_otodom_investments", return_value=[OTO_ITEM]), \
         patch("usi_scrapers.api.scrape_otodom", return_value=OTO_DATA):
        res = health_check(portals=["otodom"])
    assert res["portals"]["otodom"]["ok"] is True


# ---------------------------------------------------------------------------
# Discovery failures
# ---------------------------------------------------------------------------

def test_health_check_discovery_returns_empty():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[]), \
         patch("usi_scrapers.api.scrape_rynek_pierwotny") as mock_scrape:
        res = health_check(portals=["rp"])
    assert res["portals"]["rp"]["ok"] is False
    assert res["portals"]["rp"]["error"] is not None
    mock_scrape.assert_not_called()


def test_health_check_discovery_exception():
    with patch("usi_scrapers.api.discover_rp_investments", side_effect=RuntimeError("network down")):
        res = health_check(portals=["rp"])
    entry = res["portals"]["rp"]
    assert entry["ok"] is False
    assert "network down" in entry["error"]


# ---------------------------------------------------------------------------
# Scrape failures
# ---------------------------------------------------------------------------

def test_health_check_scrape_returns_error():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[RP_ITEM]), \
         patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value={"error": "blocked by portal"}):
        res = health_check(portals=["rp"])
    entry = res["portals"]["rp"]
    assert entry["ok"] is False
    assert "blocked by portal" in entry["error"]


def test_health_check_scrape_exception():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[RP_ITEM]), \
         patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=ConnectionError("timeout")):
        res = health_check(portals=["rp"])
    entry = res["portals"]["rp"]
    assert entry["ok"] is False
    assert "timeout" in entry["error"]


def test_health_check_scrape_missing_field():
    data = dict(RP_DATA)
    del data["latitude"]
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[RP_ITEM]), \
         patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=data):
        res = health_check(portals=["rp"])
    entry = res["portals"]["rp"]
    assert entry["ok"] is False
    assert "latitude" in entry["scrape_fields_missing"]


def test_health_check_scrape_empty_image_urls():
    data = dict(RP_DATA, image_urls=[])
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[RP_ITEM]), \
         patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=data):
        res = health_check(portals=["rp"])
    assert "image_urls" in res["portals"]["rp"]["scrape_fields_missing"]


# ---------------------------------------------------------------------------
# Global ok flag
# ---------------------------------------------------------------------------

def test_health_check_global_ok_false_if_any_portal_fails():
    with patch("usi_scrapers.api.discover_rp_investments", return_value=[RP_ITEM]), \
         patch("usi_scrapers.api.discover_otodom_investments", return_value=[OTO_ITEM]), \
         patch("usi_scrapers.api.discover_to_listing", return_value=[]):  # TO fails
        with patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=RP_DATA), \
             patch("usi_scrapers.api.scrape_otodom", return_value=OTO_DATA):
            res = health_check()

    assert res["ok"] is False
    assert res["portals"]["rp"]["ok"] is True
    assert res["portals"]["otodom"]["ok"] is True
    assert res["portals"]["tabelaofert"]["ok"] is False


# ---------------------------------------------------------------------------
# _check_fields unit tests
# ---------------------------------------------------------------------------

def test_check_fields_all_present():
    ok, missing = _check_fields(RP_DATA, "rp")
    assert missing == []
    assert set(ok) == {"name", "latitude", "longitude", "image_urls"}


def test_check_fields_none_value():
    data = dict(RP_DATA, latitude=None)
    _, missing = _check_fields(data, "rp")
    assert "latitude" in missing


def test_check_fields_empty_list():
    data = dict(RP_DATA, image_urls=[])
    _, missing = _check_fields(data, "rp")
    assert "image_urls" in missing


def test_check_fields_empty_string():
    data = dict(RP_DATA, name="")
    _, missing = _check_fields(data, "rp")
    assert "name" in missing


def test_check_fields_rp_uses_name_not_title():
    data = {"title": "X", "latitude": 52.2, "longitude": 21.0, "image_urls": ["u"]}
    _, missing = _check_fields(data, "rp")
    assert "name" in missing


def test_check_fields_otodom_uses_title_not_name():
    data = {"name": "X", "latitude": 52.2, "longitude": 21.0, "image_urls": ["u"]}
    _, missing = _check_fields(data, "otodom")
    assert "title" in missing
