"""
Dry-run: sprawdza istniejące raw_*.json w USIdata i pokazuje
ile ma portal_id w _usi_meta (gotowe do nowego nazewnictwa)
a ile nie ma (zostanie stary format jako fallback).
"""
import json
from pathlib import Path
from collections import Counter

PUBLIC_DIR = Path(__file__).parent / "Public"
DATA_DIR = PUBLIC_DIR / "USIdata"

stats = Counter()
examples_with_id = []
examples_without_id = []

for raw_file in sorted(DATA_DIR.rglob("raw_*.json")):
    # pomiń archiwa z timestampem
    parts = raw_file.stem.split("_")
    if len(parts) >= 4 and parts[-1].isdigit() and len(parts[-1]) == 6:
        continue  # HHMMSS
    if len(parts) >= 4 and len(parts[-2]) == 8 and parts[-2].isdigit():
        continue  # YYYYMMDD

    try:
        data = json.loads(raw_file.read_text(encoding="utf-8"))
    except Exception as e:
        stats["unreadable"] += 1
        continue

    meta = data.get("_usi_meta", {})
    portal = meta.get("portal", "?")
    portal_id = meta.get("portal_id")
    current_name = raw_file.name

    if portal_id:
        new_name = f"raw_{portal}_{portal_id}.json"
        needs_rename = new_name != current_name
        stats["has_id"] += 1
        if needs_rename:
            stats["would_rename"] += 1
            if len(examples_with_id) < 10:
                examples_with_id.append((current_name, new_name, str(raw_file.parent.relative_to(DATA_DIR))))
        else:
            stats["already_correct"] += 1
    else:
        stats["no_id"] += 1
        if len(examples_without_id) < 10:
            examples_without_id.append((current_name, str(raw_file.parent.relative_to(DATA_DIR))))

total = stats["has_id"] + stats["no_id"] + stats["unreadable"]
print(f"\n=== DRY-RUN portal_id w raw_*.json ===")
print(f"Łącznie plików:       {total}")
print(f"  ma portal_id:       {stats['has_id']}  ({stats['has_id']/max(total,1)*100:.1f}%)")
print(f"    już poprawna nazwa: {stats['already_correct']}")
print(f"    wymagałoby rename:  {stats['would_rename']}")
print(f"  brak portal_id:     {stats['no_id']}  ({stats['no_id']/max(total,1)*100:.1f}%)  ← zostanie stary format")
print(f"  nieczytelne:        {stats['unreadable']}")

if examples_with_id:
    print(f"\n--- Przykłady z portal_id (pierwsze {len(examples_with_id)}) ---")
    for cur, new, folder in examples_with_id:
        arrow = "→" if cur != new else "✓"
        print(f"  {folder}/")
        print(f"    {cur}  {arrow}  {new}")

if examples_without_id:
    print(f"\n--- Przykłady BEZ portal_id (pierwsze {len(examples_without_id)}) ---")
    for name, folder in examples_without_id:
        print(f"  {folder}/{name}")

print()
