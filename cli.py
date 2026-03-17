import argparse
import logging
import os
import json
import sys
from datetime import datetime
from downloader import TorDownloader
from parser import DirectoryParser


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


def main():
    parser = argparse.ArgumentParser(description='Tor-based directory downloader')
    parser.add_argument('url', help='Target URL to download from')
    parser.add_argument('-o', '--output', default='downloads', help='Output directory')
    parser.add_argument('--max-depth', type=int, default=10, help='Maximum recursion depth')
    parser.add_argument('--tor-proxy', default='socks5h://127.0.0.1:9050', help='Tor SOCKS5 proxy')
    parser.add_argument('--skip-existing', action='store_true', default=True, help='Skip already downloaded files')
    
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Validate URL format
    if not args.url.startswith('http://') and not args.url.startswith('https://'):
        logger.error("URL must start with http:// or https://")
        return
    
    os.makedirs(args.output, exist_ok=True)
    progress_file = os.path.join(args.output, '.progress.json')
    
    downloaded, failed = load_progress(progress_file)
    logger.info(f"Loaded progress: {len(downloaded)} downloaded, {len(failed)} failed")
    
    downloader = TorDownloader(tor_proxy=args.tor_proxy)
    dir_parser = DirectoryParser(downloader.session)
    
    logger.info(f"Starting crawl of {args.url}")
    logger.info("Files will be downloaded as they are discovered...")
    
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
        
        result = dir_parser.parse_directory(url)
        
        for file_url in result['files']:
            total_files += 1
            
            if file_url in downloaded:
                skipped_count += 1
                continue
            
            if file_url in failed:
                logger.info(f"\nSkipping previously failed: {file_url}")
                continue
            
            relative_path = file_url.replace(args.url, '').lstrip('/')
            output_path = os.path.join(args.output, relative_path)
            
            if args.skip_existing and is_file_complete(output_path):
                logger.info(f"\nSkipping existing file: {relative_path}")
                downloaded.add(file_url)
                skipped_count += 1
                save_progress(downloaded, failed, progress_file)
                continue
            
            logger.info(f"\n[{success_count + failed_count + 1}/{total_files}] Downloading: {relative_path}")
            
            if downloader.download_with_retry(file_url, output_path):
                success_count += 1
                downloaded.add(file_url)
            else:
                failed_count += 1
                failed.add(file_url)
            
            save_progress(downloaded, failed, progress_file)
            
            sys.stdout.write(f"\rCrawling depth {depth}... Found {total_files} files, Downloaded {success_count}, Skipped {skipped_count}, Failed {failed_count}")
            sys.stdout.flush()
        
        for directory in result['directories']:
            if directory not in visited:
                queue.append((directory, depth + 1))
    
    print(f"\n\nDownload complete!")
    print(f"Total files found: {total_files}")
    print(f"Downloaded: {success_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")


if __name__ == '__main__':
    main()
