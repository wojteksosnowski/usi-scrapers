from usi_scrapers.mapping import resolve_path
data = {"gallery": [{"image": {"g_img_1500": "https://cdn.rp.pl/1.jpg"}}]}
print(resolve_path(data, "."))
