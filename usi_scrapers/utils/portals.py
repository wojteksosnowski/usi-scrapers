import json
from pathlib import Path
from typing import Any

_PORTALS_PATH = Path(__file__).parent.parent / "portals.json"
PORTALS: dict[str, dict[str, Any]] = json.loads(_PORTALS_PATH.read_text(encoding="utf-8"))

# alias → canonical prefix mapping built from JSON
_ALIAS_MAP: dict[str, str] = {}
for _prefix, _cfg in PORTALS.items():
    for _alias in _cfg.get("aliases", []):
        _ALIAS_MAP[_alias] = _prefix


def resolve_prefix(alias: str) -> str:
    """'otodom' → 'oto', 'tabelaofert' → 'to'. Raises ValueError for unknown alias."""
    key = alias.lower()
    if key in _ALIAS_MAP:
        return _ALIAS_MAP[key]
    raise ValueError(f"Unknown portal alias: {alias!r}. Known: {sorted(_ALIAS_MAP)}")


def get_portal(prefix: str) -> dict[str, Any]:
    """Returns full portal config dict for a canonical prefix. Raises ValueError if unknown."""
    if prefix not in PORTALS:
        raise ValueError(f"Unknown portal prefix: {prefix!r}. Known: {list(PORTALS)}")
    return PORTALS[prefix]


def portal_base_url(prefix: str) -> str:
    """Returns base URL for portal, e.g. 'https://rynekpierwotny.pl'."""
    return get_portal(prefix)["base_url"]


def portal_api_url(prefix: str, endpoint: str, **kwargs: str) -> str:
    """
    Builds a full API URL from portals.json templates.
    portal_api_url('rp', 'offer_detail', offer_id='123')
    → 'https://rynekpierwotny.pl/api/v2/offers/offer/123/?s=offer-detail'
    """
    cfg = get_portal(prefix)
    api = cfg.get("api", {})
    if endpoint not in api:
        raise ValueError(f"Portal '{prefix}' has no API endpoint '{endpoint}'. Available: {list(api)}")
    path = api[endpoint].format(**kwargs)
    return cfg["base_url"] + path


def portal_url(prefix: str, pattern: str, **kwargs: str) -> str:
    """
    Builds an investment/developer URL from portals.json url_patterns.
    portal_url('rp', 'investment', dev_slug='abc', inv_slug='xyz', offer_id='123')
    → 'https://rynekpierwotny.pl/oferty/abc/xyz-123/'
    """
    cfg = get_portal(prefix)
    patterns = cfg.get("url_patterns", {})
    if pattern not in patterns:
        raise ValueError(f"Portal '{prefix}' has no url_pattern '{pattern}'. Available: {list(patterns)}")
    path = patterns[pattern].format(**kwargs)
    return cfg["base_url"] + path


def all_prefixes() -> list[str]:
    """Returns canonical portal prefixes: ['rp', 'oto', 'to']."""
    return list(PORTALS)


def default_fetch_delays() -> dict[str, float]:
    """
    Builds fetch_delays dict for ScraperConfig from portals.json.
    Returns {'rynekpierwotny.pl': 0.5, 'otodom.pl': 1.0, 'tabelaofert.pl': 0.5, 'default': 0.5}
    """
    delays: dict[str, float] = {}
    for cfg in PORTALS.values():
        domain = cfg.get("rate_limit_domain")
        rate = cfg.get("default_rate_limit", 0.5)
        if domain:
            delays[domain] = rate
    delays.setdefault("default", 0.5)
    return delays
