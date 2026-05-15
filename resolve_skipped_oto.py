"""
One-shot pipeline: read USImaster_skipped.csv → search Otodom for each missing
OTO developer → download developer profile via API (or save mock stub).
After running, re-importing USImaster.csv should produce 0 skipped rows.
"""
import csv
import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from usi_scrapers.api import download_raw_dev
from usi_scrapers.fetcher import Fetcher
from usi_scrapers.models import ScraperConfig
from usi_scrapers.utils.io import save_dev_raw_json

REPO_ROOT   = Path(__file__).parent
SKIPPED_CSV = REPO_ROOT / "reference" / "usimaster" / "USImaster_skipped.csv"
PUBLIC_DIR  = REPO_ROOT / "Public"

_OTO_ID_SUFFIX = re.compile(r"-ID[a-zA-Z0-9]+$")
_PORTAL_ID_RE  = re.compile(r"-ID(\d+)$")
_PORTAL_SLUG_RE = re.compile(r"/([^/]+)-ID\d+$")
_TITLE_LINK_RE  = re.compile(
    r'class="company-item-title"[^>]*>.*?href="(https?://[^"]+)"',
    re.DOTALL,
)

SEARCH_BASES = [
    "https://www.otodom.pl/firmy/deweloperzy/",
    "https://www.otodom.pl/firmy/biura-nieruchomosci/",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse_portal_link(link: str) -> tuple[Optional[str], Optional[str]]:
    m_id   = _PORTAL_ID_RE.search(link)
    m_slug = _PORTAL_SLUG_RE.search(link)
    if m_id and m_slug:
        return m_id.group(1), m_slug.group(1)
    return None, None


def _search_otodom(fetcher: Fetcher, name: str) -> list[dict]:
    """Return list of {url, search_url} found via company-item-title."""
    results = []
    q = urllib.parse.quote_plus(name)
    for base in SEARCH_BASES:
        url = f"{base}?sq={q}"
        try:
            html = fetcher.fetch(url) or ""
            for link in _TITLE_LINK_RE.findall(html):
                results.append({"link": link, "search_url": url})
            time.sleep(1.5)
        except Exception as e:
            print(f"  ERROR {url}: {e}")
    return results


def _pick_best(hits: list[dict], known_id: str) -> Optional[dict]:
    for h in hits:
        pid, _ = _parse_portal_link(h["link"])
        if pid == known_id:
            return h
    for h in hits:
        if "deweloperzy" in h["link"]:
            return h
    return hits[0] if hits else None


def _merge_known_id(path: Path, known_id: str) -> None:
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


def _save_stub(public_dir: Path, dev_slug: str, name: str,
               portal_id: Optional[str], known_id: str) -> None:
    existing = public_dir / "USIdev" / dev_slug / f"raw_oto_{dev_slug}.json"
    known_ids: list = []
    if existing.exists():
        try:
            known_ids = json.loads(existing.read_text(encoding="utf-8")).get("agency_ids") or []
        except Exception:
            pass
    for eid in filter(None, [portal_id, known_id]):
        if eid not in known_ids:
            known_ids.append(eid)
    save_dev_raw_json(
        {"agency_id": portal_id or known_id, "agency_ids": known_ids,
         "name": name, "_mock": True},
        public_dir, dev_slug, "oto",
    )


# ---------------------------------------------------------------------------
# load skipped rows → unique developers
# ---------------------------------------------------------------------------

def _load_developers(csv_path: Path) -> list[dict]:
    """Extract unique OTO developers from skipped CSV."""
    seen: set[str] = set()
    devs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = row.get("otoJSON", "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
                ad       = data.get("ad") or {}
                agency   = ad.get("agency") or {}
                known_id = str(agency.get("id", "")).strip()
                raw_slug = ad.get("slug", "").strip()
                if not known_id or known_id in seen:
                    continue
                seen.add(known_id)
                inv_slug = _OTO_ID_SUFFIX.sub("", raw_slug)
                devs.append({
                    "known_id": known_id,
                    "name":     row.get("Deweloper", "").strip(),
                    "inv_slug": inv_slug,
                })
            except Exception:
                continue
    return devs


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    config  = ScraperConfig(public_dir=str(PUBLIC_DIR))
    fetcher = Fetcher(config)

    devs = _load_developers(SKIPPED_CSV)
    print(f"Loaded {len(devs)} unique OTO developers from skipped CSV\n")

    ok = stubbed = 0

    for dev in devs:
        known_id = dev["known_id"]
        name     = dev["name"]
        inv_slug = dev["inv_slug"]
        print(f"[{name}]  known_id={known_id}")

        hits = _search_otodom(fetcher, name)
        best = _pick_best(hits, known_id) if hits else None

        if best:
            portal_id, dev_slug = _parse_portal_link(best["link"])
            print(f"  → found: {best['link']}")
            path = download_raw_dev(config, fetcher, "otodom", portal_id, dev_slug)
            if path:
                if known_id != portal_id:
                    _merge_known_id(path, known_id)
                ok += 1
            else:
                print(f"  → fetch failed, saving stub")
                _save_stub(PUBLIC_DIR, dev_slug, name, portal_id, known_id)
                stubbed += 1
        else:
            # No search result — stub under inv_slug as fallback directory name
            print(f"  → no search results, saving stub under slug={inv_slug}")
            _save_stub(PUBLIC_DIR, inv_slug, name, None, known_id)
            stubbed += 1

        time.sleep(0.5)

    print(f"\nDone — downloaded: {ok}, stubbed: {stubbed}")


if __name__ == "__main__":
    main()
