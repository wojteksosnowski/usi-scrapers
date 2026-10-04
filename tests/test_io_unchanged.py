from usi_scrapers.utils.io import save_raw_json


def test_identical_raw_not_archived(tmp_path):
    target = tmp_path / "USIdata" / "dev" / "inv"
    data = {"a": 1, "b": ["x", "zażółć"]}
    p1 = save_raw_json(data, target, "rp", "1")
    p2 = save_raw_json(dict(data), target, "rp", "1")
    assert p1 == p2
    assert sorted(f.name for f in target.glob("raw_rp_1*.json")) == ["raw_rp_1.json"]


def test_changed_raw_is_archived(tmp_path):
    target = tmp_path / "USIdata" / "dev" / "inv"
    save_raw_json({"a": 1}, target, "rp", "1")
    save_raw_json({"a": 2}, target, "rp", "1")
    assert len(list(target.glob("raw_rp_1_*.json"))) == 1
