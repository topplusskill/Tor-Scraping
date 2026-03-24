import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import requests


class BaseParser(ABC):
    """
    Abstract base class for site-specific parsers.

    Each ransomware leak site has different structure and requires custom
    parsing logic.  Subclasses MUST implement ``parse_directory()`` and
    ``get_download_url()``.  They MAY override ``download_file()`` and
    ``crawl_recursive()``.
    """

    SITE_NAME = "base"

    # Subclass tunables
    REQUEST_TIMEOUT = 60
    MAX_REQUEST_RETRIES = 3
    RETRY_BACKOFF = 5

    def __init__(self, session: requests.Session, **kwargs):
        self.session = session
        self.logger = logging.getLogger(f"{__name__}.{self.SITE_NAME}")
        # Statistics
        self._stats = {
            "requests": 0,
            "files_found": 0,
            "dirs_found": 0,
            "errors": 0,
        }
    
    @abstractmethod
    def parse_directory(self, url: str, **kwargs) -> Dict[str, List[str]]:
        """
        Parse a directory listing page and extract files and subdirectories.
        
        Args:
            url: The URL to parse
            **kwargs: Additional site-specific parameters
            
        Returns:
            Dict with 'files' and 'directories' lists
        """
        pass
    
    @abstractmethod
    def get_download_url(self, file_info: dict) -> str:
        """
        Get the actual download URL for a file.
        Some sites require token generation or API calls.
        
        Args:
            file_info: File information dict (structure varies by site)
            
        Returns:
            Direct download URL
        """
        pass
    
    def crawl_recursive(self, base_url: str, max_depth: int = 10, **kwargs) -> List[str]:
        """
        Recursively crawl directories and collect all file URLs.
        
        Args:
            base_url: Starting URL
            max_depth: Maximum recursion depth
            **kwargs: Additional site-specific parameters
            
        Returns:
            List of file URLs
        """
        all_files = []
        visited = set()
        queue = [(base_url, 0)]
        
        while queue:
            url, depth = queue.pop(0)
            
            if url in visited or depth > max_depth:
                continue
            
            visited.add(url)
            self.logger.info(f"Crawling: {url} (depth: {depth})")
            
            result = self.parse_directory(url, **kwargs)
            all_files.extend(result['files'])
            
            for directory in result['directories']:
                if directory not in visited:
                    queue.append((directory, depth + 1))
        
        return all_files
    
    # ─── Helpers ────────────────────────────────────────────────────

    def _get(self, url: str, **kwargs) -> requests.Response:
        """
        Wrapper around session.get with timeout default and stats tracking.
        """
        kwargs.setdefault("timeout", self.REQUEST_TIMEOUT)
        self._stats["requests"] += 1
        return self.session.get(url, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        """
        Wrapper around session.post with timeout default and stats tracking.
        """
        kwargs.setdefault("timeout", self.REQUEST_TIMEOUT)
        self._stats["requests"] += 1
        return self.session.post(url, **kwargs)

    def _retry_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Execute a request with retry on transient failures.

        Args:
            method: 'get' or 'post'
            url: Target URL
            **kwargs: Forwarded to requests

        Returns:
            Response on success, None after all retries exhausted
        """
        fn = self._get if method == "get" else self._post
        for attempt in range(self.MAX_REQUEST_RETRIES):
            try:
                resp = fn(url, **kwargs)
                resp.raise_for_status()
                return resp
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                backoff = self.RETRY_BACKOFF * (2 ** attempt)
                self.logger.warning(
                    f"Request failed ({attempt + 1}/{self.MAX_REQUEST_RETRIES}): {e}, "
                    f"retrying in {backoff}s..."
                )
                self._stats["errors"] += 1
                time.sleep(backoff)
            except requests.exceptions.HTTPError as e:
                self.logger.error(f"HTTP error: {e}")
                self._stats["errors"] += 1
                return None
        return None

    @property
    def stats(self) -> dict:
        """Return parser statistics."""
        return dict(self._stats)

    @classmethod
    def detect_site_type(cls, url: str) -> Optional[str]:
        """
        Detect which parser to use based on URL.

        Args:
            url: The target URL

        Returns:
            Site type string or None if unknown
        """
        url_lower = url.lower()

        if 'lockbit' in url_lower:
            return 'lockbit'
        elif 'dragonfor' in url_lower:
            return 'dragonforce'
        elif 'incblog' in url_lower or 'incransom' in url_lower:
            return 'incransom'

        return None
