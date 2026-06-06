from usi_scrapers.mapping import resolve_path, get_mapping
import usi_scrapers.transformers # ensures registration
data = {
    "gallery": [
        {"image": {"g_img_1500": "https://cdn.rp.pl/1.jpg"}},
        {"image": {"g_img_1500": "https://cdn.rp.pl/2.jpg"}},
    ]
}
rp_mapping = get_mapping("rp", "investment")
print(resolve_path(data, rp_mapping.get("gallery")))
