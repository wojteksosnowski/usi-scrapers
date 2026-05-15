"""
Add missing OTO developers to USIdev using oto_search_results.csv.
For each developer picks the best link (exact ID match > deweloperzy > any),
calls download_raw_dev("otodom", portal_id, dev_slug), then merges known_id
into agency_ids when it differs from the portal ID.
"""
import csv
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from usi_scrapers.api import download_raw_dev
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig
from usi_scrapers.utils.io import save_dev_raw_json

REPO_ROOT = Path(__file__).parent
SEARCH_CSV = REPO_ROOT / "reference" / "usimaster" / "oto_search_results.csv"
PUBLIC_DIR = REPO_ROOT / "Public"

_ID_RE   = re.compile(r"-ID(\d+)$")
_SLUG_RE = re.compile(r"/([^/]+)-ID\d+$")


def _parse_link(link: str) -> tuple[Optional[str], Optional[str]]:
    m_id   = _ID_RE.search(link)
    m_slug = _SLUG_RE.search(link)
    if m_id and m_slug:
        return m_id.group(1), m_slug.group(1)
    return None, None


def _pick_best(rows: list[dict]) -> Optional[dict]:
    known_id = rows[0]["known_id"]
    # 1. exact ID match
    for row in rows:
        pid, _ = _parse_link(row["link"])
        if pid == known_id:
            return row
    # 2. deweloperzy category
    for row in rows:
        if "deweloperzy" in row["link"]:
            return row
    # 3. any link
    return rows[0] if rows else None


def _merge_known_id(path: Path, known_id: str) -> None:
    """Add known_id to agency_ids in the saved raw file if missing."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ids: list = data.get("agency_ids") or []
        if known_id not in ids:
            ids.append(known_id)
            data["agency_ids"] = ids
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"    merged known_id {known_id} into agency_ids")
    except Exception as e:
        print(f"    WARNING: could not merge known_id: {e}")


def main() -> None:
    config = ScraperConfig(public_dir=str(PUBLIC_DIR))
    fetcher = Fetcher(config)

    # Group rows by known_id, skip no-result rows
    groups: dict[str, list[dict]] = defaultdict(list)
    with open(SEARCH_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["link"]:
                groups[row["known_id"]].append(row)

    ok = skipped = 0

    for known_id, rows in groups.items():
        best = _pick_best(rows)
        if not best:
            print(f"SKIP known_id={known_id}: no usable link")
            skipped += 1
            continue

        portal_id, dev_slug = _parse_link(best["link"])
        name = best["name"]

        print(f"{name}  known_id={known_id}  portal_id={portal_id}  slug={dev_slug}")

        path = download_raw_dev(config, fetcher, "otodom", portal_id, dev_slug)

        if path is None:
            # Live fetch failed — save a mock stub so the index can find known_id
            print(f"    fetch failed — saving mock stub")
            existing = PUBLIC_DIR / "USIdev" / dev_slug / f"raw_oto_{dev_slug}.json"
            known_ids: list = []
            if existing.exists():
                try:
                    known_ids = json.loads(existing.read_text(encoding="utf-8")).get("agency_ids") or []
                except Exception:
                    pass
            for eid in (portal_id, known_id):
                if eid and eid not in known_ids:
                    known_ids.append(eid)
            save_dev_raw_json(
                {"agency_id": portal_id, "agency_ids": known_ids, "name": name, "_mock": True},
                PUBLIC_DIR, dev_slug, "oto",
            )
            ok += 1
        else:
            if known_id != portal_id:
                _merge_known_id(path, known_id)
            ok += 1

        time.sleep(1.5)

    print(f"\nDone — added: {ok}, skipped: {skipped}")


if __name__ == "__main__":
    main()
