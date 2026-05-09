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
