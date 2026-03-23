import logging
import re
import json
import time
import base64
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs, unquote, quote
from bs4 import BeautifulSoup
import requests

from .base import BaseParser


class DragonForceParser(BaseParser):
    """
    Parser for DragonForce ransomware leak sites.
    
    DragonForce uses a separate file server with JWT authentication.
    The main page contains an iframe pointing to the file server with a token.
    
    Known .onion addresses (from HAR analysis):
    - dragonforxxbp3awc7mzs5dkswrua3znqyx5roefmi4smjrsdi22xwqd.onion (main leak site)
    - dragonfscjlox5bnhgjv22m42anurgpyeh3bfmhokqtix3hsnsqajead.onion (file server - NEW)
    - fsguestuctexqqaoxuahuydfa6ovxuhtng66pgyr5gqcrsi7qgchpkad.onion (file server - OLD, often offline)
    
    File Server API (simple URL-based, no POST required):
    - /?path=...&token=JWT - List directory contents (returns HTML)
    - /download?path=...&token=JWT - Download file
    
    The token is extracted from iframe on the main page and contains:
    - deploy_uuid: unique identifier for the leak
    - website: victim domain
    - exp: expiration timestamp
    """
    
    SITE_NAME = "dragonforce"
    
    # Known DragonForce .onion addresses
    KNOWN_FILE_SERVERS = [
        "dragonfscjlox5bnhgjv22m42anurgpyeh3bfmhokqtix3hsnsqajead.onion",  # New, working
        "fsguestuctexqqaoxuahuydfa6ovxuhtng66pgyr5gqcrsi7qgchpkad.onion",  # Old, often offline
    ]
    
    # Refresh token 5 minutes before expiry
    TOKEN_REFRESH_MARGIN = 300
    
    def __init__(self, session: requests.Session):
        super().__init__(session)
        self.file_server_url = None
        self.token = None
        self.token_exp = 0
        self.deploy_uuid = None
        self.main_site_url = None
        self.website = None
    
    def _extract_iframe_info(self, url: str) -> Optional[Dict]:
        """
        Extract file server URL and token from the main page iframe.
        
        Args:
            url: Main DragonForce page URL
            
        Returns:
            Dict with file_server_url, token, and deploy_uuid
        """
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            iframe = soup.find('iframe', class_='visor-content')
            
            if not iframe or not iframe.get('src'):
                self.logger.error("No iframe found on page")
                return None
            
            iframe_src = iframe['src']
            
            # Parse the iframe URL
            parsed = urlparse(iframe_src)
            query_params = parse_qs(parsed.query)
            
            token = query_params.get('token', [None])[0]
            if not token:
                self.logger.error("No token found in iframe URL")
                return None
            
            # Decode JWT payload to get deploy_uuid and expiry
            token_exp = 0
            deploy_uuid = None
            try:
                payload_b64 = token.split('.')[1]
                padding = 4 - len(payload_b64) % 4
                if padding != 4:
                    payload_b64 += '=' * padding
                
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                deploy_uuid = payload.get('deploy_uuid')
                token_exp = payload.get('exp', 0)
                self.logger.info(f"Token expires at {token_exp} (in {token_exp - time.time():.0f}s)")
            except Exception as e:
                self.logger.warning(f"Could not decode JWT: {e}")
            
            file_server_url = f"{parsed.scheme}://{parsed.netloc}"
            
            return {
                'file_server_url': file_server_url,
                'token': token,
                'deploy_uuid': deploy_uuid,
                'token_exp': token_exp
            }
            
        except Exception as e:
            self.logger.error(f"Failed to extract iframe info: {str(e)}")
            return None
    
    def _ensure_token(self, main_url: str) -> bool:
        """
        Ensure we have a valid (non-expired) token for the file server.
        Automatically refreshes token if it's about to expire.
        """
        if self.token and self.file_server_url:
            if self.token_exp and time.time() < (self.token_exp - self.TOKEN_REFRESH_MARGIN):
                return True
            self.logger.info("Token expired or expiring soon, refreshing...")
        
        info = self._extract_iframe_info(main_url)
        if not info:
            return False
        
        self.file_server_url = info['file_server_url']
        self.token = info['token']
        self.deploy_uuid = info['deploy_uuid']
        self.token_exp = info.get('token_exp', 0)
        
        return True
    
    def parse_directory(self, url: str, **kwargs) -> Dict[str, List[str]]:
        """
        Parse DragonForce directory listing.
        
        For the initial URL, extracts token from iframe.
        Then uses the file server to list contents via GET request.
        
        File server returns HTML with links to files and directories.
        """
        main_url = kwargs.get('main_url', url)
        path = kwargs.get('path', '/')
        
        # Ensure we have authentication
        if not self._ensure_token(main_url):
            self.logger.error("Could not obtain authentication token")
            return {'files': [], 'directories': []}
        
        try:
            # DragonForce file server uses simple GET with query params
            # URL format: /?path=...&token=JWT
            list_url = f"{self.file_server_url}/?path={quote(path)}&token={self.token}"
            
            self.logger.info(f"Listing directory: {path}")
            response = self.session.get(list_url, timeout=60)
            response.raise_for_status()
            
            # Parse HTML response to extract files and directories
            soup = BeautifulSoup(response.content, 'lxml')
            
            files = []
            directories = []
            
            # Find all links - they contain path info
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Skip navigation links
                if href in ['#', '..', '../'] or href.startswith('javascript:'):
                    continue
                
                # Parse the href to extract path
                parsed_href = urlparse(href)
                query = parse_qs(parsed_href.query)
                
                item_path = query.get('path', [''])[0]
                if not item_path:
                    continue
                
                item_path = unquote(item_path)
                
                # Determine if it's a file or directory
                # Download links go to /download, directory links go to /
                if '/download' in href:
                    # It's a file
                    item_name = item_path.split('/')[-1]
                    files.append({
                        'path': item_path,
                        'name': item_name,
                        'url': url,
                        'main_url': main_url
                    })
                else:
                    # It's a directory
                    item_name = item_path.rstrip('/').split('/')[-1]
                    directories.append({
                        'path': item_path,
                        'name': item_name,
                        'url': url,
                        'main_url': main_url
                    })
            
            self.logger.info(f"Found {len(files)} files, {len(directories)} directories")
            return {'files': files, 'directories': directories}
            
        except Exception as e:
            self.logger.error(f"Failed to parse {url}: {str(e)}")
            return {'files': [], 'directories': []}
    
    def get_download_url(self, file_info: dict) -> str:
        """
        Generate download URL for a file.
        DragonForce uses simple GET with path and token.
        """
        if not self.file_server_url or not self.token:
            return ''
        
        file_path = file_info.get('path', '')
        return f"{self.file_server_url}/download?path={quote(file_path)}&token={self.token}"
    
    DOWNLOAD_MAX_RETRIES = 3
    DOWNLOAD_BACKOFF = 5  # seconds
    
    def download_file(self, file_info: dict, output_path: str) -> bool:
        """
        Download a file from DragonForce with retry on transient failures.
        
        Uses simple GET request: /download?path=...&token=JWT
        Retries on timeout/connection errors with exponential backoff.
        """
        import os
        
        file_path = file_info.get('path', '')
        file_name = file_info.get('name', os.path.basename(file_path))
        main_url = file_info.get('main_url', '')
        
        for attempt in range(self.DOWNLOAD_MAX_RETRIES):
            # Refresh token if needed before each attempt
            if not self._ensure_token(main_url):
                self.logger.error("No authentication token available")
                return False
            
            try:
                download_url = self.get_download_url(file_info)
                
                self.logger.info(f"Downloading: {file_name}")
                response = self.session.get(
                    download_url,
                    timeout=300,
                    stream=True
                )
                response.raise_for_status()
                
                dir_path = os.path.dirname(output_path)
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)
                
                total_size = 0
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)
                
                self.logger.info(f"Downloaded {file_name}: {total_size} bytes")
                return True
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                backoff = self.DOWNLOAD_BACKOFF * (2 ** attempt)
                self.logger.warning(
                    f"Download failed ({attempt + 1}/{self.DOWNLOAD_MAX_RETRIES}): {e}, "
                    f"retrying in {backoff}s..."
                )
                time.sleep(backoff)
            except Exception as e:
                self.logger.error(f"Failed to download {file_name}: {str(e)}")
                return False
        
        self.logger.error(f"Download failed after {self.DOWNLOAD_MAX_RETRIES} retries: {file_name}")
        return False
    
    def crawl_recursive(self, base_url: str, max_depth: int = 10, **kwargs) -> List[dict]:
        """
        Recursively crawl DragonForce directories.
        
        Returns list of file info dicts instead of URLs since
        DragonForce requires special handling for downloads.
        """
        all_files = []
        visited = set()
        queue = [('/', 0)]
        
        # Extract token from main URL first
        if not self._ensure_token(base_url):
            self.logger.error("Could not obtain authentication token")
            return []
        
        while queue:
            path, depth = queue.pop(0)
            
            if path in visited or depth > max_depth:
                continue
            
            visited.add(path)
            self.logger.info(f"Crawling: {path} (depth: {depth})")
            
            result = self.parse_directory(base_url, main_url=base_url, path=path)
            all_files.extend(result['files'])
            
            for directory in result['directories']:
                dir_path = directory.get('path', directory) if isinstance(directory, dict) else directory
                if dir_path not in visited:
                    queue.append((dir_path, depth + 1))
        
        return all_files
