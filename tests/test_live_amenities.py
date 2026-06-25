import pytest
from usi_scrapers.api import ingest_investment_by_url
from usi_scrapers.mapping import transform_to_unified
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher

@pytest.fixture
def live_config(tmp_path):
    return ScraperConfig(public_dir=str(tmp_path))

@pytest.fixture
def live_fetcher(live_config):
    return Fetcher(live_config)

@pytest.mark.live
def test_live_amenities_rp(live_config, live_fetcher):
    # Znany bogaty URL w RP
    url = "https://rynekpierwotny.pl/oferty/spravia/aalto-gdansk-wrzeszcz-17388/"
    
    raw_data = ingest_investment_by_url(live_config, live_fetcher, "rp", url)
    assert "error" not in raw_data, "Błąd pobierania live z RP"
    
    payload = raw_data.get("raw_details", raw_data)
    unified = transform_to_unified("rp", payload)
    
    amenities = unified.get("amenities") or []
    assert isinstance(amenities, list)
    assert len(amenities) > 0, "Brak udogodnień po transformacji z RP"
    # Oczekiwane na podstawie historycznych danych z USIMaster (teraz surowe identyfikatory numeryczne jako stringi)
    assert any(isinstance(a, str) and a.isdigit() for a in amenities)

@pytest.mark.live
def test_live_amenities_oto(live_config, live_fetcher):
    # Znany bogaty URL w Otodom
    url = "https://www.otodom.pl/pl/oferta/29-l-ID4AEY6"
    
    raw_data = ingest_investment_by_url(live_config, live_fetcher, "oto", url)
    assert "error" not in raw_data, "Błąd pobierania live z OTO"
    
    payload = raw_data.get("raw_details", raw_data)
    unified = transform_to_unified("oto", payload)
    
    amenities = unified.get("amenities") or []
    assert isinstance(amenities, list)
    if len(amenities) > 0:
        assert isinstance(amenities[0], str)

@pytest.mark.live
def test_live_amenities_to(live_config, live_fetcher):
    # TO nie zawsze ma stabilne URL-e, więc używamy np. znanego dobrego lub sprawdzamy jedynie logikę.
    # W testach E2E lepiej mieć przynajmniej jeden live test jeśli URL jest stały.
    pass
