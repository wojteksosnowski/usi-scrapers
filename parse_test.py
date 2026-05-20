import re
import json

def parse_to_dev_raw(html: str) -> dict:
    m_next = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m_next:
        try:
            return json.loads(m_next.group(1))
        except Exception as e:
            print("NEXT_DATA parse error:", e)

    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    for s in scripts:
        if '"@type":"Organization"' in s or '"@type": "Organization"' in s or '"@type":"LocalBusiness"' in s or '"@type": "LocalBusiness"' in s:
            try:
                d = json.loads(s.strip())
                items = d if isinstance(d, list) else [d]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") in ("Organization", "LocalBusiness"):
                        return item
            except Exception as e:
                print("JSON-LD parse error:", e)
                
    # Fallback to finding any json with klientId
    for s in scripts:
        match = re.search(r'(\{.*?["\']klientId["\']\s*:\s*\d+.*?\})', s)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
                
    return {}

print("Defined parse_to_dev_raw")
