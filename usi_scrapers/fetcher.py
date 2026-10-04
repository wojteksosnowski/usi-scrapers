import logging
import time
import json
from urllib.parse import urlparse
from typing import Callable, Optional
from curl_cffi import requests as curl_requests
import requests as std_requests

from .models import ScraperConfig

import logging
logger = logging.getLogger("usi_scrapers.fetcher")


SCRAPERAPI_ACCOUNT_URL = "https://api.scraperapi.com/account"

# Statusy oznaczające, że zasób nie istnieje — ScraperAPI nie ma po co ponawiać (marnuje kredyt i ruch).
GONE_STATUSES = (404, 410)
# Statusy sugerujące throttling/blokadę — domena dostaje przerwę (cooldown) przed kolejnymi żądaniami bezpośrednimi.
THROTTLE_STATUSES = (403, 429)
COOLDOWN_BASE_S = 30.0
COOLDOWN_MAX_S = 300.0
CREDITS_CACHE_TTL_S = 60.0
# Wyłącznik: po tylu kolejnych 403/429 z jednej domeny przestajemy wysyłać do niej żądania bezpośrednie.
BREAKER_THRESHOLD = 3
BREAKER_OPEN_S = 900.0


def _status_of(exc: Exception) -> Optional[int]:
    """Wyciąga kod HTTP z wyjątku (curl_cffi/requests HTTPError niosą .response)."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def _retry_after_of(exc: Exception) -> Optional[float]:
    try:
        value = exc.response.headers.get("Retry-After")  # type: ignore[union-attr]
        return float(value) if value is not None else None
    except Exception:
        return None


class Fetcher:
    """
    Centralized fetcher for usi-scrapers.
    Supports direct requests, impersonation (via curl_cffi), and ScraperAPI fallback.
    Includes rate-limiting per domain to avoid blocking.
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self.session = curl_requests.Session()
        self.last_fetch_times: dict = {}
        self.last_fetch_vector: Optional[str] = None
        self.last_status: Optional[int] = None
        # Opcjonalny podgląd: wołany z adresem przed każdym żądaniem (np. do logu zadania w UI). Nie zmienia ruchu.
        self.on_request: Optional[Callable[[str], None]] = None
        # Cooldown per domena po 403/429: {domain: (until_ts, kolejna_przerwa_s)}
        self._cooldowns: dict = {}
        self._credits_cache: Optional[tuple] = None  # (timestamp, credits_left)
        # Wyłącznik per domena: {domain: kolejne_odmowy} i {domain: open_until_ts}
        self._throttle_streak: dict = {}
        self._breaker_until: dict = {}
        # Statystyki per domena: {domain: {"direct_ok": n, "direct_fail": n, "scraperapi": n, "breaker_skips": n, "status": {kod: n}}}
        self.stats: dict = {}

    def _stat(self, domain: str) -> dict:
        return self.stats.setdefault(
            domain, {"direct_ok": 0, "direct_fail": 0, "scraperapi": 0, "breaker_skips": 0, "status": {}}
        )

    def breaker_open(self, domain: str) -> bool:
        return time.time() < self._breaker_until.get(domain, 0)

    def snapshot(self) -> dict:
        """Stan Fetchera do podglądu (bez żadnych żądań HTTP): statystyki, cooldowny i wyłączniki per domena."""
        now = time.time()
        domains = set(self.stats) | set(self._cooldowns) | set(self._breaker_until) | set(self._throttle_streak)
        out = {}
        for domain in sorted(domains):
            cooldown_until = (self._cooldowns.get(domain) or (0, 0))[0]
            stat = self.stats.get(domain) or {}
            out[domain] = {
                "direct_ok": stat.get("direct_ok", 0),
                "direct_fail": stat.get("direct_fail", 0),
                "scraperapi": stat.get("scraperapi", 0),
                "breaker_skips": stat.get("breaker_skips", 0),
                "status": dict(stat.get("status", {})),
                "throttle_streak": self._throttle_streak.get(domain, 0),
                "cooldown_remaining_s": max(0, round(cooldown_until - now)),
                "breaker_open": self.breaker_open(domain),
                "breaker_remaining_s": max(0, round(self._breaker_until.get(domain, 0) - now)),
            }
        credits = self._credits_cache[1] if self._credits_cache else None
        return {
            "domains": out,
            "scraperapi_credits_cached": credits,
            "last_status": self.last_status,
            "last_fetch_vector": self.last_fetch_vector,
        }

    def _get_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def _apply_rate_limit(self, domain: str):
        if not domain:
            return
        delay = self.config.fetch_delays.get(domain, self.config.fetch_delays.get("default", 0.5))
        last_time = self.last_fetch_times.get(domain, 0)
        elapsed = time.time() - last_time
        if elapsed < delay:
            wait_time = delay - elapsed
            logger.info(f"Rate limiting: waiting {wait_time:.2f}s for {domain}")
            time.sleep(wait_time)
        self.last_fetch_times[domain] = time.time()

    def _wait_cooldown(self, domain: str):
        """Czeka do końca przerwy nałożonej na domenę po 403/429 (jeśli jest aktywna)."""
        entry = self._cooldowns.get(domain)
        if not entry:
            return
        remaining = entry[0] - time.time()
        if remaining > 0:
            logger.warning(f"Cooldown: waiting {remaining:.0f}s for {domain} after throttling response")
            time.sleep(remaining)

    def _register_throttle(self, domain: str, retry_after: Optional[float] = None):
        """Nakłada (rosnącą) przerwę na domenę; szanuje Retry-After, ale nie dłużej niż COOLDOWN_MAX_S."""
        previous = self._cooldowns.get(domain)
        pause = min((previous[1] * 2) if previous else COOLDOWN_BASE_S, COOLDOWN_MAX_S)
        if retry_after is not None and retry_after > 0:
            pause = min(max(pause, retry_after), COOLDOWN_MAX_S)
        self._cooldowns[domain] = (time.time() + pause, pause)
        streak = self._throttle_streak.get(domain, 0) + 1
        self._throttle_streak[domain] = streak
        if streak >= BREAKER_THRESHOLD:
            self._breaker_until[domain] = time.time() + BREAKER_OPEN_S
            logger.error(
                f"Circuit breaker OPEN for {domain}: {streak} consecutive 403/429. "
                f"No direct requests for {BREAKER_OPEN_S:.0f}s."
            )
        logger.warning(f"Throttling detected for {domain}; next direct request delayed by {pause:.0f}s")

    def _get_credits_left(self) -> Optional[int]:
        """Queries ScraperAPI account endpoint for remaining credits (cached for CREDITS_CACHE_TTL_S)."""
        if self._credits_cache and time.time() - self._credits_cache[0] < CREDITS_CACHE_TTL_S:
            return self._credits_cache[1]
        try:
            response = std_requests.get(
                SCRAPERAPI_ACCOUNT_URL,
                params={"api_key": self.config.scraperapi_key},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            credits_left = data.get("creditsLeft")
            logger.info(f"ScraperAPI credits remaining: {credits_left}/{data.get('requestLimit')}")
            self._credits_cache = (time.time(), credits_left)
            return credits_left
        except Exception as e:
            logger.warning(f"Could not fetch ScraperAPI account info: {e}")
            return None

    def fetch(self, url: str, use_impersonate: bool = True, use_scraperapi: bool = True, timeout: int = 30) -> Optional[str]:
        """
        Fetches HTML content from a URL using the best available strategy.
        Strategy 1: curl_cffi with Chrome impersonation (JA3 fingerprint bypass).
        Strategy 2: ScraperAPI fallback if impersonation fails and credits are available.
        """
        self.last_fetch_vector = None
        self.last_status = None
        domain = self._get_domain(url)
        stat = self._stat(domain)
        if self.on_request:
            try:
                self.on_request(url)
            except Exception:
                pass
        direct = use_impersonate and not self.breaker_open(domain)
        if use_impersonate and not direct:
            stat["breaker_skips"] += 1
            logger.warning(f"Circuit breaker open for {domain}; skipping direct request to {url}")
            if not use_scraperapi:
                return None
        if direct:
            self._wait_cooldown(domain)
        if direct or not use_impersonate:  # przy otwartym wyłączniku nie dotykamy domeny, więc nie czekamy
            self._apply_rate_limit(domain)

        if direct:
            try:
                headers = {}
                if domain == "rynekpierwotny.pl":
                    headers = {
                        "Accept": "application/json, text/plain, */*",
                        "Referer": "https://rynekpierwotny.pl/s/nowe-mieszkania/",
                        "sec-fetch-dest": "empty",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-site": "same-origin",
                    }

                logger.info(f"Fetching {url} using impersonation (chrome)")
                response = self.session.get(url, impersonate="chrome", timeout=timeout, headers=headers)
                response.raise_for_status()
                logger.info(f"Successfully fetched {url} ({len(response.text)} bytes)")
                self.last_fetch_vector = "curl_cffi"
                self._cooldowns.pop(domain, None)
                self._throttle_streak.pop(domain, None)
                self._breaker_until.pop(domain, None)
                stat["direct_ok"] += 1
                return response.text
            except Exception as e:
                status = _status_of(e)
                self.last_status = status
                stat["direct_fail"] += 1
                stat["status"][str(status)] = stat["status"].get(str(status), 0) + 1
                logger.warning(f"Impersonate fetch failed for {url}: {e}")
                if status in THROTTLE_STATUSES:
                    self._register_throttle(domain, _retry_after_of(e))
                elif status in GONE_STATUSES:
                    logger.info(f"{url} returned {status} (gone); skipping ScraperAPI fallback")
                    return None
                if not use_scraperapi:
                    return None

        if use_scraperapi and self.config.scraperapi_key:
            credits_left = self._get_credits_left()
            if credits_left is not None and credits_left <= 0:
                logger.error("ScraperAPI credits exhausted. Skipping fallback.")
                return None

            try:
                logger.info(f"Fetching {url} via ScraperAPI fallback")
                response = std_requests.get(
                    "http://api.scraperapi.com",
                    params={"api_key": self.config.scraperapi_key, "url": url, "render": "false"},
                    timeout=timeout + 30,
                )
                response.raise_for_status()
                self.last_fetch_vector = "scraperapi"
                stat["scraperapi"] += 1
                if self._credits_cache and self._credits_cache[1] is not None:
                    self._credits_cache = (self._credits_cache[0], self._credits_cache[1] - 1)
                return response.text
            except Exception as e:
                logger.error(f"ScraperAPI fallback failed for {url}: {e}")

        return None

    def fetch_json(self, url: str, **kwargs) -> Optional[dict]:
        """Fetches and parses JSON from a URL."""
        content = self.fetch(url, **kwargs)
        if content:
            try:
                return json.loads(content)
            except Exception as e:
                logger.error(f"Failed to parse JSON from {url}: {e}")
        return None
