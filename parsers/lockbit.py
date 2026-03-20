import logging
from typing import List, Dict
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests

from .base import BaseParser


class LockbitParser(BaseParser):
    """
    Parser for Lockbit ransomware leak sites.
    These sites use Apache-style directory listings with standard HTML structure.
    """
    
    SITE_NAME = "lockbit"
    
    def parse_directory(self, url: str, **kwargs) -> Dict[str, List[str]]:
        """
        Parse Apache-style directory listing.
        Filters out navigation links and sorting parameters.
        """
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            links = soup.find_all('a')
            
            files = []
            directories = []
            
            for link in links:
                href = link.get('href')
                if not href:
                    continue
                
                # Skip query parameters and anchors (Apache sorting links)
                if href.startswith('?') or href.startswith('#'):
                    continue
                
                # Skip navigation links
                if href in ['../', '../', '/', '/secret/']:
                    continue
                
                # Skip external links
                if href.startswith('http') and not href.startswith(url.split('/secret/')[0]):
                    continue
                
                full_url = urljoin(url, href)
                
                # Classify as directory or file based on trailing slash
                if href.endswith('/'):
                    directories.append(full_url)
                else:
                    files.append(full_url)
            
            return {'files': files, 'directories': directories}
            
        except Exception as e:
            self.logger.error(f"Failed to parse {url}: {str(e)}")
            return {'files': [], 'directories': []}
    
    def get_download_url(self, file_info: dict) -> str:
        """
        For Lockbit, the file URL is direct - no transformation needed.
        """
        if isinstance(file_info, str):
            return file_info
        return file_info.get('url', '')
