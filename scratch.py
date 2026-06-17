from usi_scrapers.mapping import resolve_path

path = {
    "path": "klientId|logo_url|@id",
    "regex": r"(?:,i(\d+)|,(\d+)-/|^(\d+)$)"
}

print(resolve_path({"klientId": 12345}, path))
print(resolve_path({"logo_url": "logos,54321-/foo"}, path))
print(resolve_path({"@id": "foo,i9999"}, path))
