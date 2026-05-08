import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher
import time

@pytest.fixture
def test_config(tmp_path):
    return ScraperConfig(
        public_dir=tmp_path,
        scraperapi_key="test_key",
        usage_stats_path=tmp_path / "USIdata" / "scraperapi_stats.json",
        fetch_delays={"example.com": 0.1, "default": 0.0}
    )

def test_fetcher_rate_limiting(test_config):
    fetcher = Fetcher(test_config)
    
    start_time = time.time()
    # First request shouldn't wait
    fetcher._apply_rate_limit("example.com")
    assert time.time() - start_time < 0.1
    
    # Second request should wait at least 0.1s
    start_time2 = time.time()
    fetcher._apply_rate_limit("example.com")
    assert time.time() - start_time2 >= 0.1

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
    # Make curl fail
    mock_curl_get.side_effect = Exception("Curl failed")
    
    # Make std_requests (ScraperAPI) succeed
    mock_std_response = MagicMock()
    mock_std_response.text = "<html>scraperapi</html>"
    mock_std_response.raise_for_status = MagicMock()
    mock_std_get.return_value = mock_std_response

    fetcher = Fetcher(test_config)
    content = fetcher.fetch("https://example.com")
    
    assert content == "<html>scraperapi</html>"
    mock_std_get.assert_called_once()
    
    # Check if usage stats were updated
    import json
    stats_file = test_config.usage_stats_path
    assert stats_file.exists()
    with open(stats_file, 'r') as f:
        data = json.load(f)
        assert data['scraperapi']['used'] == 1
