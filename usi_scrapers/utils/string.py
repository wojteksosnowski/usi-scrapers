import unicodedata
import re

def slugify(text: str) -> str:
    """
    Converts Polish characters, makes lowercase, removes non-alphanumeric, 
    and replaces spaces with hyphens.
    """
    if not text:
        return ""
        
    # Replace common Polish characters explicitly for better transliteration
    pl_chars = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 
        'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 
        'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    for pl, lat in pl_chars.items():
        text = text.replace(pl, lat)
        
    # Normalize unicode and encode to ascii
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('utf-8')
    
    # Lowercase, replace non-alphanumeric with hyphen
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    
    return text.strip('-')
