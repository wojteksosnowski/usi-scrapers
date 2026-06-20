import json
import logging
from pathlib import Path
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)
PATTERNS_DIR = Path(__file__).parent.parent / "schemas" / "patterns"

def generate_fingerprint(data: Any, path: str = "") -> Set[str]:
    """Rekurencyjnie wyciąga ścieżki kluczy i ich typy."""
    structure = set()
    if isinstance(data, dict):
        for k, v in data.items():
            current_path = f"{path}.{k}" if path else k
            structure.add(f"{current_path}:{type(v).__name__}")
            structure.update(generate_fingerprint(v, current_path))
    elif isinstance(data, list):
        if data:
            structure.update(generate_fingerprint(data[0], f"{path}[]"))
    return structure

def check_evolution(current_data: Dict, pattern_name: str) -> Dict:
    """Porównuje bieżącą strukturę z wzorcem i raportuje zmiany."""
    pattern_path = PATTERNS_DIR / f"{pattern_name}.json"
    
    if not pattern_path.exists():
        logger.info(f"Generating new pattern for {pattern_name}")
        structure = generate_fingerprint(current_data)
        with open(pattern_path, 'w') as f:
            json.dump(list(structure), f, indent=2)
        return {"status": "created"}
    
    with open(pattern_path, 'r') as f:
        pattern = set(json.load(f))
    
    current = generate_fingerprint(current_data)
    
    missing = pattern - current  # Klucze, które zniknęły
    added = current - pattern    # Klucze, które się pojawiły
    
    return {
        "status": "stable" if not (missing or added) else "changed",
        "missing_keys": list(missing),
        "added_keys": list(added)
    }

def normalize_to_legacy_props(data: dict, portal: str) -> dict:
    """
    Adapter zapewniający kompatybilność wsteczną.
    Konwertuje pełny, nowy payload RAW do formatu oczekiwanego przez stare mapowania.
    """
    if not data:
        return {}
        
    if portal == "oto":
        # Jeśli to nowy, pełny __NEXT_DATA__, ekstrahujemy pageProps
        if "props" in data and "pageProps" in data["props"]:
            return data["props"]["pageProps"]
        # Jeśli klucz 'ad' lub 'data' jest już na roocie, to znaczy, że to stary format
        if "ad" in data or "searchAds" in data or "data" in data:
            return data
            
    if portal == "rp":
        # Dla RynekPierwotny struktura API v2. 
        # Jeśli w przyszłości zmieni się wrapper, tu implementujemy translację.
        return data
        
    if portal == "to":
        if "to_url" in data and "url" not in data:
            data["url"] = data["to_url"]
        return data

    return data
