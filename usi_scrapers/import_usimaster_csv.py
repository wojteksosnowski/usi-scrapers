import csv
import json
import re
from pathlib import Path
from typing import Dict

from . import get_logger
from .utils.io import save_raw_json, save_meta_json

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_CSV = REPO_ROOT / "reference" / "usimaster" / "USImaster-prep.csv"
DEFAULT_PUBLIC = REPO_ROOT / "Public"

META_FIELDS = [
    ("status",       "Ocena"),
    ("Gwiazdki",     "Gwiazdki"),
    ("Balkony",      "Balkony"),
    ("Fasady",       "Fasady"),
    ("Wnętrza",      "Wnętrza"),
    ("Teren",        "Teren"),
    ("Mieszkania",   "Mieszkania"),
    ("Udogodnienia", "Udogodnienia"),
    ("komentarz",    "komentarz"),
    ("Segment",      "Segment"),
    ("ocenaLog",     "ocenaLOG"),
]

_NUMERIC_KEYS = {"Gwiazdki", "Balkony", "Fasady", "Wnętrza", "Teren", "Mieszkania", "Udogodnienia", "ocenaLog"}
_OTO_ID_SUFFIX = re.compile(r"-ID[a-zA-Z0-9]+$")


def _build_usidev_index(public_dir: Path) -> tuple[Dict[str, str], Dict[str, str]]:
    rp_index: Dict[str, str] = {}
    oto_index: Dict[str, str] = {}
    usidev = public_dir / "USIdev"
    if not usidev.is_dir():
        logger.warning("USIdev directory not found: %s", usidev)
        return rp_index, oto_index

    for raw_file in usidev.glob("*/raw_rp_*.json"):
        dev_slug = raw_file.parent.name
        try:
            data = json.loads(raw_file.read_text(encoding="utf-8"))
            vendor_id = str(data.get("id", "")).strip()
            if vendor_id:
                rp_index[vendor_id] = dev_slug
        except Exception:
            pass

    for raw_file in usidev.glob("*/raw_oto_*.json"):
        dev_slug = raw_file.parent.name
        try:
            data = json.loads(raw_file.read_text(encoding="utf-8"))
            for aid in data.get("agency_ids") or []:
                aid = str(aid).strip()
                if aid:
                    oto_index[aid] = dev_slug
            agency_id = str(data.get("agency_id", "")).strip()
            if agency_id:
                oto_index[agency_id] = dev_slug
        except Exception:
            pass

    logger.info("USIdev index: %d RP, %d OTO entries", len(rp_index), len(oto_index))
    return rp_index, oto_index


def _parse_meta(row: dict) -> dict:
    meta: dict = {}
    for key, col in META_FIELDS:
        raw = row.get(col, "").strip()
        if key in _NUMERIC_KEYS:
            try:
                meta[key] = float(raw) if raw else None
            except ValueError:
                meta[key] = None
        else:
            meta[key] = raw if raw else None
    return meta


def import_usimaster_csv(
    csv_path: Path = DEFAULT_CSV,
    public_dir: Path = DEFAULT_PUBLIC,
) -> None:
    rp_index, oto_index = _build_usidev_index(public_dir)
    skipped_rows: list[dict] = []
    fieldnames: list[str] = []
    skipped = 0
    saved_rp = 0
    saved_oto = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for i, row in enumerate(reader, start=1):
            meta = _parse_meta(row)
            row_skipped = False

            # --- RP block ---
            rp_raw = row.get("rpJSON", "").strip()
            if rp_raw:
                try:
                    rp_data = json.loads(rp_raw)
                    vendor = rp_data.get("vendor") or {}
                    if "value" in vendor:
                        vendor = vendor["value"]
                    vendor_id = str(vendor.get("id", "")).strip()
                    inv_slug = rp_data.get("slug", "").strip()
                    if not vendor_id or not inv_slug:
                        raise ValueError("missing vendor.id or slug")
                    dev_slug = rp_index.get(vendor_id)
                    if not dev_slug:
                        logger.warning("row %d RP: no USIdev entry for vendor_id=%s (%s)", i, vendor_id, inv_slug)
                        row_skipped = True
                        skipped += 1
                    else:
                        save_raw_json(rp_data, public_dir, dev_slug, inv_slug, "rp")
                        save_meta_json(meta, public_dir, dev_slug, inv_slug, "rp")
                        saved_rp += 1
                except Exception as e:
                    logger.warning("row %d RP error: %s", i, e)
                    row_skipped = True
                    skipped += 1

            # --- OTO block ---
            oto_raw = row.get("otoJSON", "").strip()
            if oto_raw:
                try:
                    oto_data = json.loads(oto_raw)
                    ad = oto_data.get("ad") or {}
                    agency = ad.get("agency") or {}
                    agency_id = str(agency.get("id", "")).strip()
                    raw_slug = ad.get("slug", "").strip()
                    if not agency_id or not raw_slug:
                        raise ValueError("missing agency.id or ad.slug")
                    inv_slug = _OTO_ID_SUFFIX.sub("", raw_slug)
                    dev_slug = oto_index.get(agency_id)
                    if not dev_slug:
                        logger.warning("row %d OTO: no USIdev entry for agency_id=%s (%s)", i, agency_id, inv_slug)
                        row_skipped = True
                        skipped += 1
                    else:
                        save_raw_json(oto_data, public_dir, dev_slug, inv_slug, "oto")
                        save_meta_json(meta, public_dir, dev_slug, inv_slug, "oto")
                        saved_oto += 1
                except Exception as e:
                    logger.warning("row %d OTO error: %s", i, e)
                    row_skipped = True
                    skipped += 1

            if row_skipped:
                skipped_rows.append(row)

    if skipped_rows and fieldnames:
        skipped_path = csv_path.with_stem(csv_path.stem + "_skipped")
        with open(skipped_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(skipped_rows)
        logger.warning("Skipped rows written to: %s (%d rows)", skipped_path.name, len(skipped_rows))

    logger.info("Done — saved RP: %d, OTO: %d, skipped: %d", saved_rp, saved_oto, skipped)


if __name__ == "__main__":
    import_usimaster_csv()
