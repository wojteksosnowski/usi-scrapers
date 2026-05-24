from typing import Any, Dict, Optional

def classify_segment(signals: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Classifies an investment into one of the 5 USI categories based on diagnostic signals.
    
    Priority Order:
    1. prs (Rental flag)
    2. segmenty i domy (House/Plot area signals)
    3. lokale usługowe (Commercial signals)
    4. lokale inwestycyjne (Investment unit tags)
    5. mieszkania deweloperskie (Residential signals)
    
    Returns:
        The category name string or None if classification fails (null fallback).
    """
    if not signals:
        return None
        
    # 1. PRS (Institutional Rental)
    if signals.get("rental") is True or signals.get("rental") == "rent":
        return "prs"
    
    # 2. Segmenty i domy
    # Check for non-zero counts or plot area existence
    houses = signals.get("houses")
    if houses and houses != 0 and houses != "0":
        return "segmenty i domy"
        
    # 3. Lokale usługowe
    commercial = signals.get("commercial")
    if commercial and commercial != 0 and commercial != "0":
        return "lokale usługowe"
        
    # 4. Lokale inwestycyjne
    # Often tagged as 'apartments' in Offered_estates_type or specific URL keywords
    inv = signals.get("investment")
    if (isinstance(inv, list) and "apartments" in inv) or \
       (isinstance(inv, str) and "apartamenty-inwestycyjne" in inv):
        return "lokale inwestycyjne"

    # 5. Mieszkania deweloperskie
    apartments = signals.get("apartments")
    if apartments and apartments != 0 and apartments != "0":
        return "mieszkania deweloperskie"
        
    # Fallback - null
    return None
