import logging
import json
import os
from typing import List, Dict
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests

from .base import BaseParser


class LockbitParser(BaseParser):
    """
    Parser for Lockbit ransomware leak sites.
    These sites use Apache-style directory listings with standard HTML structure.
    
    Changed behavior: Now downloads ONLY unpacked files from unpack/ directory.
    Skips zip archives to avoid incomplete downloads.
    """
    
    SITE_NAME = "lockbit"
    
    # Only download from unpack directory, skip archives
    PREFER_UNPACK = True
    SKIP_ARCHIVES = True  # Skip .zip files
    
    def parse_directory(self, url: str, **kwargs) -> Dict[str, List[str]]:
        """
        Parse Apache-style directory listing.
        
        New behavior:
        - If we're at root level, only follow 'unpack/' directory
        - Skip all .zip archives
        - Download only unpacked files
        """
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            links = soup.find_all('a')
            
            files = []
            directories = []
            
            # Check if we're in unpack directory
            in_unpack = '/unpack/' in url or url.endswith('/unpack')
            
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
                    # If not in unpack yet, only follow unpack directory
                    if not in_unpack and self.PREFER_UNPACK:
                        if 'unpack' in href.lower():
                            self.logger.info(f"Following unpack directory: {href}")
                            directories.append(full_url)
                        else:
                            self.logger.info(f"Skipping non-unpack directory: {href}")
                    else:
                        # Already in unpack, follow all subdirectories
                        directories.append(full_url)
                else:
                    # Skip archive files if configured
                    if self.SKIP_ARCHIVES and href.endswith('.zip'):
                        self.logger.debug(f"Skipping archive: {href}")
                        continue
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
