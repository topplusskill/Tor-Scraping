import logging
import json
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, unquote
import requests

from .base import BaseParser


class INCRansomParser(BaseParser):
    """
    Parser for INC Ransom leak sites.
    
    INC Ransom uses a React SPA with REST API backend.
    Files are accessed through a CDN server.
    
    Known .onion addresses (from HAR analysis):
    - incblog6qu4y4mm4zvw5nrmue6qbwtgjsxpw6b7ixzssu36tsajldoad.onion (main blog)
    - incbacg6bfwtrlzwdbqc55gsfl763s3twdtwhp27dzuik6s6rwdcityd.onion (API server)
    - inccdnlqq4jffxjrynglk755gsqkorblvutyeyw7uaiyscc5ueiyxnid.onion (CDN/file server)
    
    API endpoints:
    - GET /api/v1/blog/get/disclosures/{id} - Get disclosure details
    - POST /api/v1/blog/get/folder - List directory contents
      Body: {"disclosureId": "...", "path": "./"}
    - POST /api/v1/blog/get/file - Download file
      Body: {"disclosureId": "...", "path": "./path/to/file.xlsx"}
    
    Note: disclosureId in API is different from URL ID. Must fetch disclosure first.
    
    CAPTCHA Bypass:
    1. Open the site in Tor Browser
    2. Solve CAPTCHA manually
    3. Export cookies to a file (use browser extension or DevTools)
    4. Pass cookies file path via --cookies argument
    """
    
    SITE_NAME = "incransom"
    
    # Known INC Ransom .onion addresses
    API_SERVER = "incbacg6bfwtrlzwdbqc55gsfl763s3twdtwhp27dzuik6s6rwdcityd.onion"
    CDN_SERVER = "inccdnlqq4jffxjrynglk755gsqkorblvutyeyw7uaiyscc5ueiyxnid.onion"
    
    def __init__(self, session: requests.Session, cookies_file: str = None):
        super().__init__(session)
        self.disclosure = None
        self.cdn_url = f"http://{self.CDN_SERVER}"
        self.api_url = f"http://{self.API_SERVER}"
        self.disclosure_id = None  # This is the internal ID, not URL ID
        self.url_id = None  # ID from URL
        
        # Load cookies if provided
        if cookies_file:
            self._load_cookies(cookies_file)
    
    def _load_cookies(self, cookies_file: str):
        """
        Load cookies from a JSON or Netscape format file.
        
        JSON format: [{"name": "...", "value": "...", "domain": "..."}, ...]
        Netscape format: domain\tTRUE\tpath\tFALSE\texpiry\tname\tvalue
        """
        import os
        
        if not os.path.exists(cookies_file):
            self.logger.error(f"Cookies file not found: {cookies_file}")
            return
        
        try:
            with open(cookies_file, 'r') as f:
                content = f.read().strip()
            
            # Try JSON format first
            if content.startswith('['):
                import json
                cookies = json.loads(content)
                for cookie in cookies:
                    self.session.cookies.set(
                        cookie.get('name'),
                        cookie.get('value'),
                        domain=cookie.get('domain', '')
                    )
                self.logger.info(f"Loaded {len(cookies)} cookies from JSON file")
            else:
                # Netscape format
                count = 0
                for line in content.split('\n'):
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain, _, path, _, _, name, value = parts[:7]
                        self.session.cookies.set(name, value, domain=domain)
                        count += 1
                self.logger.info(f"Loaded {count} cookies from Netscape file")
                
        except Exception as e:
            self.logger.error(f"Failed to load cookies: {e}")
    
    def _extract_disclosure_id(self, url: str) -> Optional[str]:
        """
        Extract disclosure ID from URL.
        
        URL format: /blog/disclosures/{id}
        """
        parts = url.rstrip('/').split('/')
        for i, part in enumerate(parts):
            if part == 'disclosures' and i + 1 < len(parts):
                return parts[i + 1]
        return None
    
    def _get_disclosure(self, url: str, password: str = None) -> Optional[Dict]:
        """
        Fetch disclosure details from API.
        
        Args:
            url: Disclosure page URL
            password: Optional password for protected disclosures
            
        Returns:
            Disclosure object with internal disclosureId
        """
        url_id = self._extract_disclosure_id(url)
        if not url_id:
            self.logger.error("Could not extract disclosure ID from URL")
            return None
        
        self.url_id = url_id
        
        try:
            # Use the API server, not the blog server
            api_endpoint = f"{self.api_url}/api/v1/blog/get/disclosures/{url_id}"
            
            params = {}
            if password:
                params['password'] = password
            
            self.logger.info(f"Fetching disclosure from: {api_endpoint}")
            response = self.session.get(api_endpoint, params=params, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('type') == True:
                payload = data.get('payload', [])
                # API returns a list of disclosures (parts)
                # Use the first one or let user choose
                if isinstance(payload, list) and len(payload) > 0:
                    # Get first disclosure part
                    first_disclosure = payload[0]
                    self.disclosure_id = first_disclosure.get('_id', url_id)
                    self.logger.info(f"Got {len(payload)} disclosure part(s), using first: {self.disclosure_id}")
                    
                    # Store all parts for reference
                    self.all_disclosures = payload
                    return first_disclosure
                elif isinstance(payload, dict):
                    self.disclosure_id = payload.get('_id', url_id)
                    self.logger.info(f"Got disclosure, internal ID: {self.disclosure_id}")
                    return payload
                else:
                    self.logger.error("Unexpected payload format")
                    return None
            else:
                self.logger.error(f"API error: {data.get('message', 'Unknown error')}")
                return None
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                self.logger.error("Access denied - may require CAPTCHA or password")
            else:
                self.logger.error(f"HTTP error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to get disclosure: {str(e)}")
            return None
    
    def _ensure_disclosure(self, url: str, **kwargs) -> bool:
        """
        Ensure we have disclosure details loaded.
        
        Args:
            url: Disclosure page URL
            **kwargs: May contain 'password' for protected disclosures
            
        Returns:
            True if disclosure is available
        """
        if self.disclosure and self.disclosure_id:
            return True
        
        password = kwargs.get('password')
        disclosure = self._get_disclosure(url, password)
        
        if not disclosure:
            return False
        
        self.disclosure = disclosure
        
        # CDN URL is hardcoded based on HAR analysis
        # The disclosure may contain cdn info but we use known working server
        self.logger.info(f"Using CDN server: {self.cdn_url}")
        
        return True
    
    def parse_directory(self, url: str, **kwargs) -> Dict[str, List[str]]:
        """
        Parse INC Ransom directory listing via API.
        
        Uses the CDN API to list folder contents.
        API expects: {"disclosureId": "...", "path": "./"}
        """
        path = kwargs.get('path', './')
        # Ensure path starts with ./
        if not path.startswith('./'):
            path = './' + path.lstrip('/')
        
        # Ensure we have disclosure info
        if not self._ensure_disclosure(url, **kwargs):
            self.logger.error("Could not load disclosure details")
            return {'files': [], 'directories': []}
        
        try:
            api_endpoint = f"{self.cdn_url}/api/v1/blog/get/folder"
            
            payload = {
                'disclosureId': self.disclosure_id,
                'path': path
            }
            
            self.logger.info(f"Listing folder: {path}")
            response = self.session.post(api_endpoint, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            files = []
            directories = []
            
            # Process response based on HAR analysis
            # Response: {"type": true, "message": "Success", "payload": [...]}
            if data.get('type') == True:
                items = data.get('payload', [])
                
                for item in items:
                    item_name = item.get('originalname', item.get('name', ''))
                    item_path = item.get('path', '')
                    is_folder = item.get('isFolder', False)
                    
                    if is_folder:
                        directories.append({
                            'path': item_path,
                            'name': item_name,
                            'url': url
                        })
                    else:
                        files.append({
                            'path': item_path,
                            'name': item_name,
                            'size': item.get('size', 0),
                            'url': url
                        })
                
                self.logger.info(f"Found {len(files)} files, {len(directories)} directories")
            else:
                self.logger.error(f"API error: {data.get('message', 'Unknown error')}")
            
            return {'files': files, 'directories': directories}
            
        except Exception as e:
            self.logger.error(f"Failed to parse directory: {str(e)}")
            return {'files': [], 'directories': []}
    
    def get_download_url(self, file_info: dict) -> str:
        """
        Generate download URL for a file.
        INC Ransom requires API call to CDN.
        """
        if not self.cdn_url:
            return ''
        
        return f"{self.cdn_url}/api/v1/blog/get/file"
    
    def download_file(self, file_info: dict, output_path: str) -> bool:
        """
        Download a file from INC Ransom CDN.
        
        API expects: {"disclosureId": "...", "path": "./path/to/file.xlsx"}
        
        Args:
            file_info: File information dict with path
            output_path: Local path to save file
            
        Returns:
            True if successful
        """
        import os
        
        if not self.cdn_url or not self.disclosure_id:
            self.logger.error("Disclosure not loaded")
            return False
        
        file_path = file_info.get('path', '')
        file_name = file_info.get('name', os.path.basename(file_path))
        
        try:
            api_endpoint = f"{self.cdn_url}/api/v1/blog/get/file"
            
            payload = {
                'disclosureId': self.disclosure_id,
                'path': file_path
            }
            
            self.logger.info(f"Downloading: {file_name}")
            response = self.session.post(
                api_endpoint,
                json=payload,
                timeout=300,
                stream=True
            )
            response.raise_for_status()
            
            # Create directory if needed
            dir_path = os.path.dirname(output_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # Stream to file
            total_size = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
            
            self.logger.info(f"Downloaded {file_name}: {total_size} bytes")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to download file: {str(e)}")
            return False
    
    def crawl_recursive(self, base_url: str, max_depth: int = 10, **kwargs) -> List[dict]:
        """
        Recursively crawl INC Ransom directories.
        
        Returns list of file info dicts.
        """
        all_files = []
        visited = set()
        queue = [('/', 0)]
        
        # Load disclosure first
        if not self._ensure_disclosure(base_url, **kwargs):
            self.logger.error("Could not load disclosure details")
            return []
        
        while queue:
            path, depth = queue.pop(0)
            
            if path in visited or depth > max_depth:
                continue
            
            visited.add(path)
            self.logger.info(f"Crawling: {path} (depth: {depth})")
            
            result = self.parse_directory(base_url, path=path, **kwargs)
            all_files.extend(result['files'])
            
            for directory in result['directories']:
                dir_path = directory.get('path', directory) if isinstance(directory, dict) else directory
                if dir_path not in visited:
                    queue.append((dir_path, depth + 1))
        
        return all_files
