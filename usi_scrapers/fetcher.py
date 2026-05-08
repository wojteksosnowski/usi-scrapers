import logging
import time
import json
from urllib.parse import urlparse
from datetime import datetime, date
from typing import Optional
from curl_cffi import requests as curl_requests
import requests as std_requests

from .models import ScraperConfig

logger = logging.getLogger("usi_scrapers.fetcher")

class Fetcher:
    """
    Centralized fetcher for usi-scrapers.
    Supports direct requests, impersonation (via curl_cffi), and ScraperAPI fallback.
    Includes rate-limiting per domain to avoid blocking.
    """
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.session = curl_requests.Session()
        self.last_fetch_times = {} # domain -> timestamp

    def _get_domain(self, url: str) -> str:
        """Extracts the base domain from a URL (e.g., otodom.pl)."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def _apply_rate_limit(self, domain: str):
        """Applies a delay if the last request to the same domain was too recent."""
        if not domain:
            return

        delay = self.config.fetch_delays.get(domain, self.config.fetch_delays.get("default", 0.5))
        last_time = self.last_fetch_times.get(domain, 0)
        
        elapsed = time.time() - last_time
        if elapsed < delay:
            wait_time = delay - elapsed
            logger.info(f"Rate limiting: waiting {wait_time:.2f}s for {domain}")
            time.sleep(wait_time)
        
        # We update the time before the request starts to be safe 
        # (if request fails, we still want to maintain the gap)
        self.last_fetch_times[domain] = time.time()

    def _get_usage(self):
        """Loads and updates usage stats from the configured path."""
        path = self.config.usage_stats_path
        if not path or not path.exists():
            # Default fallback if file missing or path not provided
            return {"used": 0, "limit": self.config.scraperapi_limit, "reset_date": "2026-05-11"}
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
                stats = data.get("scraperapi", {})
                
                # Check for reset
                reset_date_str = stats.get("reset_date")
                if reset_date_str:
                    reset_date = datetime.strptime(reset_date_str, "%Y-%m-%d").date()
                    if date.today() >= reset_date:
                        logger.info("ScraperAPI reset date reached. Resetting counter.")
                        stats["used"] = 0
                        # Set next reset date (naive +1 month approach)
                        new_month = reset_date.month + 1
                        new_year = reset_date.year
                        if new_month > 12:
                            new_month = 1
                            new_year += 1
                        stats["reset_date"] = date(new_year, new_month, reset_date.day).isoformat()
                        self._save_usage(stats)
                return stats
        except Exception as e:
            logger.error(f"Error reading usage stats: {e}")
            return {"used": 0, "limit": self.config.scraperapi_limit, "reset_date": "2026-05-11"}

    def _save_usage(self, stats):
        """Saves usage stats."""
        path = self.config.usage_stats_path
        if not path:
            return
            
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Load full data to preserve other fields
            full_data = {}
            if path.exists():
                with open(path, "r") as f:
                    full_data = json.load(f)
            
            full_data["scraperapi"] = stats
            with open(path, "w") as f:
                json.dump(full_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving usage stats: {e}")

    def fetch(self, url: str, use_impersonate: bool = True, use_scraperapi: bool = True, timeout: int = 30) -> Optional[str]:
        """
        Fetches HTML content from a URL using the best available strategy.
        """
        domain = self._get_domain(url)
        self._apply_rate_limit(domain)

        # Strategy 1: Impersonate (curl_cffi)
        if use_impersonate:
            try:
                logger.info(f"Fetching {url} using impersonation (chrome)")
                # 'chrome' impersonation handles JA3 and common headers
                response = self.session.get(url, impersonate="chrome", timeout=timeout)
                response.raise_for_status()
                logger.info(f"Successfully fetched {url} ({len(response.text)} bytes)")
                return response.text
            except Exception as e:
                logger.warning(f"Impersonate fetch failed for {url}: {e}")
                if not use_scraperapi:
                    return None

        # Strategy 2: ScraperAPI Fallback
        if use_scraperapi and self.config.scraperapi_key:
            stats = self._get_usage()
            used = stats.get("used", 0)
            limit = stats.get("limit", self.config.scraperapi_limit)
            
            if used >= limit:
                logger.error(f"ScraperAPI limit reached ({used}/{limit}). Skipping fallback.")
                return None

            try:
                logger.info(f"Fetching {url} via ScraperAPI fallback (Usage: {used + 1}/{limit})")
                proxy_url = "http://api.scraperapi.com"
                params = {
                    "api_key": self.config.scraperapi_key,
                    "url": url,
                    "render": "false" # Try without rendering first
                }
                response = std_requests.get(proxy_url, params=params, timeout=timeout + 30)
                response.raise_for_status()
                
                # Increment usage on success
                stats["used"] = used + 1
                self._save_usage(stats)
                
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
