import os
import json
import pytest
from pathlib import Path
from usi_scrapers.scraper_otodom import scrape_otodom
from usi_scrapers.models import ScraperConfig
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.mapping import transform_to_unified

@pytest.fixture
def config(tmp_path):
    # Ensure USIdev directory exists for proactive fetch
    (tmp_path / "USIdev").mkdir(parents=True, exist_ok=True)
    return ScraperConfig(
        public_dir=tmp_path,
        scraperapi_key=os.getenv("SCRAPERAPI_API_KEY")
    )

@pytest.fixture
def fetcher(config):
    return Fetcher(config)

@pytest.mark.live
def test_oto_live_id_extraction(config, fetcher):
    """
    Test weryfikujący na żywym adresie URL czy ID inwestycji Otodom 
    jest poprawnie wyciągane przez silnik mappingu.
    """
    # Znany URL inwestycji Otodom
    url = "https://www.otodom.pl/pl/oferta/3-pokoje-59-84-m-balkon-parkowe-zlotniki-ID4BHLS"
    
    print(f"\nFetching live URL: {url}")
    result = scrape_otodom(url, fetcher)
    
    if "error" in result:
        # Jeśli SCRAPERAPI_API_KEY brakuje, może nas zablokować - skipujemy zamiast failować test live
        if "403" in str(result["error"]) or "429" in str(result["error"]) or "Forbidden" in str(result["error"]):
            pytest.skip(f"Live fetch blocked (likely no API key): {result['error']}")
        pytest.fail(f"Live fetch failed: {result['error']}")
        
    # transform_to_unified powinien znaleźć ID w 'raw_details' (które jest pełnym __NEXT_DATA__)
    # lub bezpośrednio w result jeśli mapping tak wskazuje.
    # UWAGA: transform_to_unified wywołuje normalize_to_legacy_props.
    # scrape_otodom zwraca słownik zawierający 'raw_details'.
    
    raw_data = result.get("raw_details", result)
    unified = transform_to_unified("oto", raw_data, "investment")
    
    print(f"Unified ID: {unified.get('id')}")
    print(f"Unified Numeric ID: {unified.get('numeric_id')}")
    
    # Podstawowe asercje
    assert unified.get("id") == "4BHLS", f"Expected hash ID '4BHLS', got {unified.get('id')}"
    assert unified.get("numeric_id") is not None, "Numeric ID should not be None"
    
    # Dodatkowe sprawdzenie zagnidżonych ID jeśli istnieją
    # W portal_data_mapping.json mamy "id": "id|ad.id|oto_url_id"
    # W raw_details od scrape_otodom mamy root 'id' (hash) oraz 'ad.id' (numeric)

def test_mapping_with_local_raw_files():
    """
    Weryfikacja baseline na lokalnych plikach testowych.
    """
    mapping_dir = Path("usi_scrapers/schemas/porta_data_mapping_tests")
    if not mapping_dir.exists():
        pytest.skip("Mapping tests directory not found")
        
    oto_files = list(mapping_dir.glob("raw_oto_*.json"))
    
    success_count = 0
    total_count = 0
    
    for oto_file in oto_files:
        with open(oto_file, "r") as f:
            raw_data = json.load(f)
        
        # Interesują nas tylko inwestycje (nie deweloperzy)
        # normalize_to_legacy_props wyciągnie pageProps jeśli trzeba
        props = raw_data.get("props", {}).get("pageProps", raw_data)
        if "ad" not in props and "raw_details" not in raw_data and "searchAds" not in props:
            continue
            
        total_count += 1
        unified = transform_to_unified("oto", raw_data, "investment")
        
        id_val = unified.get("id")
        num_id = unified.get("numeric_id")
        
        print(f"File: {oto_file.name:40} -> ID: {str(id_val):10}, NumID: {str(num_id):10}")
        if id_val or num_id:
            success_count += 1
            
    assert success_count > 0, "No IDs extracted from any local OTO raw file"
    print(f"\nMapping success rate: {success_count}/{total_count}")

def test_mapping_with_random_local_db_files():
    """
    Losuje do 100 plików raw_{portal}_*.json z lokalnej bazy danych (Public/USIdata) 
    dla każdego z portali (rp, oto, to) i weryfikuje poprawność ekstrakcji ID. 
    Odrzuca pliki z 'mock' lub 'test' w nazwie.
    """
    import random
    
    # Katalog bazy danych (zgodnie z konwencjami repozytorium to Public/USIdata)
    db_dir = Path("Public/USIdata")
    if not db_dir.exists():
        pytest.skip("Katalog bazy danych 'Public/USIdata' nie istnieje. Test pominięty.")
        
    portals = ["rp", "oto", "to"]
    overall_success = True
    
    for portal in portals:
        # Szukamy tylko inwestycji (USIdata), omijamy deweloperów (USIdev)
        raw_files = list(db_dir.rglob(f"raw_{portal}_*.json"))
        
        # Filtrujemy mocki i pliki testowe (case-insensitive)
        valid_files = [
            f for f in raw_files 
            if "mock" not in f.name.lower() and "test" not in f.name.lower()
        ]
        
        if not valid_files:
            print(f"\nBrak prawidłowych plików raw_{portal}_*.json w 'Public/USIdata'. Skipowanie portalu.")
            continue
            
        sample_size = min(100, len(valid_files))
        sampled_files = random.sample(valid_files, sample_size)
        
        success_count = 0
        total_count = 0
        failed_files = []
        
        print(f"\nTesting {sample_size} random '{portal}' records from local DB...")
        
        for raw_file in sampled_files:
            try:
                with open(raw_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception as e:
                print(f"Error reading {raw_file.name}: {e}")
                continue
                
            # Heurystyki odfiltrowujące dane deweloperów lub niepełne struktury
            if portal == "oto":
                props = raw_data.get("props", {}).get("pageProps", raw_data)
                if "ad" not in props and "raw_details" not in raw_data and "searchAds" not in props:
                    continue
            elif portal == "rp":
                if "name" not in raw_data and "id" not in raw_data:
                    continue
            elif portal == "to":
                if "name" not in raw_data and "url" not in raw_data:
                    continue
            
            total_count += 1
            unified = transform_to_unified(portal, raw_data, "investment")
            
            id_val = unified.get("id")
            num_id = unified.get("numeric_id")
            
            if id_val or num_id:
                success_count += 1
            else:
                failed_files.append(raw_file.name)
        
        if total_count > 0:
            print(f"Random DB sample success rate for '{portal}': {success_count}/{total_count}")
            if failed_files:
                print(f"Failed extractions ({len(failed_files)}):", ", ".join(failed_files[:10]) + ("..." if len(failed_files) > 10 else ""))
            
            if success_count != total_count:
                overall_success = False
                
    assert overall_success, "Wystąpiły błędy ekstrakcji ID w próbkach danych historycznych (szczegóły powyżej)."

if __name__ == "__main__":
    # Pozwala na szybkie uruchomienie skryptu bezpośrednio
    pytest.main([__file__, "-s"])
