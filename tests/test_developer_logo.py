"""Tests for developer logo extraction and download across all three portals."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from usi_scrapers.scraper_rp import extract_rp_dev_logo
from usi_scrapers.scraper_otodom import extract_otodom_dev_logo
from usi_scrapers.scraper_to import extract_to_dev_logo, extract_to_dev_data
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


# ─── extract_to_dev_logo ──────────────────────────────────────────────────

class TestExtractToDevLogo:
    def test_og_image_property_first(self):
        html = '<meta property="og:image" content="https://cdn.to.pl/logo.jpg"/>'
        assert extract_to_dev_logo(html) == "https://cdn.to.pl/logo.jpg"

    def test_og_image_reversed_attribute_order(self):
        html = '<meta content="https://cdn.to.pl/logo.jpg" property="og:image"/>'
        assert extract_to_dev_logo(html) == "https://cdn.to.pl/logo.jpg"

    def test_img_with_alt_logo(self):
        html = '<img alt="logo firmy" src="https://cdn.to.pl/logo.png"/>'
        assert extract_to_dev_logo(html) == "https://cdn.to.pl/logo.png"

    def test_img_with_class_logo(self):
        html = '<img class="company-logo" src="https://cdn.to.pl/dev-logo.jpg"/>'
        assert extract_to_dev_logo(html) == "https://cdn.to.pl/dev-logo.jpg"

    def test_none_when_no_logo(self):
        html = "<html><body><h1>Devco</h1></body></html>"
        assert extract_to_dev_logo(html) is None

    def test_og_image_takes_priority(self):
        html = (
            '<meta property="og:image" content="https://og.pl/logo.jpg"/>'
            '<img class="logo" src="https://img.pl/other.jpg"/>'
        )
        assert extract_to_dev_logo(html) == "https://og.pl/logo.jpg"


# ─── extract_to_dev_data ──────────────────────────────────────────────────

class TestExtractToDevData:
    def test_url_always_present(self):
        data = extract_to_dev_data("<html></html>", "https://tabelaofert.pl/katalog-firm/deweloperzy/devco")
        assert data["url"] == "https://tabelaofert.pl/katalog-firm/deweloperzy/devco"

    def test_name_from_jsonld_organization(self):
        html = '<script type="application/ld+json">{"@type":"Organization","name":"Devco Sp. z o.o."}</script>'
        data = extract_to_dev_data(html, "https://tabelaofert.pl/katalog-firm/deweloperzy/devco")
        assert data["name"] == "Devco Sp. z o.o."

    def test_name_from_h1_fallback(self):
        html = "<h1>Devco S.A.</h1>"
        data = extract_to_dev_data(html, "https://x.pl/y")
        assert data["name"] == "Devco S.A."

    def test_no_name_when_empty(self):
        data = extract_to_dev_data("<html></html>", "https://x.pl/y")
        assert data.get("name") is None


# ─── download_developer_logo ──────────────────────────────────────────────

class TestDownloadDeveloperLogo:
    def test_saves_to_usidev_dir(self, tmp_path):
        config = ScraperConfig(public_dir=tmp_path)
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raw = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            with patch("shutil.copyfileobj"):
                result = download_developer_logo("https://cdn.pl/logo.png", "devco", config, portal_prefix="rp")

        assert result == "logo_rp_devco.png"
        assert (tmp_path / "USIdev" / "devco").exists()

    def test_preserves_jpg_extension(self, tmp_path):
        config = ScraperConfig(public_dir=tmp_path)
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raw = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            with patch("shutil.copyfileobj"):
                result = download_developer_logo("https://cdn.pl/logo.jpg?v=2", "devco", config, portal_prefix="oto")
        assert result == "logo_oto_devco.jpg"

    def test_defaults_to_jpg_for_unknown_extension(self, tmp_path):
        config = ScraperConfig(public_dir=tmp_path)
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raw = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            with patch("shutil.copyfileobj"):
                result = download_developer_logo("https://cdn.pl/logo", "devco", config, portal_prefix="to")
        assert result == "logo_to_devco.jpg"

    def test_skips_existing_large_file(self, tmp_path):
        config = ScraperConfig(public_dir=tmp_path)
        logo_path = tmp_path / "USIdev" / "devco" / "logo_rp_devco.png"
        logo_path.parent.mkdir(parents=True)
        logo_path.write_bytes(b"x" * 2048)

        with patch("requests.get") as mock_get:
            result = download_developer_logo("https://cdn.pl/logo.png", "devco", config, portal_prefix="rp")
            mock_get.assert_not_called()

        assert result == "logo_rp_devco.png"

    def test_returns_empty_string_on_error(self, tmp_path):
        config = ScraperConfig(public_dir=tmp_path)
        with patch("requests.get", side_effect=Exception("network error")):
            result = download_developer_logo("https://cdn.pl/logo.jpg", "devco", config)
        assert result == ""
