import csv
import json
import re
from pathlib import Path
from typing import Dict, Optional

from . import get_logger
from .utils.images import clean_filename
from .utils.io import save_raw_json, save_meta_json
from .scraper_otodom import _parse_otodom_slug

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


def _build_usi_index(public_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    usi = public_dir / "USI"
    if not usi.is_dir():
        return index
    for p in usi.rglob("*"):
        if p.is_file() and p.stat().st_size > 0:
            index.setdefault(p.name, p)
    return index


def _fix_imglist_paths(
    raw: Optional[str],
    usi_index: dict[str, Path],
    repo_root: Path,
) -> Optional[str]:
    if not raw:
        return raw
    fixed = []
    for p in (s.strip() for s in raw.split(",") if s.strip()):
        abs_path = repo_root / p.lstrip("/")
        if abs_path.exists() and abs_path.stat().st_size > 0:
            fixed.append(p)
        else:
            hit = usi_index.get(Path(p).name)
            if hit:
                fixed.append("/" + str(hit.relative_to(repo_root)))
            else:
                fixed.append(p)
    return ", ".join(fixed) or None


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


def _rp_image_filenames(rp_data: dict) -> set[str]:
    fnames: set[str] = set()
    main = rp_data.get("main_image") or {}
    if isinstance(main, dict) and "value" in main:
        main = main["value"]
    if isinstance(main, dict):
        for url in main.values():
            if isinstance(url, str):
                fnames.add(clean_filename(url))
    for item in (rp_data.get("_raw_gallery") or {}).get("gallery") or []:
        for url in (item.get("image") or {}).values():
            if isinstance(url, str):
                fnames.add(clean_filename(url))
    return fnames - {""}


def _oto_image_filenames(oto_data: dict) -> set[str]:
    fnames: set[str] = set()
    for item in (oto_data.get("ad") or {}).get("images") or []:
        for url in item.values():
            if isinstance(url, str) and "apollo.olxcdn.com" in url:
                fname = clean_filename(url)
                fnames.add(fname)
                # Otodom CDN images land on disk as .webp regardless of URL extension
                stem = fname.rsplit(".", 1)[0]
                fnames.add(stem + ".webp")
    return fnames - {""}


def _split_imglist(
    raw: Optional[str],
    rp_data: Optional[dict],
    oto_data: Optional[dict],
) -> tuple[Optional[str], Optional[str]]:
    if not raw:
        return None, None
    paths = [p.strip() for p in raw.split(",") if p.strip()]
    if not paths:
        return None, None
    rp_fnames = _rp_image_filenames(rp_data) if rp_data else set()
    oto_fnames = _oto_image_filenames(oto_data) if oto_data else set()
    rp_paths: list[str] = []
    oto_paths: list[str] = []
    unmatched: list[str] = []
    for p in paths:
        fname = Path(p).name
        if fname in rp_fnames:
            rp_paths.append(p)
        elif fname in oto_fnames:
            oto_paths.append(p)
        else:
            unmatched.append(p)
    if unmatched:
        if rp_data and not oto_data:
            rp_paths.extend(unmatched)
        elif oto_data and not rp_data:
            oto_paths.extend(unmatched)
    return (", ".join(rp_paths) or None, ", ".join(oto_paths) or None)


def import_usimaster_csv(
    csv_path: Path = DEFAULT_CSV,
    public_dir: Path = DEFAULT_PUBLIC,
) -> None:
    rp_index, oto_index = _build_usidev_index(public_dir)
    usi_index = _build_usi_index(public_dir)
    repo_root = public_dir.parent
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

            rp_raw = row.get("rpJSON", "").strip()
            oto_raw = row.get("otoJSON", "").strip()
            imglist_raw = row.get("imgList", "").strip() or None

            # pre-parse both JSONs for imgList splitting (best-effort)
            try:
                _rp_pre: Optional[dict] = json.loads(rp_raw) if rp_raw else None
            except Exception:
                _rp_pre = None
            try:
                _oto_pre: Optional[dict] = json.loads(oto_raw) if oto_raw else None
            except Exception:
                _oto_pre = None

            rp_imglist, oto_imglist = _split_imglist(imglist_raw, _rp_pre, _oto_pre)
            rp_imglist = _fix_imglist_paths(rp_imglist, usi_index, repo_root)
            oto_imglist = _fix_imglist_paths(oto_imglist, usi_index, repo_root)

            # --- RP block ---
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
                        rp_portal_id = str(rp_data.get("id", "")) or None
                        save_raw_json(rp_data, public_dir, dev_slug, inv_slug, "rp", portal_id=rp_portal_id)
                        save_meta_json({**meta, "imgList": rp_imglist}, public_dir, dev_slug, inv_slug, "rp", portal_id=rp_portal_id)
                        saved_rp += 1
                except Exception as e:
                    logger.warning("row %d RP error: %s", i, e)
                    row_skipped = True
                    skipped += 1

            # --- OTO block ---
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
                        ad_url = (oto_data.get("ad") or {}).get("url", "")
                        ad_slug = ad_url.rstrip("/").rsplit("/", 1)[-1] if ad_url else ""
                        _, hash_part = _parse_otodom_slug(ad_slug)
                        oto_portal_id = f"ID{hash_part}" if hash_part else None
                        save_raw_json(oto_data, public_dir, dev_slug, inv_slug, "oto", portal_id=oto_portal_id)
                        save_meta_json({**meta, "imgList": oto_imglist}, public_dir, dev_slug, inv_slug, "oto", portal_id=oto_portal_id)
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
