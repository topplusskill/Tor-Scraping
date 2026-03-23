import argparse
import logging
import os
import json
import sys
import shutil
from datetime import datetime
from downloader import TorDownloader
from parser import DirectoryParser
from parsers import LockbitParser, DragonForceParser, INCRansomParser
from parsers.base import BaseParser


def setup_logging(log_file: str = 'download.log'):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


def save_progress(downloaded: set, failed: set, output_file: str = 'progress.json'):
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'downloaded': list(downloaded),
            'failed': list(failed)
        }, f, indent=2)


def load_progress(progress_file: str = 'progress.json'):
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            data = json.load(f)
            return set(data.get('downloaded', [])), set(data.get('failed', []))
    return set(), set()


def is_file_complete(file_path: str, expected_size: int = None) -> bool:
    if not os.path.exists(file_path):
        return False
    if expected_size and os.path.getsize(file_path) != expected_size:
        return False
    return True


def get_parser_for_site(site_type: str, session, cookies_file: str = None):
    """
    Factory function to get the appropriate parser for a site type.
    
    Args:
        site_type: One of 'lockbit', 'dragonforce', 'incransom', or 'auto'
        session: requests.Session with Tor proxy configured
        cookies_file: Optional path to cookies file for CAPTCHA bypass
        
    Returns:
        Parser instance
    """
    if site_type == 'lockbit':
        return LockbitParser(session)
    elif site_type == 'dragonforce':
        return DragonForceParser(session)
    elif site_type == 'incransom':
        return INCRansomParser(session, cookies_file=cookies_file)
    
    # Default to legacy DirectoryParser for backward compatibility
    return DirectoryParser(session)


def detect_site_type(url: str) -> str:
    """
    Auto-detect site type from URL.
    
    Args:
        url: Target URL
        
    Returns:
        Site type string
    """
    url_lower = url.lower()
    
    if 'lockbit' in url_lower:
        return 'lockbit'
    elif 'dragonfor' in url_lower:
        return 'dragonforce'
    elif 'incblog' in url_lower or 'incransom' in url_lower:
        return 'incransom'
    
    # Default to lockbit-style (Apache directory listing)
    return 'lockbit'


def main():
    parser = argparse.ArgumentParser(description='Tor-based directory downloader')
    parser.add_argument('url', help='Target URL to download from')
    parser.add_argument('-o', '--output', default='downloads', help='Output directory')
    parser.add_argument('--max-depth', type=int, default=10, help='Maximum recursion depth')
    parser.add_argument('--tor-proxy', default='socks5h://127.0.0.1:9050', help='Tor SOCKS5 proxy')
    parser.add_argument('--skip-existing', action='store_true', default=True, help='Skip already downloaded files')
    parser.add_argument('--site-type', choices=['auto', 'lockbit', 'dragonforce', 'incransom'], 
                        default='auto', help='Site type (auto-detected if not specified)')
    parser.add_argument('--password', default=None, help='Password for protected disclosures (INC Ransom)')
    parser.add_argument('--cookies', default=None, help='Path to cookies file for CAPTCHA bypass (JSON or Netscape format)')
    parser.add_argument('--mount-gdrive', action='store_true', default=False,
                        help='Mount Google Drive via rclone and write directly to it')
    
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Validate URL format
    if not args.url.startswith('http://') and not args.url.startswith('https://'):
        logger.error("URL must start with http:// or https://")
        return
    
    # Mount Google Drive if requested
    gdrive_mount = None
    gdrive_output = None
    local_output = args.output
    if args.mount_gdrive:
        from cloud_sync import GDriveMount
        gdrive_mount = GDriveMount()
        if not gdrive_mount.ensure_mounted():
            logger.error("Failed to mount Google Drive. Check rclone config.")
            return
        gdrive_output = os.path.join(gdrive_mount.path, args.output)
        os.makedirs(gdrive_output, exist_ok=True)
        local_output = os.path.join('/tmp', f"tor-local-{args.output}")
        logger.info(f"GDrive mounted. Download local -> {local_output}, then copy -> {gdrive_output}")
    
    args.output = local_output
    os.makedirs(args.output, exist_ok=True)
    progress_file = os.path.join(args.output, '.progress.json')
    
    downloaded, failed = load_progress(progress_file)
    logger.info(f"Loaded progress: {len(downloaded)} downloaded, {len(failed)} failed")
    
    downloader = TorDownloader(tor_proxy=args.tor_proxy)
    
    # Detect or use specified site type
    site_type = args.site_type
    if site_type == 'auto':
        site_type = detect_site_type(args.url)
        logger.info(f"Auto-detected site type: {site_type}")
    
    # Get appropriate parser
    dir_parser = get_parser_for_site(site_type, downloader.session, cookies_file=args.cookies)
    logger.info(f"Using parser: {dir_parser.__class__.__name__}")
    
    logger.info(f"Starting crawl of {args.url}")
    logger.info("Files will be downloaded as they are discovered...")
    
    # Additional kwargs for site-specific parsers
    parser_kwargs = {}
    if args.password:
        parser_kwargs['password'] = args.password
    
    total_files = 0
    skipped_count = 0
    success_count = len(downloaded)
    failed_count = len(failed)
    
    visited = set()
    queue = [(args.url, 0)]
    
    while queue:
        url, depth = queue.pop(0)
        
        if url in visited or depth > args.max_depth:
            continue
        
        visited.add(url)
        sys.stdout.write(f"\rCrawling depth {depth}... Found {total_files} files, Downloaded {success_count}, Skipped {skipped_count}, Failed {failed_count}")
        sys.stdout.flush()
        
        # For API-based parsers (INC Ransom, DragonForce), url might be a path, not actual URL
        # Pass it as 'path' kwarg if it doesn't look like a URL
        if not url.startswith('http'):
            result = dir_parser.parse_directory(args.url, path=url, **parser_kwargs)
        else:
            result = dir_parser.parse_directory(url, **parser_kwargs)
        
        for file_item in result['files']:
            total_files += 1
            
            # Handle both URL strings and dict format
            if isinstance(file_item, dict):
                file_url = file_item.get('url', '')
                file_path = file_item.get('path', '')
                file_id = file_path or file_url
                relative_path = file_path.lstrip('/')
            else:
                file_url = file_item
                file_id = file_url
                relative_path = file_url.replace(args.url, '').lstrip('/')
            
            if file_id in downloaded:
                skipped_count += 1
                continue
            
            if file_id in failed:
                logger.info(f"\nSkipping previously failed: {file_id}")
                continue
            
            output_path = os.path.join(args.output, relative_path)
            
            if args.skip_existing and is_file_complete(output_path):
                logger.info(f"\nSkipping existing file: {relative_path}")
                downloaded.add(file_id)
                skipped_count += 1
                save_progress(downloaded, failed, progress_file)
                continue
            
            logger.info(f"\n[{success_count + failed_count + 1}/{total_files}] Downloading: {relative_path}")
            
            # Use parser's download method if available (for API-based sites)
            download_success = False
            if hasattr(dir_parser, 'download_file') and isinstance(file_item, dict):
                download_success = dir_parser.download_file(file_item, output_path)
            else:
                download_success = downloader.download_with_retry(file_url, output_path)
            
            if download_success:
                # Copy to GDrive mount if configured
                if gdrive_mount and gdrive_output:
                    if not gdrive_mount.ensure_mounted():
                        logger.error("GDrive mount lost, attempting recovery...")
                    else:
                        gdrive_path = os.path.join(gdrive_output, relative_path)
                        os.makedirs(os.path.dirname(gdrive_path), exist_ok=True)
                        try:
                            shutil.copy2(output_path, gdrive_path)
                            logger.info(f"Copied to GDrive: {relative_path}")
                        except Exception as e:
                            logger.error(f"Failed to copy to GDrive: {e}")
                
                success_count += 1
                downloaded.add(file_id)
            else:
                failed_count += 1
                failed.add(file_id)
            
            save_progress(downloaded, failed, progress_file)
            
            sys.stdout.write(f"\rCrawling depth {depth}... Found {total_files} files, Downloaded {success_count}, Skipped {skipped_count}, Failed {failed_count}")
            sys.stdout.flush()
        
        for directory in result['directories']:
            # Handle both URL strings and dict format for directories
            if isinstance(directory, dict):
                dir_path = directory.get('path', directory.get('url', ''))
            else:
                dir_path = directory
            
            if dir_path not in visited:
                queue.append((dir_path, depth + 1))
    
    print(f"\n\nDownload complete!")
    print(f"Total files found: {total_files}")
    print(f"Downloaded: {success_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")
    
    if gdrive_mount:
        print(f"\nFiles saved to Google Drive via {gdrive_mount.path}")


if __name__ == '__main__':
    main()
