#!/usr/bin/env python3
"""
Universal Tor Downloader for Ransomware Leak Sites

Supports: Lockbit, DragonForce, INC Ransom

Best Practices Applied:
- HTTP Range resume for large files (tested with 261GB+)
- Optimal chunk size (256KB) for Tor network
- Connection pooling with retry strategy
- Streaming downloads (no memory buffering)
- Real-time progress bar with speed/ETA
- Automatic token refresh (DragonForce)
- Exponential backoff retry (up to 50 attempts)
- Specific folder selection

Based on research:
- torget: Multiple circuits for speed (20+ parallel)
- Python requests: stream=True with iter_content()
- Optimal chunk: 256KB-1MB for Tor (balance speed/memory)
"""

import os
import sys
import time
import json
import logging
import argparse
from pathlib import Path
from typing import Optional, List, Dict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Import parsers from existing codebase
from parsers import LockbitParser, DragonForceParser, INCRansomParser
from downloader import TorDownloader


class ProgressTracker:
    """Enhanced progress tracker with statistics"""
    
    def __init__(self, total_files: int):
        self.total_files = total_files
        self.downloaded = 0
        self.failed = 0
        self.skipped = 0
        self.total_bytes = 0
        self.start_time = time.time()
        
    def update(self, status: str, file_size: int = 0):
        if status == 'downloaded':
            self.downloaded += 1
            self.total_bytes += file_size
        elif status == 'failed':
            self.failed += 1
        elif status == 'skipped':
            self.skipped += 1
    
    def print_progress(self, current_file: str = ""):
        elapsed = time.time() - self.start_time
        processed = self.downloaded + self.failed + self.skipped
        percent = (processed / self.total_files * 100) if self.total_files > 0 else 0
        
        speed = self.total_bytes / elapsed if elapsed > 0 else 0
        eta = (self.total_files - processed) * (elapsed / processed) if processed > 0 else 0
        
        print(f"\r[{processed}/{self.total_files}] {percent:.1f}% | "
              f"✓{self.downloaded} ✗{self.failed} ⊘{self.skipped} | "
              f"{self._format_size(self.total_bytes)} | "
              f"{self._format_speed(speed)} | "
              f"ETA: {self._format_time(eta)} | "
              f"{current_file[:40]:<40}", end='', flush=True)
    
    def print_summary(self):
        elapsed = time.time() - self.start_time
        avg_speed = self.total_bytes / elapsed if elapsed > 0 else 0
        
        print(f"\n{'='*80}")
        print(f"Download Summary:")
        print(f"  Total files:    {self.total_files}")
        print(f"  Downloaded:     {self.downloaded} ({self.downloaded/self.total_files*100:.1f}%)")
        print(f"  Failed:         {self.failed} ({self.failed/self.total_files*100:.1f}%)")
        print(f"  Skipped:        {self.skipped} ({self.skipped/self.total_files*100:.1f}%)")
        print(f"  Total size:     {self._format_size(self.total_bytes)}")
        print(f"  Time elapsed:   {self._format_time(elapsed)}")
        print(f"  Average speed:  {self._format_speed(avg_speed)}")
        print(f"{'='*80}")
    
    @staticmethod
    def _format_size(bytes_size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f}PB"
    
    @staticmethod
    def _format_speed(bytes_per_sec: float) -> str:
        return f"{ProgressTracker._format_size(bytes_per_sec)}/s"
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m{int(seconds%60)}s"
        else:
            return f"{int(seconds/3600)}h{int((seconds%3600)/60)}m"


def detect_site_type(url: str) -> str:
    """Auto-detect site type from URL"""
    url_lower = url.lower()
    
    if 'lockbit' in url_lower:
        return 'lockbit'
    elif 'dragonfor' in url_lower:
        return 'dragonforce'
    elif 'incblog' in url_lower or 'incransom' in url_lower:
        return 'incransom'
    
    return 'lockbit'  # Default


def create_parser(site_type: str, session: requests.Session, **kwargs):
    """Factory to create appropriate parser"""
    if site_type == 'lockbit':
        return LockbitParser(session)
    elif site_type == 'dragonforce':
        return DragonForceParser(session)
    elif site_type == 'incransom':
        return INCRansomParser(session, cookies_file=kwargs.get('cookies_file'))
    else:
        raise ValueError(f"Unknown site type: {site_type}")


def save_file_list(files: List[Dict], output_file: Path):
    """Save file list to JSON for resume"""
    with open(output_file, 'w') as f:
        json.dump(files, f, indent=2)


def load_file_list(input_file: Path) -> List[Dict]:
    """Load file list from JSON"""
    if input_file.exists():
        with open(input_file, 'r') as f:
            return json.load(f)
    return []


def load_targets():
    """Load targets from targets.json"""
    targets_file = Path(__file__).parent / 'targets.json'
    if targets_file.exists():
        with open(targets_file, 'r') as f:
            data = json.load(f)
            return {t['name']: t for t in data.get('targets', [])}
    return {}


def main():
    # Load targets first to show in help
    targets = load_targets()
    target_names = ', '.join(targets.keys()) if targets else 'none'
    
    parser = argparse.ArgumentParser(
        description='Universal Tor Downloader for Ransomware Leak Sites',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Simple - use target name from targets.json
  %(prog)s lockbit-kioti
  %(prog)s dragonforce-hartmann
  %(prog)s incransom-68001f58
  
  # Or use full URL
  %(prog)s "http://lockbit...onion/secret/.../company.com/"
  
  # Specific folder only
  %(prog)s dragonforce-hartmann --path "/Accounting"
  
  # Custom output directory
  %(prog)s lockbit-kioti -o ./my-folder

Available targets: {target_names}

Supported sites (auto-detected):
  - Lockbit (Apache directory listing)
  - DragonForce (JWT auth + file server)
  - INC Ransom (REST API + CDN)
  
Default behavior:
  - Downloads to: downloads/ folder
  - Downloads: ALL files (unlimited depth)
  - Auto-detects: site type
  - Resume support: enabled
  - Retry: up to 50 attempts per file
        """
    )
    
    # Required arguments
    parser.add_argument('target', help='Target name from targets.json or full .onion URL')
    
    # Optional arguments
    parser.add_argument('-o', '--output', default='downloads', help='Output directory (default: downloads/)')
    parser.add_argument('--path', help='Specific folder path to download (default: download ALL files)')
    parser.add_argument('--max-depth', type=int, default=999, help='Max recursion depth (default: 999 = unlimited)')
    parser.add_argument('--site-type', choices=['auto', 'lockbit', 'dragonforce', 'incransom'],
                       default='auto', help='Site type (default: auto-detect)')
    parser.add_argument('--tor-proxy', default='socks5h://127.0.0.1:9050', 
                       help='Tor SOCKS5 proxy (default: socks5h://127.0.0.1:9050)')
    parser.add_argument('--password', help='Password for INC Ransom')
    parser.add_argument('--cookies', help='Cookies file for INC Ransom CAPTCHA bypass')
    parser.add_argument('--resume', action='store_true', help='Resume from previous run')
    parser.add_argument('--log-file', default='download.log', help='Log file (default: download.log)')
    parser.add_argument('--no-resume-download', action='store_true', 
                       help='Disable HTTP Range resume')
    
    args = parser.parse_args()
    
    # Resolve target name to URL if needed
    url = args.target
    site_type = args.site_type
    
    if not url.startswith('http'):
        # It's a target name, look it up
        if args.target in targets:
            target_info = targets[args.target]
            url = target_info['url']
            if site_type == 'auto':
                site_type = target_info.get('site_type', 'auto')
            print(f"Using target: {args.target}")
            print(f"URL: {url}")
        else:
            print(f"Error: Unknown target '{args.target}'")
            print(f"Available targets: {', '.join(targets.keys())}")
            return 1
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(args.log_file),
            logging.StreamHandler(sys.stderr)
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Detect site type if still auto
    if site_type == 'auto':
        site_type = detect_site_type(url)
        logger.info(f"Auto-detected site type: {site_type}")
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # File list cache
    file_list_cache = output_dir / '.file_list.json'
    
    # Create session with Tor proxy
    session = requests.Session()
    session.proxies = {
        'http': args.tor_proxy,
        'https': args.tor_proxy
    }
    
    # Add retry strategy
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Create parser
    parser_obj = create_parser(site_type, session, cookies_file=args.cookies)
    
    # Set default path if not specified
    start_path = args.path if args.path else '/'
    
    # Crawl or load file list
    files = []
    if args.resume and file_list_cache.exists():
        logger.info(f"Resuming from cached file list: {file_list_cache}")
        files = load_file_list(file_list_cache)
    else:
        logger.info(f"Crawling {url} from path: {start_path}")
        
        if site_type == 'dragonforce':
            # DragonForce uses special crawl method with path support
            # Need to manually crawl from specific path
            all_files = []
            visited = set()
            queue = [(start_path, 0)]
            
            # Extract token first
            if not parser_obj._ensure_token(url):
                logger.error("Could not obtain authentication token")
                return 1
            
            while queue:
                path, depth = queue.pop(0)
                
                if path in visited or depth > args.max_depth:
                    continue
                
                visited.add(path)
                logger.info(f"Crawling: {path} (depth: {depth})")
                
                result = parser_obj.parse_directory(url, main_url=url, path=path)
                all_files.extend(result['files'])
                
                for directory in result['directories']:
                    dir_path = directory.get('path', directory) if isinstance(directory, dict) else directory
                    if dir_path not in visited:
                        queue.append((dir_path, depth + 1))
            
            files = all_files
        else:
            # Lockbit and INC Ransom use standard crawl
            all_urls = parser_obj.crawl_recursive(url, max_depth=args.max_depth)
            files = [{'url': file_url, 'path': file_url.split('/')[-1]} for file_url in all_urls]
        
        if not files:
            logger.error("No files found")
            return 1
        
        logger.info(f"Found {len(files)} files")
        save_file_list(files, file_list_cache)
    
    # Create downloader
    downloader = TorDownloader(tor_proxy=args.tor_proxy)
    
    # Progress tracker
    progress = ProgressTracker(len(files))
    
    # Download files
    for i, file_info in enumerate(files, 1):
        if site_type == 'dragonforce':
            file_path = file_info.get('path', '')
            file_name = file_info.get('name', os.path.basename(file_path))
            download_url = parser_obj.get_download_url(file_info)
        else:
            download_url = file_info.get('url', '')
            file_name = file_info.get('path', download_url.split('/')[-1])
            file_path = file_name
        
        output_path = output_dir / file_path.lstrip('/')
        
        # Skip if already exists
        if output_path.exists() and output_path.stat().st_size > 0:
            progress.update('skipped')
            progress.print_progress(file_name)
            continue
        
        # Download with retry
        progress.print_progress(f"Downloading {file_name}")
        
        resume_enabled = not args.no_resume_download
        success = downloader.download_with_retry(download_url, str(output_path), max_retries=50)
        
        if success:
            file_size = output_path.stat().st_size if output_path.exists() else 0
            progress.update('downloaded', file_size)
        else:
            progress.update('failed')
        
        progress.print_progress(file_name)
    
    print()  # New line after progress
    progress.print_summary()
    
    return 0 if progress.failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
