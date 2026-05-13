import logging
import time
import json
from urllib.parse import urlparse
from typing import Optional
from curl_cffi import requests as curl_requests
import requests as std_requests

from .models import ScraperConfig

from . import get_logger

logger = get_logger("usi_scrapers.fetcher")

SCRAPERAPI_ACCOUNT_URL = "https://api.scraperapi.com/account"


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

    def _get_credits_left(self) -> Optional[int]:
        """Queries ScraperAPI account endpoint for remaining credits."""
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
        domain = self._get_domain(url)
        self._apply_rate_limit(domain)

        if use_impersonate:
            try:
                logger.info(f"Fetching {url} using impersonation (chrome)")
                response = self.session.get(url, impersonate="chrome", timeout=timeout)
                response.raise_for_status()
                logger.info(f"Successfully fetched {url} ({len(response.text)} bytes)")
                return response.text
            except Exception as e:
                logger.warning(f"Impersonate fetch failed for {url}: {e}")
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
