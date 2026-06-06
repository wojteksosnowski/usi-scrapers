"""Tests for developer logo extraction and download across all three portals."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from usi_scrapers.scraper_rp import extract_rp_dev_logo
from usi_scrapers.scraper_otodom import extract_otodom_dev_logo
from usi_scrapers.utils.images import download_developer_logo
from usi_scrapers.models import ScraperConfig


# ─── extract_rp_dev_logo ───────────────────────────────────────────────────

class TestExtractRpDevLogo:
    def test_plain_logo_field(self):
        assert extract_rp_dev_logo({"logo": "https://cdn.rp.pl/logo.png"}) == "https://cdn.rp.pl/logo.png"

    def test_logo_url_field(self):
        assert extract_rp_dev_logo({"logo_url": "https://cdn.rp.pl/logo.jpg"}) == "https://cdn.rp.pl/logo.jpg"

    def test_image_field(self):
        assert extract_rp_dev_logo({"image": "https://cdn.rp.pl/img.webp"}) == "https://cdn.rp.pl/img.webp"

    def test_logo_as_dict_with_url(self):
        assert extract_rp_dev_logo({"logo": {"url": "https://cdn.rp.pl/logo.png"}}) == "https://cdn.rp.pl/logo.png"

    def test_logo_as_dict_with_src(self):
        assert extract_rp_dev_logo({"logo": {"src": "https://cdn.rp.pl/logo.png"}}) == "https://cdn.rp.pl/logo.png"

    def test_none_when_no_logo(self):
        assert extract_rp_dev_logo({"name": "Devco", "slug": "devco"}) is None

    def test_ignores_relative_url(self):
        assert extract_rp_dev_logo({"logo": "/static/logo.png"}) is None

    def test_empty_dict(self):
        assert extract_rp_dev_logo({}) is None


# ─── extract_otodom_dev_logo ───────────────────────────────────────────────

class TestExtractOtodomDevLogo:
    def test_advertiser_logo_url(self):
        props = {"advertiser": {"logoUrl": "https://img.otodom.pl/logo.jpg"}}
        assert extract_otodom_dev_logo(props) == "https://img.otodom.pl/logo.jpg"

    def test_agency_logo_dict(self):
        props = {"agency": {"logo": {"url": "https://img.otodom.pl/logo.png"}}}
        assert extract_otodom_dev_logo(props) == "https://img.otodom.pl/logo.png"

    def test_agency_logo_url(self):
        props = {"agency": {"logoUrl": "https://img.otodom.pl/logo.webp"}}
        assert extract_otodom_dev_logo(props) == "https://img.otodom.pl/logo.webp"

    def test_shallow_scan_finds_logo_key(self):
        props = {"someSection": {"logoImage": "https://cdn.otodom.pl/x.jpg"}}
        assert extract_otodom_dev_logo(props) == "https://cdn.otodom.pl/x.jpg"

    def test_top_level_logo_key(self):
        props = {"logoSrc": "https://cdn.otodom.pl/logo.jpg", "name": "Devco"}
        assert extract_otodom_dev_logo(props) == "https://cdn.otodom.pl/logo.jpg"

    def test_none_when_no_logo(self):
        assert extract_otodom_dev_logo({"title": "Devco", "ads": []}) is None

    def test_empty_dict(self):
        assert extract_otodom_dev_logo({}) is None


# Removed obsolete TestExtractToDevLogo and TestExtractToDevData tests


# ─── download_developer_logo ──────────────────────────────────────────────

class TestDownloadDeveloperLogo:
    def test_saves_to_usidev_dir(self, tmp_path):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raw = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            with patch("shutil.copyfileobj"):
                result = download_developer_logo("https://cdn.pl/logo.png", tmp_path / "USIdev" / "devco", portal_prefix="rp", portal_id="955")

        assert result == "logo_rp_955.png"
        assert (tmp_path / "USIdev" / "devco").exists()

    def test_preserves_jpg_extension(self, tmp_path):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raw = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            with patch("shutil.copyfileobj"):
                result = download_developer_logo("https://cdn.pl/logo.jpg?v=2", tmp_path / "USIdev" / "devco", portal_prefix="oto", portal_id="9867181")
        assert result == "logo_oto_9867181.jpg"

    def test_defaults_to_jpg_for_unknown_extension(self, tmp_path):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raw = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            with patch("shutil.copyfileobj"):
                result = download_developer_logo("https://cdn.pl/logo", tmp_path / "USIdev" / "devco", portal_prefix="to", portal_id="12345")
        assert result == "logo_to_12345.jpg"

    def test_skips_existing_large_file(self, tmp_path):
        logo_path = tmp_path / "USIdev" / "devco" / "logo_rp_955.png"
        logo_path.parent.mkdir(parents=True)
        logo_path.write_bytes(b"x" * 2048)

        with patch("requests.get") as mock_get:
            result = download_developer_logo("https://cdn.pl/logo.png", tmp_path / "USIdev" / "devco", portal_prefix="rp", portal_id="955")
            mock_get.assert_not_called()

        assert result == "logo_rp_955.png"

    def test_returns_empty_string_on_error(self, tmp_path):
        with patch("requests.get", side_effect=Exception("network error")):
            result = download_developer_logo("https://cdn.pl/logo.jpg", tmp_path / "USIdev" / "devco", portal_id="999")
        assert result == ""

    def test_raises_when_portal_id_missing(self, tmp_path):
        import pytest as _pytest
        with _pytest.raises(ValueError, match="portal_id is required"):
            download_developer_logo("https://cdn.pl/logo.png", tmp_path / "USIdev" / "devco", portal_prefix="rp")
