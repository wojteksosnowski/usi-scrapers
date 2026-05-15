"""
Tests for the USImaster CSV import pipeline.
Checks whether image paths listed in imgList column are resolvable on disk.
Skips automatically when reference CSV or Public/USI tree are absent.
"""
import csv
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CSV_PATH  = REPO_ROOT / "reference" / "usimaster" / "USImaster-prep.csv"
USI_ROOT  = REPO_ROOT / "Public" / "USI"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse_img_list(raw: str) -> list[str]:
    """Split comma-separated imgList cell into individual path strings."""
    return [p.strip() for p in raw.split(",") if p.strip()]


def _resolve_path(img_path: str) -> Path:
    """Convert /Public/USI/... to an absolute filesystem path."""
    return REPO_ROOT / img_path.lstrip("/")


def _find_by_filename(filename: str) -> list[Path]:
    """Search all of Public/USI/ for a file with this name."""
    return list(USI_ROOT.rglob(filename)) if USI_ROOT.is_dir() else []


def _load_rows() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def image_check_results():
    """
    Returns a list of dicts, one per image reference:
      path, row_id, found_by_path, found_by_name, alt_paths
    """
    if not CSV_PATH.exists():
        pytest.skip(f"USImaster CSV not found: {CSV_PATH}")
    if not USI_ROOT.is_dir():
        pytest.skip(f"Public/USI directory not found: {USI_ROOT}")

    results = []
    for row in _load_rows():
        row_id = row.get("Inwestycja") or row.get("USIfolder") or "?"
        for img_path in _parse_img_list(row.get("imgList", "")):
            resolved = _resolve_path(img_path)
            found_by_path = resolved.exists() and resolved.stat().st_size > 0
            alt_paths: list[Path] = []
            if not found_by_path:
                alt_paths = _find_by_filename(resolved.name)
            results.append({
                "row_id":        row_id,
                "path":          img_path,
                "found_by_path": found_by_path,
                "found_by_name": bool(alt_paths),
                "alt_paths":     alt_paths,
            })
    return results


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_all_images_have_entries(image_check_results):
    """Every imgList entry must resolve either by path or by filename search."""
    truly_missing = [
        r for r in image_check_results
        if not r["found_by_path"] and not r["found_by_name"]
    ]
    if truly_missing:
        lines = [
            f"  [{r['row_id']}] {r['path']}"
            for r in truly_missing
        ]
        pytest.fail(
            f"{len(truly_missing)} image(s) not found by path OR filename:\n"
            + "\n".join(lines)
        )


def test_images_found_by_path(image_check_results):
    """Report images that exist on disk but at a different path than recorded."""
    wrong_path = [
        r for r in image_check_results
        if not r["found_by_path"] and r["found_by_name"]
    ]
    if wrong_path:
        lines = []
        for r in wrong_path:
            alt = ", ".join(str(p.relative_to(REPO_ROOT)) for p in r["alt_paths"][:2])
            lines.append(f"  [{r['row_id']}] recorded: {r['path']}\n    found at: {alt}")
        pytest.fail(
            f"{len(wrong_path)} image(s) found by filename but path is stale:\n"
            + "\n".join(lines)
        )


def test_image_path_coverage_summary(image_check_results):
    """
    Informational: print coverage breakdown.
    Never fails — just ensures the numbers are visible in -v output.
    """
    total         = len(image_check_results)
    by_path       = sum(1 for r in image_check_results if r["found_by_path"])
    by_name_only  = sum(1 for r in image_check_results if not r["found_by_path"] and r["found_by_name"])
    missing       = total - by_path - by_name_only

    print(
        f"\nImage coverage: {total} total | "
        f"{by_path} by path ({by_path/total:.0%}) | "
        f"{by_name_only} by filename only | "
        f"{missing} not found"
    )
    assert total > 0, "No image references found — is imgList column empty?"
