def get_val(data, key, default=None):
    """
    Helper to unwrap nested Coda/RP JSON values recursively.
    Handles both {"value": ...} and {"type": "obj", "value": ...} patterns.
    """
    if data is None:
        return default
    
    val = data.get(key, default)
    
    # Recursive unwrapping
    while isinstance(val, dict) and "value" in val:
        val = val["value"]
    
    return val
