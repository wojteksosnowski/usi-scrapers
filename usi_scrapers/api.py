"""
Public API dla usi-scrapers.
Zbiór metod służących do interakcji z pakietem.
"""
from typing import Any, Dict, List

def list_investments(developer_slug: str, portal: str | None = None) -> List[Dict[str, Any]]:
    """Pobiera listę inwestycji dewelopera ze wskazanego portalu."""
    raise NotImplementedError

def fetch_investment(url_or_slug: str, portal: str | None = None) -> Dict[str, Any]:
    """Pobiera szczegóły konkretnej inwestycji ze wskazanego portalu."""
    raise NotImplementedError

def transform_raw(raw_data: Dict[str, Any], portal: str) -> Dict[str, Any]:
    """Transformuje surowy JSON z portalu na wewnętrzny ujednolicony format USI."""
    raise NotImplementedError
