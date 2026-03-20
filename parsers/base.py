import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import requests


class BaseParser(ABC):
    """
    Abstract base class for site-specific parsers.
    Each ransomware leak site has different structure and requires custom parsing logic.
    """
    
    SITE_NAME = "base"
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.logger = logging.getLogger(f"{__name__}.{self.SITE_NAME}")
    
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
