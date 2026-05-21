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
