import pytest
import time
from unittest.mock import patch, MagicMock
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher


@pytest.fixture
def test_config(tmp_path):
    return ScraperConfig(
        public_dir=tmp_path,
        scraperapi_key="test_key",
        fetch_delays={"example.com": 0.1, "default": 0.0}
    )


def test_fetcher_rate_limiting(test_config):
    fetcher = Fetcher(test_config)

    fetcher._apply_rate_limit("example.com")
    start = time.time()
    fetcher._apply_rate_limit("example.com")
    assert time.time() - start >= 0.1


@patch('usi_scrapers.fetcher.curl_requests.Session.get')
def test_fetcher_impersonate_success(mock_get, test_config):
    mock_response = MagicMock()
    mock_response.text = "<html>test</html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    fetcher = Fetcher(test_config)
    content = fetcher.fetch("https://example.com", use_scraperapi=False)

    assert content == "<html>test</html>"
    mock_get.assert_called_once()


@patch('usi_scrapers.fetcher.std_requests.get')
@patch('usi_scrapers.fetcher.curl_requests.Session.get')
def test_fetcher_scraperapi_fallback(mock_curl_get, mock_std_get, test_config):
    mock_curl_get.side_effect = Exception("Curl failed")

    # First std_requests call is _get_credits_left (account endpoint),
    # second is the actual ScraperAPI fetch.
    account_response = MagicMock()
    account_response.json.return_value = {"creditsLeft": 500, "requestLimit": 1000}
    account_response.raise_for_status = MagicMock()

    fetch_response = MagicMock()
    fetch_response.text = "<html>scraperapi</html>"
    fetch_response.raise_for_status = MagicMock()

    mock_std_get.side_effect = [account_response, fetch_response]

    fetcher = Fetcher(test_config)
    content = fetcher.fetch("https://example.com")

    assert content == "<html>scraperapi</html>"
    assert mock_std_get.call_count == 2


@patch('usi_scrapers.fetcher.std_requests.get')
@patch('usi_scrapers.fetcher.curl_requests.Session.get')
def test_fetcher_scraperapi_skipped_when_no_credits(mock_curl_get, mock_std_get, test_config):
    mock_curl_get.side_effect = Exception("Curl failed")

    account_response = MagicMock()
    account_response.json.return_value = {"creditsLeft": 0, "requestLimit": 1000}
    account_response.raise_for_status = MagicMock()
    mock_std_get.return_value = account_response

    fetcher = Fetcher(test_config)
    content = fetcher.fetch("https://example.com")

    assert content is None
    assert mock_std_get.call_count == 1  # only account check, no actual fetch


class _HttpError(Exception):
    def __init__(self, status, headers=None):
        super().__init__(f"HTTP {status}")
        self.response = MagicMock(status_code=status, headers=headers or {})


@patch('usi_scrapers.fetcher.std_requests.get')
@patch('usi_scrapers.fetcher.curl_requests.Session.get')
def test_fetcher_404_does_not_use_scraperapi(mock_curl_get, mock_std_get, test_config):
    mock_curl_get.side_effect = _HttpError(404)

    fetcher = Fetcher(test_config)
    assert fetcher.fetch("https://example.com/gone") is None
    assert fetcher.last_status == 404
    mock_std_get.assert_not_called()


@patch('usi_scrapers.fetcher.time.sleep')
@patch('usi_scrapers.fetcher.std_requests.get')
@patch('usi_scrapers.fetcher.curl_requests.Session.get')
def test_fetcher_429_sets_cooldown_and_still_falls_back(mock_curl_get, mock_std_get, mock_sleep, test_config):
    mock_curl_get.side_effect = _HttpError(429, {"Retry-After": "45"})
    account = MagicMock()
    account.json.return_value = {"creditsLeft": 500, "requestLimit": 1000}
    page = MagicMock(text="<html>ok</html>")
    mock_std_get.side_effect = [account, page]

    fetcher = Fetcher(test_config)
    assert fetcher.fetch("https://example.com/x") == "<html>ok</html>"
    until, pause = fetcher._cooldowns["example.com"]
    assert pause == 45.0

    # kolejne żądanie bezpośrednie czeka na koniec przerwy
    mock_curl_get.side_effect = None
    mock_curl_get.return_value = MagicMock(text="fine")
    fetcher.fetch("https://example.com/y", use_scraperapi=False)
    assert any(c.args[0] > 1 for c in mock_sleep.call_args_list)
    assert "example.com" not in fetcher._cooldowns


@patch('usi_scrapers.fetcher.std_requests.get')
@patch('usi_scrapers.fetcher.curl_requests.Session.get')
def test_fetcher_credits_cached(mock_curl_get, mock_std_get, test_config):
    mock_curl_get.side_effect = Exception("Curl failed")
    account = MagicMock()
    account.json.return_value = {"creditsLeft": 500, "requestLimit": 1000}
    page = MagicMock(text="x")
    mock_std_get.side_effect = [account, page, page]

    fetcher = Fetcher(test_config)
    fetcher.fetch("https://example.com/a")
    fetcher.fetch("https://example.com/b")
    # 1 zapytanie o konto + 2 pobrania
    assert mock_std_get.call_count == 3


@patch('usi_scrapers.fetcher.time.sleep')
@patch('usi_scrapers.fetcher.curl_requests.Session.get')
def test_fetcher_breaker_opens_after_repeated_throttling(mock_curl_get, mock_sleep, test_config):
    mock_curl_get.side_effect = _HttpError(429)
    fetcher = Fetcher(test_config)
    for _ in range(3):
        assert fetcher.fetch("https://example.com/p", use_scraperapi=False) is None
    assert fetcher.breaker_open("example.com")

    calls_before = mock_curl_get.call_count
    assert fetcher.fetch("https://example.com/p", use_scraperapi=False) is None
    assert mock_curl_get.call_count == calls_before  # brak żądania do serwera
    assert fetcher.stats["example.com"]["breaker_skips"] == 1
    assert fetcher.stats["example.com"]["status"]["429"] == 3


@patch('usi_scrapers.fetcher.time.sleep')
@patch('usi_scrapers.fetcher.curl_requests.Session.get')
def test_fetcher_success_resets_throttle_streak(mock_curl_get, mock_sleep, test_config):
    fetcher = Fetcher(test_config)
    mock_curl_get.side_effect = _HttpError(429)
    fetcher.fetch("https://example.com/a", use_scraperapi=False)
    fetcher.fetch("https://example.com/a", use_scraperapi=False)
    mock_curl_get.side_effect = None
    mock_curl_get.return_value = MagicMock(text="ok")
    assert fetcher.fetch("https://example.com/a", use_scraperapi=False) == "ok"
    assert "example.com" not in fetcher._throttle_streak
    assert not fetcher.breaker_open("example.com")
