import csv
import json
from pathlib import Path

from .utils.io import save_dev_raw_json

REPO_ROOT = Path(__file__).parent.parent


def import_competitors_csv(
    csv_path: Path = REPO_ROOT / "reference" / "konkurenci.csv",
    public_dir: Path = REPO_ROOT / "Public",
) -> None:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name     = row.get("Deweloper", "").strip()
            rp_slug  = row.get("rpSlug", "").strip()
            rp_id    = row.get("rpID", "").strip()
            oto_slug = row.get("otoSlug", "").strip()
            oto_id   = row.get("otoID", "").strip().lstrip("ID")

            if rp_slug and rp_id:
                rp_dev_url = f"https://rynekpierwotny.pl/deweloperzy/{rp_slug}/"
                save_dev_raw_json(
                    {"id": rp_id, "slug": rp_slug, "name": name, "_mock": True},
                    public_dir, rp_slug, "rp",
                    portal_id=rp_id,
                    source_url=rp_dev_url,
                )
            if oto_slug and oto_id:
                existing_path = Path(public_dir) / "USIdev" / oto_slug / f"raw_oto_{oto_slug}.json"
                known_ids: list = []
                if existing_path.exists():
                    try:
                        known_ids = json.loads(existing_path.read_text(encoding="utf-8")).get("agency_ids") or []
                    except Exception:
                        pass
                if oto_id not in known_ids:
                    known_ids.append(oto_id)
                oto_dev_url = f"https://www.otodom.pl/pl/firmy/deweloperzy/{oto_slug}-ID{oto_id}"
                save_dev_raw_json(
                    {"agency_id": oto_id, "agency_ids": known_ids, "name": name, "_mock": True},
                    public_dir, oto_slug, "oto",
                    portal_id=oto_id,
                    source_url=oto_dev_url,
                )


if __name__ == "__main__":
    import_competitors_csv()
