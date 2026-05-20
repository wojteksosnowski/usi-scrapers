import json
import re

def run():
    with open("/Volumes/Samsam/claude-py/usi-scrapers/dev_page.html") as f:
        html = f.read()
        
    print("Finding JSON-LDs...")
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    for s in scripts:
        if "@type" in s:
            print("--- JSON-LD ---")
            print(s[:500])
            
    print("\nFinding window objects...")
    for s in scripts:
        if "window." in s:
            print("--- Window ---")
            print(s[:500])

if __name__ == "__main__":
    run()
