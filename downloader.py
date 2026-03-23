import os
import time
import logging
from typing import Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _fmt_size(n: int) -> str:
    for u in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


class TorDownloader:
    # connect timeout 120s, read timeout None (wait forever for chunks)
    TIMEOUT = (120, None)
    CHUNK_SIZE = 256 * 1024  # 256KB chunks for large files

    def __init__(self, tor_proxy: str = "socks5h://127.0.0.1:9050", timeout=None):
        self.tor_proxy = tor_proxy
        self.timeout = timeout or self.TIMEOUT
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
        """
        Download a single file with resume support.
        Returns (success, message).
        """
        try:
            dir_path = os.path.dirname(output_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            existing_size = 0
            mode = 'wb'
            
            if resume and os.path.exists(output_path):
                existing_size = os.path.getsize(output_path)
                mode = 'ab'
                self.logger.info(f"Resuming from {_fmt_size(existing_size)}")
            
            headers = {}
            if existing_size > 0:
                headers['Range'] = f'bytes={existing_size}-'
            
            response = self.session.get(
                url, headers=headers, stream=True, timeout=self.timeout
            )
            
            if response.status_code not in [200, 206]:
                return False, f"HTTP {response.status_code}"
            
            # Server ignored Range header — start over
            if response.status_code == 200 and existing_size > 0:
                mode = 'wb'
                existing_size = 0
            
            # Get expected total size from Content-Length / Content-Range
            total_size = None
            cr = response.headers.get('Content-Range', '')
            if cr and '/' in cr:
                try:
                    total_size = int(cr.split('/')[-1])
                except ValueError:
                    pass
            if total_size is None:
                cl = response.headers.get('Content-Length')
                if cl:
                    total_size = existing_size + int(cl)
            
            if total_size:
                self.logger.info(
                    f"File size: {_fmt_size(total_size)}, "
                    f"remaining: {_fmt_size(total_size - existing_size)}"
                )
            
            downloaded = existing_size
            last_log = time.time()
            with open(output_path, mode) as f:
                for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Progress log every 30s
                        now = time.time()
                        if now - last_log > 30:
                            pct = f" ({downloaded*100/total_size:.1f}%)" if total_size else ""
                            self.logger.info(f"Progress: {_fmt_size(downloaded)}{pct}")
                            last_log = now
            
            # Verify size if known
            if total_size and downloaded < total_size:
                return False, f"Incomplete: {_fmt_size(downloaded)}/{_fmt_size(total_size)}"
            
            self.logger.info(f"Download complete: {_fmt_size(downloaded)}")
            return True, "Success"
            
        except requests.exceptions.ConnectionError as e:
            return False, f"Connection error: {str(e)}"
        except requests.exceptions.Timeout as e:
            return False, f"Timeout: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def download_with_retry(self, url: str, output_path: str, max_retries: int = 50) -> bool:
        """
        Download with resume-retry loop.
        Keeps retrying with resume until the full file is downloaded.
        For large files (261GB+) this may take many resume cycles.
        """
        for attempt in range(max_retries):
            success, msg = self.download_file(url, output_path, resume=True)
            
            if success:
                return True
            
            backoff = min(2 ** min(attempt, 6), 120)
            self.logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed: {msg}. "
                f"Retry in {backoff}s (file will resume)..."
            )
            time.sleep(backoff)
        
        self.logger.error(f"Failed after {max_retries} attempts: {url}")
        return False
