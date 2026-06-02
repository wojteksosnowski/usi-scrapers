import pytest
from usi_scrapers.mapping import resolve_path

def test_resolve_path_simple():
    data = {"a": {"b": {"c": 123}}}
    assert resolve_path(data, "a.b.c") == 123
    assert resolve_path(data, "a.b.d") is None

def test_resolve_path_list_index():
    data = {"a": [{"b": 1}, {"b": 2}]}
    assert resolve_path(data, "a[0].b") == 1
    assert resolve_path(data, "a[1].b") == 2
    assert resolve_path(data, "a[2].b") is None

def test_resolve_path_list_filter():
    data = {
        "topInformation": [
            {"label": "other", "values": ["a"]},
            {"label": "number_of_units_in_project", "values": ["100"]}
        ]
    }
    assert resolve_path(data, "topInformation[label=number_of_units_in_project].values[0]") == "100"
    assert resolve_path(data, "topInformation[label=missing].values[0]") is None

def test_resolve_path_root_list():
    data = [{"id": 1}, {"id": 2}]
    assert resolve_path(data, "[0].id") == 1
    assert resolve_path(data, "[id=2].id") == 2

def test_resolve_path_transform():
    data = {"stats": {"ranges_height_min": "260 cm"}}
    # Testing transform only
    path_def = {"path": "stats.ranges_height_min", "transform": "cm_to_m", "unit": "m"}
    assert resolve_path(data, path_def) == 2.6

    # Testing transform with regex
    data2 = {"url": "/inwestycja/super-house,i123"}
    path_def2 = {"path": "url", "regex": ",i(\\d+)", "transform": "cm_to_m"} # silly transform just to see if it processes string
    assert resolve_path(data2, path_def2) == 1.23

    # Testing fallback string formatting
    path_def3 = "stats.missing|stats.ranges_height_min"
    assert resolve_path(data, path_def3) == "260 cm"

def test_resolve_path_evaluate_signals():
    data = {
        "apartments_count": 0,
        "houses_count": 5
    }
    path_def = {
        "evaluate_signals": {
            "apartments": "apartments_count",
            "houses": "houses_count"
        },
        "fallback": "unknown"
    }
    assert resolve_path(data, path_def) == "houses"

    data2 = {
        "apartments_count": "0",
        "houses_count": 0
    }
    assert resolve_path(data2, path_def) == "unknown"

    data3 = {
        "url": "/domy-na-sprzedaz"
    }
    path_def2 = {
        "evaluate_signals": {
            "apartments": {"path": "url", "regex": "mieszkania"},
            "houses": {"path": "url", "regex": "domy"}
        },
        "fallback": "unknown"
    }
    assert resolve_path(data3, path_def2) == "houses"

