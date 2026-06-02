"""
Data Transformers for the Mapping Engine.
Allows applying specific logic to parsed values.
"""
import re
from typing import Any, Callable

_TRANSFORMERS: dict[str, Callable[[Any], Any]] = {}

def register_transformer(name: str):
    def decorator(func: Callable[[Any], Any]):
        _TRANSFORMERS[name] = func
        return func
    return decorator

def apply_transformer(name: str, value: Any) -> Any:
    if value is None:
        return None
    if name not in _TRANSFORMERS:
        raise ValueError(f"Unknown transformer: {name}")
    try:
        return _TRANSFORMERS[name](value)
    except Exception:
        return value

@register_transformer("cm_to_m")
def _cm_to_m(value: Any) -> float | None:
    """Converts a cm value (string or numeric) to meters."""
    try:
        if isinstance(value, str):
            # Extract just digits and dots/commas
            value = value.replace(",", ".")
            m = re.search(r"(\d+(?:\.\d+)?)", value)
            if not m:
                return None
            num = float(m.group(1))
        else:
            num = float(value)
        # Assuming typical ceiling heights, if it's over 100, it's likely cm.
        if num > 100:
            return round(num / 100, 2)
        return round(num, 2)
    except (ValueError, TypeError):
        return None

@register_transformer("date_to_quarter")
def _date_to_quarter(value: Any) -> int | None:
    """Converts a date string like '2025-01' to a quarter number (1-4)."""
    try:
        if isinstance(value, str):
            parts = value.split("-")
            if len(parts) >= 2:
                month = int(parts[1])
                return (month - 1) // 3 + 1
        return None
    except (ValueError, TypeError):
        return None
