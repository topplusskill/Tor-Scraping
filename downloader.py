import os
import time
import logging
from typing import Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class TorDownloader:
    def __init__(self, tor_proxy: str = "socks5h://127.0.0.1:9050", timeout: int = 60):
        self.tor_proxy = tor_proxy
        self.timeout = timeout
        self.session = self._create_session()
        self.logger = logging.getLogger(__name__)
        
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.proxies = {
            'http': self.tor_proxy,
            'https': self.tor_proxy
        }
        
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def download_file(self, url: str, output_path: str, resume: bool = True) -> Tuple[bool, str]:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            existing_size = 0
            mode = 'wb'
            
            if resume and os.path.exists(output_path):
                existing_size = os.path.getsize(output_path)
                mode = 'ab'
                self.logger.info(f"Resuming download from byte {existing_size}")
            
            headers = {}
            if existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
            
            response = self.session.get(url, headers=headers, stream=True, timeout=self.timeout)
            
            if response.status_code not in [200, 206]:
                return False, f"HTTP {response.status_code}"
            
            if response.status_code == 200 and existing_size > 0:
                mode = 'wb'
                existing_size = 0
            
            with open(output_path, mode) as f:
                downloaded = existing_size
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            return True, "Success"
            
        except requests.exceptions.ConnectionError as e:
            return False, f"Connection error: {str(e)}"
        except requests.exceptions.Timeout:
            return False, "Timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def download_with_retry(self, url: str, output_path: str, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            success, message = self.download_file(url, output_path)
            
            if success:
                self.logger.info(f"Downloaded: {url}")
                return True
            
            self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {message}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                self.logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        self.logger.error(f"Failed to download {url} after {max_retries} attempts")
        return False
