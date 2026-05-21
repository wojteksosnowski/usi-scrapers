import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .mapping import get_mapping, resolve_path
from .. import get_logger

logger = get_logger(__name__)


def is_multistage(rp_details: dict) -> bool:
    rp_mapping = get_mapping("rp", "investment")
    return bool(resolve_path(rp_details, rp_mapping.get("groups_stages")))


def extract_groups_id(rp_details: dict):
    rp_mapping = get_mapping("rp", "investment")
    return resolve_path(rp_details, rp_mapping.get("groups_id"))


def extract_stages(rp_details: dict) -> list:
    rp_mapping = get_mapping("rp", "investment")
    stage_mapping = get_mapping("rp", "stage")
    stages = resolve_path(rp_details, rp_mapping.get("groups_stages")) or []
    result = []
    for stage in stages:
        vendor_slug = resolve_path(stage, stage_mapping.get("vendor_slug")) or ""
        offer_id = str(resolve_path(stage, stage_mapping.get("offer_id")) or "")
        offer_slug = resolve_path(stage, stage_mapping.get("offer_slug"))
        stage_id = resolve_path(stage, stage_mapping.get("id"))
        result.append({
            "stage_id": stage_id,
            "offer_id": offer_id,
            "slug": offer_slug,
            "name": resolve_path(stage, stage_mapping.get("offer_name")),
            "vendor_slug": vendor_slug,
            "sort": stage.get("sort"),
            "current": bool(stage.get("current")),
            "primary": bool(stage.get("primary")),
            "url": build_stage_url(vendor_slug, offer_slug, offer_id, stage_id),
        })
    return result


def build_stage_url(vendor_slug: str, offer_slug: str, offer_id: str, stage_id) -> str:
    return (
        f"https://rynekpierwotny.pl/oferty/{vendor_slug}/{offer_slug}-{offer_id}/"
        f"?show_sold_stage=true&stage={stage_id}"
    )


def run_stage_detection(data_dir: Path) -> dict:
    data_dir = Path(data_dir)
    updated = 0
    stubs_created = 0

    for result_path in sorted(data_dir.rglob("app_result_*.json")):
        try:
            with open(result_path, encoding="utf-8") as f:
                result = json.load(f)
        except Exception as e:
            logger.warning(f"Could not read {result_path}: {e}")
            continue

        if result.get("source") != "rynekpierwotny.pl":
            continue

        raw = result.get("raw_details") or {}
        if not raw:
            # Try loading rp_details.json from same folder
            rp_path = result_path.parent / "rp_details.json"
            if rp_path.exists():
                try:
                    with open(rp_path, encoding="utf-8") as f:
                        raw = json.load(f)
                except Exception:
                    pass

        stages = extract_stages(raw)
        if not stages:
            continue

        rp_mapping = get_mapping("rp", "investment")
        groups_id = resolve_path(raw, rp_mapping.get("groups_id"))
        groups_name = resolve_path(raw, rp_mapping.get("groups_name")) or ""
        dev_slug = result.get("developer_slug", "")
        current_offer_id = str(result.get("id", ""))

        sibling_folders = [
            f"{dev_slug}/{s['slug']}"
            for s in stages
            if str(s["offer_id"]) != current_offer_id and s["slug"]
        ]

        result["groups_id"] = groups_id
        result["groups_name"] = groups_name
        result["sibling_stage_folders"] = sibling_folders
        result["sibling_stages"] = stages

        for s in stages:
            if str(s["offer_id"]) == current_offer_id:
                result["stage_sort"] = s["sort"]
                result["stage_is_current"] = s["current"]
                break

        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        logger.info(f"Updated {result_path} ({len(stages)} stages, {len(sibling_folders)} siblings)")
        updated += 1

        for stage in stages:
            if str(stage["offer_id"]) == current_offer_id:
                continue
            if not stage["slug"] or not dev_slug:
                continue

            sibling_dir = data_dir / dev_slug / stage["slug"]
            stub_path = sibling_dir / "usi_stage_stub.json"

            existing = list(sibling_dir.glob("app_result_*.json")) if sibling_dir.exists() else []
            if existing:
                continue

            sibling_dir.mkdir(parents=True, exist_ok=True)

            other_folders = [
                f"{dev_slug}/{s['slug']}"
                for s in stages
                if str(s["offer_id"]) != str(stage["offer_id"]) and s["slug"]
            ]

            stub = {
                "source": "rynekpierwotny.pl",
                "status": "stub",
                "groups_id": groups_id,
                "groups_name": groups_name,
                "stage_id": stage["stage_id"],
                "stage_sort": stage["sort"],
                "stage_is_current": stage["current"],
                "offer_id": stage["offer_id"],
                "name": stage["name"],
                "slug": stage["slug"],
                "url": stage["url"],
                "developer_slug": dev_slug,
                "investment_slug": stage["slug"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "sibling_stage_folders": other_folders,
            }

            with open(stub_path, "w", encoding="utf-8") as f:
                json.dump(stub, f, indent=4, ensure_ascii=False)
            logger.info(f"Created stub {stub_path}")
            stubs_created += 1

    logger.info(f"detect-stages: updated={updated}, stubs_created={stubs_created}")
    return {"updated": updated, "stubs_created": stubs_created}
