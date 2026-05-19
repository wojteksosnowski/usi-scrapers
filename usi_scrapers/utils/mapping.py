import json
import re
from pathlib import Path
from typing import Any

_MAPPING_FILE = Path(__file__).parent.parent.parent / "portal_data_mapping.json"
_MAPPING_DATA = None

def load_mapping() -> dict:
    global _MAPPING_DATA
    if _MAPPING_DATA is None:
        if not _MAPPING_FILE.exists():
            return {}
        with open(_MAPPING_FILE, "r", encoding="utf-8") as f:
            _MAPPING_DATA = json.load(f)
    return _MAPPING_DATA

def get_mapping(portal_prefix: str, entity_type: str = "investment") -> dict:
    """Gets the path definitions for a specific portal and entity type."""
    mapping = load_mapping()
    return mapping.get("portals", {}).get(portal_prefix, {}).get(entity_type, {})

def resolve_path(data: dict | list, path: str) -> Any:
    """
    Resolves a custom path string against a JSON-like dictionary or list.
    Supports:
    - Dot notation: a.b.c
    - Array indices: a[0].b
    - Array filtering: a[label=something].b
    """
    if not path or data is None:
        return None

    parts = path.split('.')
    current = data
    
    for part in parts:
        if current is None:
            return None
            
        bracket_match = re.search(r'^([^\[]*)\[(.*?)\]$', part)
        if bracket_match:
            key = bracket_match.group(1)
            condition = bracket_match.group(2)
            
            if key:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return None
                    
            if current is None:
                return None
                
            if isinstance(current, list):
                if condition.isdigit():
                    idx = int(condition)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
                elif '=' in condition:
                    c_key, c_val = condition.split('=', 1)
                    found = False
                    for item in current:
                        if isinstance(item, dict) and str(item.get(c_key)) == c_val:
                            current = item
                            found = True
                            break
                    if not found:
                        return None
                else:
                    return None
            else:
                return None
        else:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
                
    return current
