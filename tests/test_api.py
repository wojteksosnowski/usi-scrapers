"""Tests for api.py — process_batch() and fetch_investment()."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from usi_scrapers.api import process_batch, fetch_investment

GOOD_INV = {
    "name": "Inwestycja X",
    "developer_slug": "dev-x",
    "investment_slug": "inwestycja-x",
    "latitude": 52.2,
    "longitude": 21.0,
    "image_urls": ["https://cdn/img1.jpg", "https://cdn/img2.jpg"],
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
def test_process_batch_success_rp(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch(config, fetcher, "rp", ["111", "222"], delay_range=(0, 0))

    assert len(results) == 2
    assert mock_scrape.call_count == 2
    mock_scrape.assert_any_call("111", fetcher)
    mock_scrape.assert_any_call("222", fetcher)
    assert mock_mgr_cls.return_value.save_raw_data.call_count == 2
    # portal_prefix for rp
    mock_mgr_cls.return_value.save_raw_data.assert_called_with(GOOD_INV, Path(config.public_dir) / "USIdata" / "dev-x" / "inwestycja-x", "rp")


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_otodom", return_value=GOOD_INV)
@patch("time.sleep")
def test_process_batch_success_otodom(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch(config, fetcher, "otodom", ["https://otodom.pl/x"], delay_range=(0, 0))

    assert len(results) == 1
    mock_scrape.assert_called_once_with("https://otodom.pl/x", fetcher)
    # portal_prefix for otodom -> "oto"
    mock_mgr_cls.return_value.save_raw_data.assert_called_once_with(GOOD_INV, Path(config.public_dir) / "USIdata" / "dev-x" / "inwestycja-x", "oto")


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_tabelaofert", return_value=GOOD_INV)
@patch("time.sleep")
def test_process_batch_success_tabelaofert(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch(config, fetcher, "tabelaofert", ["https://tabelaofert.pl/x,i1"], delay_range=(0, 0))

    assert len(results) == 1
    # portal_prefix for tabelaofert -> "to"
    mock_mgr_cls.return_value.save_raw_data.assert_called_once_with(GOOD_INV, Path(config.public_dir) / "USIdata" / "dev-x" / "inwestycja-x", "to")


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=[ERROR_429, GOOD_INV])
@patch("time.sleep")
def test_process_batch_retries_on_429(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch(config, fetcher, "rp", ["111"], delay_range=(0, 0))

    assert mock_scrape.call_count == 2
    mock_sleep.assert_any_call(10)
    assert results[0] == GOOD_INV


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=[ERROR_TIMEOUT, GOOD_INV])
@patch("time.sleep")
def test_process_batch_retries_on_timeout(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch(config, fetcher, "rp", ["111"], delay_range=(0, 0))

    assert mock_scrape.call_count == 2
    mock_sleep.assert_any_call(10)
    assert results[0] == GOOD_INV


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=ERROR_429)
@patch("time.sleep")
def test_process_batch_max_retries_exceeded(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch(config, fetcher, "rp", ["111"], max_retries=3, delay_range=(0, 0))

    assert mock_scrape.call_count == 3
    assert mock_sleep.call_args_list.count(call(10)) == 3
    assert mock_mgr_cls.return_value.save_raw_data.call_count == 0


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=ERROR_OTHER)
@patch("time.sleep")
def test_process_batch_non_429_error_no_retry(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch(config, fetcher, "rp", ["111"], delay_range=(0, 0))

    assert mock_scrape.call_count == 1
    assert not any(c == call(10) for c in mock_sleep.call_args_list)


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
@patch("time.sleep")
def test_process_batch_progress_callback_called(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()
    progress_calls = []

    process_batch(config, fetcher, "rp", ["111", "222"],
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
def test_process_batch_retrying_callback(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()
    progress_calls = []

    process_batch(config, fetcher, "rp", ["111"],
                  on_progress=progress_calls.append, delay_range=(0, 0))

    statuses = [p["status"] for p in progress_calls]
    assert "retrying" in statuses
    retrying_idx = statuses.index("retrying")
    assert statuses[retrying_idx + 1] == "success"


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
@patch("time.sleep")
def test_process_batch_no_callback_no_error(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch(config, fetcher, "rp", ["111"], on_progress=None, delay_range=(0, 0))
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Throttling
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
@patch("time.sleep")
@patch("random.uniform", return_value=1.5)
def test_process_batch_throttle_between_items(mock_uniform, mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    process_batch(config, fetcher, "rp", ["1", "2", "3"], delay_range=(0.5, 2.0))

    # throttle called N-1 times (not after last item), sleep(10) not in mix
    throttle_calls = [c for c in mock_sleep.call_args_list if c != call(10)]
    assert len(throttle_calls) == 2
    mock_uniform.assert_called_with(0.5, 2.0)


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
@patch("time.sleep")
@patch("random.uniform", return_value=0.0)
def test_process_batch_custom_delay_range(mock_uniform, mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    process_batch(config, fetcher, "rp", ["1", "2"], delay_range=(0.0, 0.0))

    mock_uniform.assert_called_with(0.0, 0.0)


# ---------------------------------------------------------------------------
# I/O isolation
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=[GOOD_INV, ERROR_OTHER])
@patch("time.sleep")
def test_process_batch_saves_immediately_after_each(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr = _make_manager_mock()
    mock_mgr_cls.return_value = mock_mgr

    process_batch(config, fetcher, "rp", ["111", "222"], delay_range=(0, 0))

    # Only the first item succeeded — save_raw_data called exactly once
    assert mock_mgr.save_raw_data.call_count == 1


@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny")
@patch("time.sleep")
def test_process_batch_empty_identifiers(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()

    results = process_batch(config, fetcher, "rp", [], delay_range=(0, 0))

    assert results == []
    mock_scrape.assert_not_called()
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.TechnicalDataManager")
@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=RuntimeError("unexpected crash"))
@patch("time.sleep")
def test_process_batch_scraper_exception(mock_sleep, mock_scrape, mock_mgr_cls, config, fetcher):
    mock_mgr_cls.return_value = _make_manager_mock()
    progress_calls = []

    process_batch(config, fetcher, "rp", ["111"], max_retries=2,
                  on_progress=progress_calls.append, delay_range=(0, 0))

    final = progress_calls[-1]
    assert final["status"] == "failed"
    assert "unexpected crash" in (final["error_details"] or "")
    # sleep(10) called between attempts (not after last attempt)
    assert call(10) in mock_sleep.call_args_list


# ---------------------------------------------------------------------------
# fetch_investment
# ---------------------------------------------------------------------------

@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
def test_fetch_investment_rp_success(mock_scrape, config, fetcher):
    result = fetch_investment(config, fetcher, "rp", "123")
    assert result == GOOD_INV
    mock_scrape.assert_called_once_with("123", fetcher)


@patch("usi_scrapers.api.scrape_otodom", return_value=GOOD_INV)
def test_fetch_investment_otodom(mock_scrape, config, fetcher):
    result = fetch_investment(config, fetcher, "otodom", "https://otodom.pl/x")
    assert result == GOOD_INV


@patch("usi_scrapers.api.scrape_tabelaofert", return_value=GOOD_INV)
def test_fetch_investment_tabelaofert(mock_scrape, config, fetcher):
    result = fetch_investment(config, fetcher, "tabelaofert", "https://tabelaofert.pl/x,i1")
    assert result == GOOD_INV


@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value=GOOD_INV)
def test_fetch_investment_progress_callback_success(mock_scrape, config, fetcher):
    calls = []
    fetch_investment(config, fetcher, "rp", "123", on_progress=calls.append)

    assert len(calls) == 1
    p = calls[0]
    assert p["total"] == 1
    assert p["current_index"] == 1
    assert p["progress_percent"] == 100
    assert p["status"] == "success"
    assert p["error_details"] is None


@patch("usi_scrapers.api.scrape_rynek_pierwotny", return_value={"error": "blocked"})
def test_fetch_investment_progress_callback_failure(mock_scrape, config, fetcher):
    calls = []
    fetch_investment(config, fetcher, "rp", "123", on_progress=calls.append)

    assert calls[0]["status"] == "failed"
    assert calls[0]["error_details"] == "blocked"


@patch("usi_scrapers.api.scrape_rynek_pierwotny", side_effect=RuntimeError("boom"))
def test_fetch_investment_exception_returns_error_dict(mock_scrape, config, fetcher):
    result = fetch_investment(config, fetcher, "rp", "123")
    assert "error" in result
    assert "boom" in result["error"]


def test_fetch_investment_unsupported_portal(config, fetcher):
    # ValueError is caught internally and returned as an error dict
    result = fetch_investment(config, fetcher, "unknown_portal", "id")
    assert "error" in result
    assert "Unknown portal alias" in result["error"]

