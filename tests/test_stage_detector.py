import json
import pytest
from pathlib import Path
from usi_scrapers.utils.stage_detector import (
    is_multistage,
    extract_groups_id,
    extract_stages,
    build_stage_url,
    run_stage_detection,
)


STAGE_A = {
    "id": 1,
    "sort": 1,
    "current": True,
    "primary": True,
    "offer": {
        "id": 100,
        "slug": "etap-1",
        "name": "Etap 1",
        "vendor": {"slug": "devco"},
    },
}
STAGE_B = {
    "id": 2,
    "sort": 2,
    "current": False,
    "primary": False,
    "offer": {
        "id": 200,
        "slug": "etap-2",
        "name": "Etap 2",
        "vendor": {"slug": "devco"},
    },
}
MULTISTAGE_DATA = {
    "groups": {
        "id": 42,
        "name": "Osiedle XYZ",
        "stages": [STAGE_A, STAGE_B],
    }
}
SINGLESTAGE_DATA = {"groups": {"id": 42, "stages": []}}
NO_GROUPS_DATA = {"name": "Solo"}


class TestIsMultistage:
    def test_true_when_stages_present(self):
        assert is_multistage(MULTISTAGE_DATA) is True

    def test_false_when_stages_empty(self):
        assert is_multistage(SINGLESTAGE_DATA) is False

    def test_false_when_no_groups(self):
        assert is_multistage(NO_GROUPS_DATA) is False

    def test_false_on_empty_dict(self):
        assert is_multistage({}) is False


class TestExtractGroupsId:
    def test_returns_id(self):
        assert extract_groups_id(MULTISTAGE_DATA) == 42

    def test_returns_none_when_no_groups(self):
        assert extract_groups_id(NO_GROUPS_DATA) is None

    def test_returns_none_on_empty(self):
        assert extract_groups_id({}) is None


class TestExtractStages:
    def test_returns_two_stages(self):
        stages = extract_stages(MULTISTAGE_DATA)
        assert len(stages) == 2

    def test_stage_fields_present(self):
        stages = extract_stages(MULTISTAGE_DATA)
        s = stages[0]
        assert s["stage_id"] == 1
        assert s["offer_id"] == "100"
        assert s["slug"] == "etap-1"
        assert s["name"] == "Etap 1"
        assert s["vendor_slug"] == "devco"
        assert s["sort"] == 1
        assert s["current"] is True
        assert s["primary"] is True
        assert "url" in s

    def test_non_current_stage(self):
        stages = extract_stages(MULTISTAGE_DATA)
        s = stages[1]
        assert s["current"] is False
        assert s["primary"] is False

    def test_empty_when_no_stages(self):
        assert extract_stages(SINGLESTAGE_DATA) == []

    def test_empty_when_no_groups(self):
        assert extract_stages(NO_GROUPS_DATA) == []

    def test_empty_on_empty_dict(self):
        assert extract_stages({}) == []


class TestBuildStageUrl:
    def test_url_format(self):
        url = build_stage_url("devco", "etap-1", "100", 1)
        assert url == (
            "https://rynekpierwotny.pl/oferty/devco/etap-1-100/"
            "?show_sold_stage=true&stage=1"
        )

    def test_url_in_extract_stages(self):
        stages = extract_stages(MULTISTAGE_DATA)
        expected = build_stage_url("devco", "etap-1", "100", 1)
        assert stages[0]["url"] == expected


class TestRunStageDetection:
    def _write_result(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_skips_non_rp_files(self, tmp_path):
        result_path = tmp_path / "devco" / "etap-1" / "app_result_1.json"
        self._write_result(result_path, {"source": "otodom.pl", "raw_details": MULTISTAGE_DATA})
        stats = run_stage_detection(tmp_path)
        assert stats["updated"] == 0
        assert stats["stubs_created"] == 0

    def test_updates_rp_file_with_stage_metadata(self, tmp_path):
        rp_data = {
            "source": "rynekpierwotny.pl",
            "id": 100,
            "developer_slug": "devco",
            "investment_slug": "etap-1",
            "raw_details": MULTISTAGE_DATA,
        }
        result_path = tmp_path / "devco" / "etap-1" / "app_result_1.json"
        self._write_result(result_path, rp_data)

        stats = run_stage_detection(tmp_path)
        assert stats["updated"] == 1

        with open(result_path, encoding="utf-8") as f:
            updated = json.load(f)
        assert updated["groups_id"] == 42
        assert updated["groups_name"] == "Osiedle XYZ"
        assert len(updated["sibling_stages"]) == 2
        assert "devco/etap-2" in updated["sibling_stage_folders"]

    def test_creates_stub_for_sibling(self, tmp_path):
        rp_data = {
            "source": "rynekpierwotny.pl",
            "id": 100,
            "developer_slug": "devco",
            "investment_slug": "etap-1",
            "raw_details": MULTISTAGE_DATA,
        }
        result_path = tmp_path / "devco" / "etap-1" / "app_result_1.json"
        self._write_result(result_path, rp_data)

        stats = run_stage_detection(tmp_path)
        assert stats["stubs_created"] == 1

        stub_path = tmp_path / "devco" / "etap-2" / "usi_stage_stub.json"
        assert stub_path.exists()
        with open(stub_path, encoding="utf-8") as f:
            stub = json.load(f)
        assert stub["status"] == "stub"
        assert stub["offer_id"] == "200"
        assert stub["slug"] == "etap-2"
        assert stub["developer_slug"] == "devco"

    def test_skips_stub_if_result_exists(self, tmp_path):
        rp_data = {
            "source": "rynekpierwotny.pl",
            "id": 100,
            "developer_slug": "devco",
            "investment_slug": "etap-1",
            "raw_details": MULTISTAGE_DATA,
        }
        result_path = tmp_path / "devco" / "etap-1" / "app_result_1.json"
        self._write_result(result_path, rp_data)

        sibling_result = tmp_path / "devco" / "etap-2" / "app_result_99.json"
        self._write_result(sibling_result, {"source": "rynekpierwotny.pl", "id": 200})

        stats = run_stage_detection(tmp_path)
        assert stats["stubs_created"] == 0

    def test_no_files_returns_zero(self, tmp_path):
        stats = run_stage_detection(tmp_path)
        assert stats == {"updated": 0, "stubs_created": 0}

    def test_handles_corrupt_json(self, tmp_path):
        bad = tmp_path / "devco" / "bad" / "app_result_1.json"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("not json")
        stats = run_stage_detection(tmp_path)
        assert stats["updated"] == 0

    def test_stage_sort_and_current_set_on_result(self, tmp_path):
        rp_data = {
            "source": "rynekpierwotny.pl",
            "id": 100,
            "developer_slug": "devco",
            "investment_slug": "etap-1",
            "raw_details": MULTISTAGE_DATA,
        }
        result_path = tmp_path / "devco" / "etap-1" / "app_result_1.json"
        self._write_result(result_path, rp_data)
        run_stage_detection(tmp_path)
        with open(result_path, encoding="utf-8") as f:
            updated = json.load(f)
        assert updated["stage_sort"] == 1
        assert updated["stage_is_current"] is True
