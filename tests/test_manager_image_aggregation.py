"""
Tests for TechnicalDataManager.collect_archived_image_urls
and TechnicalDataManager.collect_disk_image_filenames.

Weryfikuje, że lista image_urls i image_paths po zapisie zawiera
obrazy zarówno z bieżącego scrapowania, jak i poprzednich (zarchiwizowanych)
kopii pliku raw JSON oraz plików już obecnych na dysku.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from usi_scrapers.manager import TechnicalDataManager
from usi_scrapers.models import ScraperConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config(tmp_path):
    return ScraperConfig(public_dir=tmp_path)


@pytest.fixture
def manager(config):
    return TechnicalDataManager(config)


# ---------------------------------------------------------------------------
# collect_disk_image_filenames
# ---------------------------------------------------------------------------

def test_collect_disk_image_filenames_empty_dir(tmp_path):
    empty_dir = tmp_path / "USI" / "dev" / "inv"
    empty_dir.mkdir(parents=True)
    result = TechnicalDataManager.collect_disk_image_filenames(empty_dir)
    assert result == []


def test_collect_disk_image_filenames_nonexistent_dir(tmp_path):
    result = TechnicalDataManager.collect_disk_image_filenames(tmp_path / "nonexistent")
    assert result == []


def test_collect_disk_image_filenames_returns_known_extensions(tmp_path):
    img_dir = tmp_path / "USI" / "dev" / "inv"
    img_dir.mkdir(parents=True)

    # Valid large images
    for name in ("a.jpg", "b.png", "c.webp"):
        f = img_dir / name
        f.write_bytes(b"X" * 2048)  # > 1KB

    # Too small (should be skipped)
    (img_dir / "tiny.jpg").write_bytes(b"small")

    # Non-image extension (should be skipped)
    (img_dir / "data.json").write_bytes(b"X" * 2048)

    result = TechnicalDataManager.collect_disk_image_filenames(img_dir)
    assert set(result) == {"a.jpg", "b.png", "c.webp"}


# ---------------------------------------------------------------------------
# collect_archived_image_urls
# ---------------------------------------------------------------------------

def _make_oto_raw(images: list[dict]) -> dict:
    return {"ad": {"images": images}}


def _make_to_raw(gallery_urls: list[str]) -> dict:
    return {"_raw_gallery_urls": gallery_urls}


def _make_rp_raw(gallery_list: list[dict]) -> dict:
    return {"_raw_gallery": {"gallery": gallery_list}}


def test_collect_archived_image_urls_no_archives(tmp_path):
    inv_dir = tmp_path / "USIdata" / "dev" / "inv"
    inv_dir.mkdir(parents=True)
    result = TechnicalDataManager.collect_archived_image_urls(inv_dir, "oto", "ID123")
    assert result == []


def test_collect_archived_image_urls_oto(tmp_path):
    inv_dir = tmp_path / "USIdata" / "dev" / "inv"
    inv_dir.mkdir(parents=True)

    arc1 = _make_oto_raw([
        {"large": "https://cdn.oto.pl/img1.webp"},
        {"medium": "https://cdn.oto.pl/img2.webp"},
    ])
    arc2 = _make_oto_raw([
        {"large": "https://cdn.oto.pl/img3.webp"},
        {"large": "https://cdn.oto.pl/img1.webp"},  # duplicate
    ])

    (inv_dir / "raw_oto_ID123_20260601_100000.json").write_text(json.dumps(arc1))
    (inv_dir / "raw_oto_ID123_20260602_110000.json").write_text(json.dumps(arc2))

    result = TechnicalDataManager.collect_archived_image_urls(inv_dir, "oto", "ID123")
    # img1 appears in both, should be deduplicated
    assert "https://cdn.oto.pl/img1.webp" in result
    assert "https://cdn.oto.pl/img2.webp" in result
    assert "https://cdn.oto.pl/img3.webp" in result
    assert len(result) == 3


def test_collect_archived_image_urls_to(tmp_path):
    inv_dir = tmp_path / "USIdata" / "dev" / "inv"
    inv_dir.mkdir(parents=True)

    arc = _make_to_raw(["https://to.pl/img1.jpg", "https://to.pl/img2.jpg"])
    (inv_dir / "raw_to_i9999_20260601_120000.json").write_text(json.dumps(arc))

    result = TechnicalDataManager.collect_archived_image_urls(inv_dir, "to", "i9999")
    assert result == ["https://to.pl/img1.jpg", "https://to.pl/img2.jpg"]


def test_collect_archived_image_urls_rp(tmp_path):
    inv_dir = tmp_path / "USIdata" / "dev" / "inv"
    inv_dir.mkdir(parents=True)

    rp_gallery = [
        {"image": {"g_img_2000": "https://cdn.rp.pl/img1.jpg"}},
        {"image": {"g_img_2000": "https://cdn.rp.pl/img2.jpg"}},
    ]
    arc = _make_rp_raw(rp_gallery)
    (inv_dir / "raw_rp_1234_20260601_130000.json").write_text(json.dumps(arc))

    result = TechnicalDataManager.collect_archived_image_urls(inv_dir, "rp", "1234")
    assert "https://cdn.rp.pl/img1.jpg" in result
    assert "https://cdn.rp.pl/img2.jpg" in result


def test_collect_archived_image_urls_corrupt_file_skipped(tmp_path):
    inv_dir = tmp_path / "USIdata" / "dev" / "inv"
    inv_dir.mkdir(parents=True)

    (inv_dir / "raw_oto_XBAD_20260601_140000.json").write_text("NOT VALID JSON {{{")
    # Should not raise; simply returns empty
    result = TechnicalDataManager.collect_archived_image_urls(inv_dir, "oto", "XBAD")
    assert result == []


# ---------------------------------------------------------------------------
# save_raw_data — integration with image aggregation (no real HTTP)
# ---------------------------------------------------------------------------

def test_save_raw_data_merges_archived_image_urls(tmp_path):
    """
    Weryfikuje, że po zapisie image_urls zawiera zarówno URL-e bieżącego
    scrapowania, jak i adresy z poprzedniej zarchiwizowanej kopii raw JSON.
    """
    config = ScraperConfig(public_dir=tmp_path)
    manager = TechnicalDataManager(config)

    dev_slug = "test-dev"
    inv_slug = "test-inv"
    portal_prefix = "oto"
    portal_id = "ID42"

    # Przygotuj zarchiwizowany plik raw z innym URL obrazka
    inv_dir = tmp_path / "USIdata" / dev_slug / inv_slug
    inv_dir.mkdir(parents=True)
    archived_raw = {"ad": {"images": [{"large": "https://old.cdn/old_image.webp"}]}}
    arc_path = inv_dir / f"raw_{portal_prefix}_{portal_id}_20260601_100000.json"
    arc_path.write_text(json.dumps(archived_raw))

    # Dane bieżącego scrapowania z nowym URL
    current_url = "https://new.cdn/new_image.webp"
    data = {
        "developer_slug": dev_slug,
        "investment_slug": inv_slug,
        "oto_url_id": portal_id,
        "image_urls": [current_url],
        "raw_details": {"ad": {"id": 42, "images": [{"large": current_url}]}},
    }

    # Zastępujemy fizyczne pobieranie obrazów — save_images zwraca nazwy z clean_filename
    with patch("usi_scrapers.manager.save_images") as mock_save:
        mock_save.side_effect = lambda urls, *a, **kw: [
            url.split("/")[-1] for url in urls
        ]
        with patch.object(manager.resolver, "update_investment_index"):
            manager.save_raw_data(data, portal_prefix)

    # image_urls powinno zawierać oba URL-e
    assert current_url in data["image_urls"]
    assert "https://old.cdn/old_image.webp" in data["image_urls"]
    assert len(data["image_urls"]) == 2

    # image_paths powinny zawierać nazwy plików z obu URL-i
    assert any("new_image.webp" in p for p in data["image_paths"])
    assert any("old_image.webp" in p for p in data["image_paths"])


def test_save_raw_data_disk_filenames_included(tmp_path):
    """
    Weryfikuje, że image_paths zawiera też pliki obrazów już istniejące
    na dysku, nawet jeśli ich URL nie pojawił się w bieżącym scrapowaniu.
    """
    config = ScraperConfig(public_dir=tmp_path)
    manager = TechnicalDataManager(config)

    dev_slug = "dev-b"
    inv_slug = "inv-b"
    portal_prefix = "to"
    portal_id = "i8888"

    inv_dir = tmp_path / "USIdata" / dev_slug / inv_slug
    inv_dir.mkdir(parents=True)

    # Utwórz plik obrazu już na dysku (symulacja poprzedniego pobierania)
    img_dir = tmp_path / "USI" / dev_slug / inv_slug
    img_dir.mkdir(parents=True)
    old_img = img_dir / "already_on_disk.jpg"
    old_img.write_bytes(b"X" * 2048)

    current_url = "https://to.pl/fresh.jpg"
    data = {
        "developer_slug": dev_slug,
        "investment_slug": inv_slug,
        "to_id": portal_id,
        "image_urls": [current_url],
        "raw_details": {"_raw_gallery_urls": [current_url]},
    }

    with patch("usi_scrapers.manager.save_images") as mock_save:
        mock_save.return_value = ["fresh.jpg"]
        with patch.object(manager.resolver, "update_investment_index"):
            manager.save_raw_data(data, portal_prefix)

    assert any("fresh.jpg" in p for p in data["image_paths"])
    assert any("already_on_disk.jpg" in p for p in data["image_paths"])
