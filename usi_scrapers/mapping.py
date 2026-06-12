"""
Mapping engine for raw portal data.
Designed exclusively for processing `raw_*.json` files (source of truth).
Do not use on partially transformed or normalized data.
"""
import json
import re
from pathlib import Path
from typing import Any

from .transformers import apply_transformer
from .utils.integrity import normalize_to_legacy_props

_MAPPING_FILE = Path(__file__).parent / "schemas" / "portal_data_mapping.json"
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

def list_available_keys(portal_prefix: str, entity_type: str = "investment") -> list[str]:
    """Returns a list of keys available for the specified portal and entity."""
    mapping = get_mapping(portal_prefix, entity_type)
    return list(mapping.keys())

def resolve_path(data: dict | list, path: str | dict) -> Any:
    """
    Resolves a custom path string against a JSON-like dictionary or list.
    Supports:
    - Dot notation: a.b.c
    - Array indices: a[0].b
    - Array filtering: a[label=something].b
    - Dict with regex: {"path": "a.b", "regex": "pattern"}
    """
    if not path or data is None:
        return None

    regex_pattern = None
    transform_name = None
    if isinstance(path, dict):
        if "evaluate_signals" in path:
            signals = path["evaluate_signals"]
            for sig_name, sig_path in signals.items():
                val = resolve_path(data, sig_path)
                if val is not None and val != 0 and val != "0" and val != False:
                    return sig_name
            return path.get("fallback")

        regex_pattern = path.get("regex")
        transform_name = path.get("transform")
        path = path.get("path")
        if not path:
            return None

    if regex_pattern and isinstance(path, str) and '|' not in path:
        pass # Will handle below
        
    if isinstance(path, str) and '|' in path:
        paths = path.split('|')
        for p in paths:
            temp_path = {"path": p.strip(), "regex": regex_pattern, "transform": transform_name} 
            if not regex_pattern and not transform_name:
                temp_path = p.strip()
            res = resolve_path(data, temp_path)
            if res is not None:
                return res
        return None

    if path == ".":
        current = data
    else:
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
                
    if regex_pattern and isinstance(current, str):
        match = re.search(regex_pattern, current)
        if match:
            if match.groups():
                for g in match.groups():
                    if g is not None:
                        current = g
                        break
            else:
                current = match.group(0)
        else:
            current = None

    if transform_name and current is not None:
        current = apply_transformer(transform_name, current)

    return current

def transform_to_unified(portal_prefix: str, raw_data: dict, entity_type: str = "investment") -> dict:
    """
    Transforms raw_data using portal_data_mapping into a unified schema dictionary.
    This eliminates the need for manual parsing in downstream consumers.
    """
    if not raw_data:
        return {}
        
    # Apply compatibility adapter
    raw_data = normalize_to_legacy_props(raw_data, portal_prefix)
        
    mapping = get_mapping(portal_prefix, entity_type)
    unified = {}
    
    for key, path_config in mapping.items():
        unified[key] = resolve_path(raw_data, path_config)
        
    return unified
