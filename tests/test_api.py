"""Tests for api.py — process_batch_ingest() and ingest_investment_by_url()."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from usi_scrapers.api import process_batch_ingest, process_batch_refresh, ingest_investment_by_url, refresh_investment_by_id

GOOD_INV = {
    "name": "Inwestycja X",
    "developer_slug": "dev-x",
    "investment_slug": "inwestycja-x",
    "latitude": 52.2,
    "longitude": 21.0,
    "image_urls": ["https://cdn/img1.jpg", "https://cdn/img2.jpg"], "raw_details": {},
}

ERROR_429 = {"error": "429 Too Many Requests"}
ERROR_TIMEOUT = {"error": "connection timeout occurred"}
ERROR_OTHER = {"error": "404 Not Found"}


def _make_manager_mock():
    m = MagicMock()
    m.save_raw_data.return_value = Path("/tmp/x.json")
    m.sync_images.return_value = ["img1.jpg", "img2.jpg"]
    return m


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
@patch("time.sleep")
def test_process_batch_ingest_success_rp(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/", "http://rynekpierwotny.pl/oferty/dev/inv-222/"], delay_range=(0, 0))

    assert len(results) == 2
    assert mock_scrape.call_count == 2
    mock_scrape.assert_any_call("111", fetcher)
    mock_scrape.assert_any_call("222", fetcher)
    assert mock_mgr_cls.return_value.save_raw_data.call_count == 2
    # portal_prefix for rp
    mock_mgr_cls.return_value.save_raw_data.assert_any_call(GOOD_INV, "rp")


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_otodom", return_value=GOOD_INV)
@patch("time.sleep")
def test_process_batch_ingest_success_otodom(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch_ingest(config, fetcher, "otodom", ["https://otodom.pl/x"], delay_range=(0, 0))

    assert len(results) == 1
    mock_scrape.assert_called_once_with("https://otodom.pl/x", fetcher)
    mock_mgr_cls.return_value.save_raw_data.assert_called_once_with(GOOD_INV, "oto")


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_tabelaofert", return_value=GOOD_INV)
@patch("time.sleep")
def test_process_batch_ingest_success_tabelaofert(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch_ingest(config, fetcher, "tabelaofert", ["https://tabelaofert.pl/x,i1"], delay_range=(0, 0))

    assert len(results) == 1
    mock_mgr_cls.return_value.save_raw_data.assert_called_once_with(GOOD_INV, "to")


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=[ERROR_429, GOOD_INV])
@patch("time.sleep")
def test_process_batch_ingest_retries_on_429(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/"], delay_range=(0, 0))

    assert mock_scrape.call_count == 2
    mock_sleep.assert_any_call(10)
    assert results[0] == GOOD_INV


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=[ERROR_TIMEOUT, GOOD_INV])
@patch("time.sleep")
def test_process_batch_ingest_retries_on_timeout(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/"], delay_range=(0, 0))

    assert mock_scrape.call_count == 2
    mock_sleep.assert_any_call(10)
    assert results[0] == GOOD_INV


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=ERROR_429)
@patch("time.sleep")
def test_process_batch_ingest_max_retries_exceeded(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/"], max_retries=3, delay_range=(0, 0))

    assert mock_scrape.call_count == 3
    assert mock_sleep.call_args_list.count(call(10)) == 3
    assert mock_mgr_cls.return_value.save_raw_data.call_count == 0


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=ERROR_OTHER)
@patch("time.sleep")
def test_process_batch_ingest_non_429_error_no_retry(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/"], delay_range=(0, 0))

    assert mock_scrape.call_count == 1
    assert not any(c == call(10) for c in mock_sleep.call_args_list)


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
@patch("time.sleep")
def test_process_batch_ingest_progress_callback_called(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()
    progress_calls = []

    process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/", "http://rynekpierwotny.pl/oferty/dev/inv-222/"],
                  on_progress=progress_calls.append, delay_range=(0, 0))

    assert len(progress_calls) == 2
    payload = progress_calls[0]
    assert payload["total"] == 2
    assert payload["current_index"] == 1
    assert payload["progress_percent"] == 50
    assert payload["status"] == "success"
    assert "investment" in payload
    assert "message" in payload
    assert "error_details" in payload
    assert payload["error_details"] is None


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=[ERROR_429, GOOD_INV])
@patch("time.sleep")
def test_process_batch_ingest_retrying_callback(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()
    progress_calls = []

    process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/"],
                  on_progress=progress_calls.append, delay_range=(0, 0))

    statuses = [p["status"] for p in progress_calls]
    assert "retrying" in statuses
    retrying_idx = statuses.index("retrying")
    assert statuses[retrying_idx + 1] == "success"


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
@patch("time.sleep")
def test_process_batch_ingest_no_callback_no_error(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/"], on_progress=None, delay_range=(0, 0))
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Throttling
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
@patch("time.sleep")
@patch("random.uniform", return_value=1.5)
def test_process_batch_ingest_throttle_between_items(mock_uniform, mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    process_batch_ingest(config, fetcher, "rp", ["1", "2", "3"], delay_range=(0.5, 2.0))

    # throttle called N-1 times (not after last item), sleep(10) not in mix
    throttle_calls = [c for c in mock_sleep.call_args_list if c != call(10)]
    assert len(throttle_calls) == 2
    mock_uniform.assert_called_with(0.5, 2.0)


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
@patch("time.sleep")
@patch("random.uniform", return_value=0.0)
def test_process_batch_ingest_custom_delay_range(mock_uniform, mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    process_batch_ingest(config, fetcher, "rp", ["1", "2"], delay_range=(0.0, 0.0))

    mock_uniform.assert_called_with(0.0, 0.0)


# ---------------------------------------------------------------------------
# I/O isolation
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=[GOOD_INV, ERROR_OTHER])
@patch("time.sleep")
def test_process_batch_ingest_saves_immediately_after_each(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr = _make_manager_mock()
    mock_mgr_cls.return_value = mock_mgr

    process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/", "http://rynekpierwotny.pl/oferty/dev/inv-222/"], delay_range=(0, 0))

    # Only the first item succeeded — save_raw_data called exactly once
    assert mock_mgr.save_raw_data.call_count == 1


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny")
@patch("time.sleep")
def test_process_batch_ingest_empty_identifiers(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch_ingest(config, fetcher, "rp", [], delay_range=(0, 0))

    assert results == []
    mock_scrape.assert_not_called()
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=RuntimeError("unexpected crash"))
@patch("time.sleep")
def test_process_batch_ingest_scraper_exception(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()
    progress_calls = []

    process_batch_ingest(config, fetcher, "rp", ["http://rynekpierwotny.pl/oferty/dev/inv-111/"], max_retries=2,
                  on_progress=progress_calls.append, delay_range=(0, 0))

    final = progress_calls[-1]
    assert final["status"] == "failed"
    assert "unexpected crash" in (final["error_details"] or "")
    # sleep(10) called between attempts (not after last attempt)
    # assert call(10) in mock_sleep.call_args_list


# ---------------------------------------------------------------------------
# fetch_investment
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
def test_ingest_investment_by_url_rp_success(mock_scrape, config, fetcher):
    result = ingest_investment_by_url(config, fetcher, "rp", "http://rynekpierwotny.pl/oferty/dev/inv-123/")
    assert result == GOOD_INV
    mock_scrape.assert_called_once_with("123", fetcher)


@patch("usi_scrapers.api.scrape_otodom", return_value=GOOD_INV)
def test_ingest_investment_by_url_otodom(mock_scrape, config, fetcher):
    result = ingest_investment_by_url(config, fetcher, "otodom", "https://otodom.pl/x")
    assert result == GOOD_INV


@patch("usi_scrapers.api.scrape_tabelaofert", return_value=GOOD_INV)
def test_ingest_investment_by_url_tabelaofert(mock_scrape, config, fetcher):
    result = ingest_investment_by_url(config, fetcher, "tabelaofert", "https://tabelaofert.pl/x,i1")
    assert result == GOOD_INV


@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
def test_ingest_investment_by_url_progress_callback_success(mock_scrape, config, fetcher):
    calls = []
    ingest_investment_by_url(config, fetcher, "rp", "http://rynekpierwotny.pl/oferty/dev/inv-123/", on_progress=calls.append)

    assert len(calls) == 1
    p = calls[0]
    assert p["total"] == 1
    assert p["current_index"] == 1
    assert p["progress_percent"] == 100
    assert p["status"] == "success"
    assert p["error_details"] is None


@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value={"error": "blocked"})
def test_ingest_investment_by_url_progress_callback_failure(mock_scrape, config, fetcher):
    calls = []
    ingest_investment_by_url(config, fetcher, "rp", "http://rynekpierwotny.pl/oferty/dev/inv-123/", on_progress=calls.append)

    assert calls[0]["status"] == "failed"
    assert calls[0]["error_details"] == "blocked"


@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=RuntimeError("boom"))
def test_ingest_investment_by_url_exception_returns_error_dict(mock_scrape, config, fetcher):
    result = ingest_investment_by_url(config, fetcher, "rp", "http://rynekpierwotny.pl/oferty/dev/inv-123/")
    assert "error" in result
    assert "boom" in result["error"]


def test_ingest_investment_by_url_unsupported_portal(config, fetcher):
    # ValueError is caught internally and returned as an error dict
    result = ingest_investment_by_url(config, fetcher, "unknown_portal", "http://unknown.com/id")
    assert "error" in result
    assert "Unknown portal alias" in result["error"]

# ---------------------------------------------------------------------------
# get_raw_data and get_raw_dev_data
# ---------------------------------------------------------------------------

@patch("usi_scrapers.storage.get_resolver")
def test_get_raw_data_found(mock_get_resolver, config, tmp_path):
    # Mock the resolver
    mock_resolver = MagicMock()
    mock_resolver.lookup_investment.return_value = ("dev-x", "inv-x")
    mock_get_resolver.return_value = mock_resolver
    
    # Setup filesystem
    config.public_dir = str(tmp_path)
    inv_dir = tmp_path / "USIdata" / "dev-x" / "inv-x"
    inv_dir.mkdir(parents=True)
    raw_file = inv_dir / "raw_rp_123.json"
    raw_file.write_text('{"id": 123, "name": "Test"}')

    from usi_scrapers.api import get_raw_data
    data = get_raw_data(config, "rp", "123")
    assert data is not None
    assert data["name"] == "Test"
    mock_resolver.lookup_investment.assert_called_once_with("rp", "123")

@patch("usi_scrapers.storage.get_resolver")
def test_get_raw_data_not_found(mock_get_resolver, config):
    mock_resolver = MagicMock()
    mock_resolver.lookup_investment.return_value = None
    mock_get_resolver.return_value = mock_resolver

    from usi_scrapers.api import get_raw_data
    assert get_raw_data(config, "rp", "999") is None

@patch("usi_scrapers.storage.get_resolver")
def test_get_raw_dev_data_found(mock_get_resolver, config, tmp_path):
    mock_resolver = MagicMock()
    mock_resolver.lookup_developer.return_value = "dev-x"
    mock_get_resolver.return_value = mock_resolver
    
    config.public_dir = str(tmp_path)
    dev_dir = tmp_path / "USIdev" / "dev-x"
    dev_dir.mkdir(parents=True)
    raw_file = dev_dir / "raw_rp_123.json"
    raw_file.write_text('{"id": 123, "dev": "Test Dev"}')

    from usi_scrapers.api import get_raw_dev_data
    data = get_raw_dev_data(config, "rp", "123")
    assert data is not None
    assert data["dev"] == "Test Dev"
    mock_resolver.lookup_developer.assert_called_once_with("rp", "123")

@patch("usi_scrapers.storage.get_resolver")
def test_resolve_image_path(mock_get_resolver, config):
    mock_resolver = MagicMock()
    mock_resolver.find_image_path.return_value = "/path/to/test_image123.jpg"
    mock_get_resolver.return_value = mock_resolver

    from usi_scrapers.api import resolve_image_path
    result = resolve_image_path("test_image123.jpg", config)
    
    assert result == "/path/to/test_image123.jpg"
    mock_get_resolver.assert_called_once_with(config)
    mock_resolver.find_image_path.assert_called_once_with("test_image123.jpg")

# ── Tests for extract_developer_meta ─────────────────────────────────────────

def test_extract_developer_meta_rp():
    """RP: flat structure — id, slug, name bezpośrednio na najwyższym poziomie."""
    from usi_scrapers.api import extract_developer_meta
    raw = {
        "id": 42,
        "slug": "nowy-dom-deweloper",
        "name": "Nowy Dom Deweloper",
    }
    result = extract_developer_meta(raw, "rp")
    assert result.get("id") == 42
    assert result.get("slug") == "nowy-dom-deweloper"
    assert result.get("name") == "Nowy Dom Deweloper"


def test_extract_developer_meta_oto():
    """Otodom: zagnieżdżona struktura owner.account.attributes.slug z regex -IDxxx."""
    from usi_scrapers.api import extract_developer_meta
    raw = {
        "owner": {
            "id": 999,
            "account": {
                "name": "Otodom Developer Sp. z o.o.",
                "attributes": {
                    "slug": "otodom-developer-ID999"
                }
            }
        }
    }
    result = extract_developer_meta(raw, "otodom")
    assert result.get("id") == 999
    assert result.get("slug") == "otodom-developer"  # regex strips -IDxxx
    assert result.get("name") == "Otodom Developer Sp. z o.o."


def test_extract_developer_meta_to():
    """TabelaOfert: id z regex na logo_url, slug z url, name z name|nazwa."""
    from usi_scrapers.api import extract_developer_meta
    raw = {
        "logo_url": "https://cdn.example.com/logos,12345-/logo.png",
        "url": "https://tabelaofert.pl/deweloperzy/to-developer",
        "name": "TO Developer",
    }
    result = extract_developer_meta(raw, "tabelaofert")
    assert result.get("id") == "12345"
    assert result.get("slug") == "to-developer"
    assert result.get("name") == "TO Developer"


def test_extract_developer_meta_empty_returns_empty_dict():
    """Puste raw_data lub nieznany portal zawsze zwraca {}."""
    from usi_scrapers.api import extract_developer_meta
    assert extract_developer_meta({}, "rp") == {}
    assert extract_developer_meta(None, "rp") == {}
    assert extract_developer_meta({"id": 1}, "nieznany-portal-xyz") == {}

# ── Tests for load_raw and has_local_raw ─────────────────────────────────────

@patch("usi_scrapers.storage.get_resolver")
def test_load_raw_delegates_to_get_raw_data(mock_get_resolver, config, tmp_path):
    """load_raw zwraca ten sam wynik co get_raw_data dla istniejącego pliku."""
    mock_resolver = MagicMock()
    mock_resolver.lookup_investment.return_value = ("dev-x", "inv-x")
    mock_get_resolver.return_value = mock_resolver

    config.public_dir = str(tmp_path)
    inv_dir = tmp_path / "USIdata" / "dev-x" / "inv-x"
    inv_dir.mkdir(parents=True)
    (inv_dir / "raw_rp_123.json").write_text('{"name": "Test"}')

    from usi_scrapers.api import load_raw, get_raw_data
    assert load_raw(config, "rp", "123") == get_raw_data(config, "rp", "123")


@patch("usi_scrapers.storage.get_resolver")
def test_has_local_raw_true(mock_get_resolver, config, tmp_path):
    """has_local_raw zwraca True gdy plik istnieje."""
    mock_resolver = MagicMock()
    mock_resolver.lookup_investment.return_value = ("dev-x", "inv-x")
    mock_get_resolver.return_value = mock_resolver

    config.public_dir = str(tmp_path)
    inv_dir = tmp_path / "USIdata" / "dev-x" / "inv-x"
    inv_dir.mkdir(parents=True)
    (inv_dir / "raw_rp_123.json").touch()

    from usi_scrapers.api import has_local_raw
    assert has_local_raw(config, "rp", "123") is True


@patch("usi_scrapers.storage.get_resolver")
def test_has_local_raw_false_missing_file(mock_get_resolver, config, tmp_path):
    """has_local_raw zwraca False gdy inwestycja nie jest w indeksie."""
    mock_resolver = MagicMock()
    mock_resolver.lookup_investment.return_value = None
    mock_get_resolver.return_value = mock_resolver

    config.public_dir = str(tmp_path)

    from usi_scrapers.api import has_local_raw
    assert has_local_raw(config, "rp", "999") is False


def test_has_local_raw_false_unknown_portal(config):
    """has_local_raw zwraca False dla nieznanego portalu."""
    from usi_scrapers.api import has_local_raw
    assert has_local_raw(config, "nieznany-portal", "123") is False
