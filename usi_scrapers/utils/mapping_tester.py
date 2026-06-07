import json
import os
import glob
from collections import defaultdict
from pathlib import Path
from usi_scrapers.mapping import load_mapping, resolve_path

TEST_DIR = Path(__file__).parent.parent / "schemas" / "porta_data_mapping_tests"

def main():
    mapping = load_mapping()
    portals = mapping.get("portals", {})
    
    # Znajdźmy wszystkie testowe JSONy
    test_files = glob.glob(str(TEST_DIR / "raw_*.json"))
    files_by_portal = defaultdict(list)
    
    for f in test_files:
        basename = os.path.basename(f)
        if basename.startswith("raw_rp_"):
            files_by_portal["rp"].append(f)
        elif basename.startswith("raw_oto_"):
            files_by_portal["oto"].append(f)
        elif basename.startswith("raw_to_"):
            files_by_portal["to"].append(f)
            
    report = {
        "title": "Mapping API Coverage Report",
        "results": {}
    }
    
    for portal_prefix, portal_data in portals.items():
        if portal_prefix not in files_by_portal:
            continue
            
        report["results"][portal_prefix] = {
            "name": portal_data.get("name", portal_prefix),
            "files_tested": [os.path.basename(p) for p in files_by_portal[portal_prefix]],
            "entities": {}
        }
        
        for entity_type in ["investment", "developer", "stage"]:
            if entity_type not in portal_data:
                continue
                
            entity_mapping = portal_data[entity_type]
            entity_results = {
                "total_keys": len(entity_mapping),
                "fully_covered": 0,
                "partially_covered": 0,
                "missing": 0,
                "keys": {}
            }
            
            for key, path_def in entity_mapping.items():
                if key == "signals": # signals contains dict, handle specially or flatten
                    continue
                    
                key_results = {
                    "extracted_values": {},
                    "types_found": set(),
                    "success_count": 0,
                    "fail_count": 0
                }
                
                for json_file in files_by_portal[portal_prefix]:
                    with open(json_file, 'r', encoding='utf-8') as jf:
                        raw_data = json.load(jf)
                    
                    # Apply compatibility adapter
                    from .integrity import normalize_to_legacy_props
                    raw_data = normalize_to_legacy_props(raw_data, portal_prefix)
                    
                    val = resolve_path(raw_data, path_def)
                    filename = os.path.basename(json_file)
                    
                    if val is not None:
                        key_results["success_count"] += 1
                        val_type = type(val).__name__
                        key_results["types_found"].add(val_type)
                        
                        # Zapisujemy tylko pierwsze 3 znalezienia, aby nie przeładować raportu
                        if len(key_results["extracted_values"]) < 3:
                            # Jeśli to długa lista/słownik, skróćmy to trochę dla czytelności
                            display_val = val
                            if isinstance(val, (list, dict)):
                                display_val = str(val)[:100] + ("..." if len(str(val)) > 100 else "")
                            key_results["extracted_values"][filename] = f"[{val_type}] {display_val}"
                    else:
                        key_results["fail_count"] += 1
                        
                key_results["types_found"] = list(key_results["types_found"])
                
                if key_results["success_count"] == len(files_by_portal[portal_prefix]):
                    entity_results["fully_covered"] += 1
                    status = "FULL"
                elif key_results["success_count"] > 0:
                    entity_results["partially_covered"] += 1
                    status = "PARTIAL"
                else:
                    entity_results["missing"] += 1
                    status = "MISSING"
                    
                key_results["status"] = status
                entity_results["keys"][key] = key_results
                
            report["results"][portal_prefix]["entities"][entity_type] = entity_results

    # Generate Markdown Report
    md = ["# Raport z Głębokiego Testu Pokrycia Mapowania API\n"]
    
    for p_id, p_data in report["results"].items():
        md.append(f"## Portal: {p_data['name']} ({p_id})")
        md.append(f"**Przetestowane pliki ({len(p_data['files_tested'])}):** {', '.join(p_data['files_tested'])}\n")
        
        for e_id, e_data in p_data['entities'].items():
            md.append(f"### Obiekt: `{e_id}`")
            md.append(f"- Razem kluczy: **{e_data['total_keys']}**")
            md.append(f"- W pełni pokryte: **{e_data['fully_covered']}**")
            md.append(f"- Częściowo pokryte: **{e_data['partially_covered']}**")
            md.append(f"- Całkowity brak pokrycia: **{e_data['missing']}**\n")
            
            md.append("#### Brakujące klucze (MISSING)")
            for k, k_data in e_data["keys"].items():
                if k_data["status"] == "MISSING":
                    md.append(f"- `{k}`")
            md.append("")
            
            md.append("#### Szczegóły ekstrakcji (Różnice w zapisie / Częściowe pokrycie)")
            for k, k_data in e_data["keys"].items():
                if k_data["status"] != "MISSING":
                    status_icon = "🟢" if k_data["status"] == "FULL" else "🟡"
                    md.append(f"**{status_icon} `{k}`** (Sukcesy: {k_data['success_count']}, Błędy: {k_data['fail_count']})")
                    md.append(f"- Odnalezione typy: `{', '.join(k_data['types_found'])}`")
                    md.append("- Przykłady:")
                    for fname, val in k_data["extracted_values"].items():
                        md.append(f"  - `{fname}`: `{val}`")
                    md.append("")
                    
    with open("mapping_coverage_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print("Raport wygenerowany do pliku mapping_coverage_report.md")

if __name__ == "__main__":
    main()
