import os
import glob
import json
from collections import defaultdict
from usi_scrapers.mapping import transform_to_unified

def test_extraction(data_dir):
    portals = ['rp', 'oto', 'to']
    stats = defaultdict(lambda: defaultdict(int))
    
    # We will test a subset of files to keep it fast
    # Searching for raw_{portal}_*.json
    
    for portal in portals:
        print(f"\\n--- Testing Portal {portal.upper()} ---")
        pattern = os.path.join(data_dir, "**", f"raw_{portal}_*.json")
        files = glob.glob(pattern, recursive=True)
        
        print(f"Found {len(files)} files for {portal}")
        
        # Test first 100 files
        for fpath in files[:100]:
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    
                unified = transform_to_unified(portal, raw_data, "investment")
                
                amenities = unified.get("amenities", [])
                
                if amenities:
                    stats[portal]['has_amenities'] += 1
                    
                    if portal == 'rp':
                        # Check if numerical elements are present in RP facilities
                        # RP facilities usually are strings of numbers like '1', '14', etc.
                        has_numerical = any(str(a).isdigit() for a in amenities)
                        if has_numerical:
                            stats[portal]['has_numerical_amenities'] += 1
                        
                stats[portal]['total'] += 1
                
                # Debug output for first 3 files with amenities
                if amenities and stats[portal]['debug_printed'] < 3:
                    print(f"[{portal}] Amenities in {os.path.basename(fpath)}: {amenities}")
                    stats[portal]['debug_printed'] += 1
                    
            except Exception as e:
                # Some might not be valid investment JSONs (e.g. dev raw files if they matched)
                stats[portal]['errors'] += 1
                
        print(f"Stats for {portal}:")
        print(f"  Total processed: {stats[portal]['total']}")
        print(f"  Files with amenities: {stats[portal]['has_amenities']}")
        if portal == 'rp':
            print(f"  Files with numerical amenities (RP specific check): {stats[portal]['has_numerical_amenities']}")
        print(f"  Errors: {stats[portal]['errors']}")

if __name__ == "__main__":
    data_dir = "/Volumes/Samsam/Public/USIdata"
    test_extraction(data_dir)
