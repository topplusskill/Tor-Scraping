import logging
from typing import List, Dict
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests


class DirectoryParser:
    def __init__(self, session: requests.Session):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    def parse_directory(self, url: str) -> Dict[str, List[str]]:
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
    
    def crawl_recursive(self, base_url: str, max_depth: int = 10) -> List[str]:
        all_files = []
        visited = set()
        queue = [(base_url, 0)]
        
        while queue:
            url, depth = queue.pop(0)
            
            if url in visited or depth > max_depth:
                continue
            
            visited.add(url)
            self.logger.info(f"Crawling: {url} (depth: {depth})")
            
            result = self.parse_directory(url)
            all_files.extend(result['files'])
            
            for directory in result['directories']:
                if directory not in visited:
                    queue.append((directory, depth + 1))
        
        return all_files
