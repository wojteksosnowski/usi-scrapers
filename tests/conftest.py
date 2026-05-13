import pytest
from unittest.mock import MagicMock
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher


@pytest.fixture
def config(tmp_path):
    return ScraperConfig(public_dir=tmp_path)


@pytest.fixture
def fetcher(config):
    f = Fetcher(config)
    f.fetch = MagicMock()
    f.fetch_json = MagicMock()
    return f
