import json
import argparse
import logging
from pathlib import Path
import shutil

logging.basicConfig(level=logging.INFO, format="%(message)s")

def clean_file(filepath: Path, apply: bool) -> bool:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logging.error(f"Could not read {filepath}: {e}")
        return False

    if not isinstance(data, dict):
        return False

    modified = False
    keys_removed = []

    # 1. Universal: _usi_meta
    if "_usi_meta" in data:
        del data["_usi_meta"]
        keys_removed.append("_usi_meta")
        modified = True

    name = filepath.name
    is_to = "raw_to_" in name
    is_rp = "raw_rp_" in name
    is_oto = "raw_oto_" in name

    # 2. Portal specific cleanups
    if is_to:
        for k in ["_extracted_location", "_raw_gallery_urls", "url"]:
            if k in data:
                # Ochrona przed usunięciem 'url' ze skromnych plików dev profilu TO
                if k == "url" and len(data) <= 5 and "klient_id" in data:
                    continue
                del data[k]
                keys_removed.append(k)
                modified = True

    elif is_rp:
        if "_raw_gallery" in data:
            del data["_raw_gallery"]
            keys_removed.append("_raw_gallery")
            modified = True

    elif is_oto:
        # Prawdziwe pliki raw Otodom to root obiektu Next.js
        if "url" in data and "props" in data:
            del data["url"]
            keys_removed.append("url")
            modified = True

    if modified:
        if apply:
            # Tworzymy backup przed nadpisaniem
            backup_path = filepath.with_suffix(".json.bak")
            shutil.copy2(filepath, backup_path)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logging.info(f"[FIXED] {filepath} (removed: {', '.join(keys_removed)})")
        else:
            logging.info(f"[DRY-RUN] WOULD FIX: {filepath} (remove: {', '.join(keys_removed)})")
        return True
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleans legacy injections from raw_*.json files.")
    parser.add_argument("directory", help="Root directory to scan (e.g. Public/USIdata or Public/USIdev)")
    parser.add_argument("--apply", action="store_true", help="Apply changes and save .bak backups")
    args = parser.parse_args()

    target_dir = Path(args.directory)
    if not target_dir.exists():
        logging.error(f"Directory {target_dir} does not exist.")
        exit(1)

    logging.info(f"Scanning {target_dir} for raw_*.json files...")
    
    count = 0
    total = 0
    for f in target_dir.rglob("raw_*.json"):
        if f.is_file():
            total += 1
            if clean_file(f, args.apply):
                count += 1

    action = "Fixed" if args.apply else "Would fix"
    logging.info(f"\n--- Summary ---")
    logging.info(f"Total raw files scanned: {total}")
    logging.info(f"{action}: {count} files.")
