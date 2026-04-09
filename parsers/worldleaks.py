import logging
import json
from typing import List, Dict
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
import requests
import urllib3

# Disable SSL warnings for .onion sites
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .base import BaseParser


class WorldLeaksParser(BaseParser):
    """
    Parser for World Leaks ransomware leak site.
    Uses REST API for file navigation and downloads.
    
    API endpoints:
    - GET /api/companies - list all companies
    - GET /api/companies/{id}/storages/dirs - root directories
    - GET /api/companies/{id}/storages/dirs/{path} - subdirectories
    - GET /api/companies/{id}/storages/files/{path}/{filename} - download file
    """
    
    SITE_NAME = "worldleaks"
    
    def __init__(self, session: requests.Session, **kwargs):
        super().__init__(session, **kwargs)
        self.company_id = None
        self.base_api_url = None
    
    def _extract_company_id(self, url: str) -> str:
        """Extract company ID from URL."""
        # URL format: https://worldleaks.../companies/7731149748/storage
        parts = url.split('/companies/')
        if len(parts) > 1:
            company_id = parts[1].split('/')[0]
            return company_id
        return None
    
    def parse_directory(self, url: str, **kwargs) -> Dict[str, List[str]]:
        """
        Parse World Leaks directory using REST API.
        
        Args:
            url: Company storage URL or API endpoint
            
        Returns:
            Dict with 'files' and 'directories' lists
        """
        try:
            # Extract company ID and setup API base URL
            if not self.company_id:
                self.company_id = self._extract_company_id(url)
                if not self.company_id:
                    self.logger.error(f"Could not extract company ID from URL: {url}")
                    return {'files': [], 'directories': []}
                
                # Extract base URL
                base_url = url.split('/companies/')[0]
                self.base_api_url = f"{base_url}/api/companies/{self.company_id}"
                self.logger.info(f"Company ID: {self.company_id}")
            
            # Determine current path - extract from URL if it's an API URL
            if '/storages/dirs/' in url:
                # Extract path from API URL
                # Format: .../api/companies/{id}/storages/dirs/{path}
                path_part = url.split('/storages/dirs/')[-1]
                from urllib.parse import unquote
                current_path = '/' + unquote(path_part) if path_part else '/'
            else:
                current_path = kwargs.get('path', '/')
            
            # Use the URL directly if it's already an API URL
            if url.startswith(self.base_api_url):
                api_url = url
            else:
                # Build API URL for directory listing
                if current_path == '/':
                    api_url = f"{self.base_api_url}/storages/dirs"
                else:
                    # URL encode the path
                    encoded_path = quote(current_path.lstrip('/'), safe='/')
                    api_url = f"{self.base_api_url}/storages/dirs/{encoded_path}"
            
            self.logger.info(f"Fetching: {api_url}")
            
            # Make API request (disable SSL verification for .onion)
            response = self.session.get(api_url, timeout=60, verify=False)
            response.raise_for_status()
            
            data = response.json()
            
            # Log statistics
            total_files = data.get('total_files', 0)
            total_size = data.get('total_size', 0)
            path = data.get('path', current_path)
            self.logger.info(
                f"Path: {path} | Files: {total_files} | "
                f"Size: {total_size / (1024**3):.2f} GB"
            )
            
            files = []
            directories = []
            
            # Process subdirectories
            for dir_info in data.get('dirs', []):
                dir_name = dir_info['name']
                # Build full path for subdirectory
                if path == '/':
                    subdir_path = f"/{dir_name}"
                else:
                    subdir_path = f"{path}/{dir_name}"
                
                # Create directory URL (will be used for recursive crawling)
                dir_url = f"{self.base_api_url}/storages/dirs/{quote(subdir_path.lstrip('/'), safe='/')}"
                directories.append(dir_url)
                
                self.logger.debug(
                    f"Dir: {dir_name} | Files: {dir_info.get('files', 0)} | "
                    f"Size: {dir_info.get('size', 0) / (1024**3):.2f} GB"
                )
            
            # Process files in current directory
            for file_info in data.get('files', []):
                file_name = file_info['name']
                file_size = file_info.get('size', 0)
                
                # Build file download URL
                if path == '/':
                    file_path = f"/{file_name}"
                else:
                    file_path = f"{path}/{file_name}"
                
                # File download URL format
                file_url = f"{self.base_api_url}/storages/files/{quote(file_path.lstrip('/'), safe='/')}"
                
                files.append({
                    'url': file_url,
                    'name': file_name,
                    'size': file_size,
                    'path': file_path
                })
                
                self.logger.debug(f"File: {file_name} | Size: {file_size / (1024**2):.2f} MB")
            
            return {'files': files, 'directories': directories}
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error: {e}")
            return {'files': [], 'directories': []}
        except Exception as e:
            self.logger.error(f"Failed to parse {url}: {str(e)}")
            return {'files': [], 'directories': []}
    
    def get_download_url(self, file_info: dict) -> str:
        """
        Get download URL for a file.
        
        Args:
            file_info: File info dict with 'url' key
            
        Returns:
            Download URL
        """
        if isinstance(file_info, str):
            return file_info
        return file_info.get('url', '')
    
    def get_all_companies(self, base_url: str = "https://worldleaksartrjm3c6vasllvgacbi5u3mgzkluehrzhk2jz4taufuid.onion/") -> List[str]:
        """
        Get list of all companies from World Leaks.
        
        Args:
            base_url: World Leaks main page URL
            
        Returns:
            List of company storage URLs
        """
        try:
            # Try to get companies from API
            api_url = f"{base_url.rstrip('/')}/api/companies"
            self.logger.info(f"Fetching companies from {api_url}")
            
            response = self.session.get(api_url, timeout=60)
            response.raise_for_status()
            
            companies_data = response.json()
            companies = []
            
            # Extract company URLs
            for company in companies_data:
                company_id = company.get('id') or company.get('company_id')
                if company_id:
                    storage_url = f"{base_url}companies/{company_id}/storage"
                    companies.append(storage_url)
            
            self.logger.info(f"Found {len(companies)} companies")
            return companies
            
        except Exception as e:
            self.logger.error(f"Failed to get company list: {e}")
            return []
