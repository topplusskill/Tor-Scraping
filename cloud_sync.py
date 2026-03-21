"""
Google Drive sync module for Tor Parser.

Uploads files directly to Google Drive using a service account
with domain-wide delegation (impersonation).

Features:
- Resumable uploads for large files
- Automatic retry with exponential backoff
- Folder structure creation and caching
- Upload verification (size check)
- Progress tracking
"""

import os
import io
import time
import json
import logging
import hashlib
from typing import Optional, Dict, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from googleapiclient.errors import HttpError


logger = logging.getLogger(__name__)


class GoogleDriveSync:
    """
    Handles uploading files to Google Drive with retry logic and verification.
    
    Architecture:
        Tor Site → temp file → Google Drive (resumable upload) → verify → delete temp
    """
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    # Retry configuration
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 2  # seconds
    MAX_BACKOFF = 60  # seconds
    
    # Upload chunk size (256KB minimum for Google Drive resumable uploads)
    CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks
    
    # Retryable HTTP status codes
    RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
    
    def __init__(
        self,
        service_account_file: str,
        impersonate_user: str,
        root_folder_id: str
    ):
        """
        Initialize Google Drive sync.
        
        Args:
            service_account_file: Path to service account JSON key
            impersonate_user: Email of user to impersonate
            root_folder_id: Google Drive folder ID to upload to
        """
        self.service_account_file = service_account_file
        self.impersonate_user = impersonate_user
        self.root_folder_id = root_folder_id
        
        # Folder ID cache: relative_path -> folder_id
        self._folder_cache: Dict[str, str] = {'': root_folder_id}
        
        # Track uploaded files for deduplication
        self._uploaded_files: set = set()
        
        # Stats
        self.stats = {
            'uploaded': 0,
            'failed': 0,
            'skipped': 0,
            'bytes_uploaded': 0,
            'retries': 0,
        }
        
        self._service = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Google Drive API."""
        try:
            creds = service_account.Credentials.from_service_account_file(
                self.service_account_file, scopes=self.SCOPES
            )
            creds = creds.with_subject(self.impersonate_user)
            self._service = build('drive', 'v3', credentials=creds)
            logger.info(f"Connected to Google Drive as {self.impersonate_user}")
        except Exception as e:
            logger.error(f"Failed to connect to Google Drive: {e}")
            raise
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Execute function with exponential backoff retry.
        
        Retries on transient HTTP errors (408, 429, 5xx).
        """
        last_exception = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except HttpError as e:
                status = e.resp.status
                if status in self.RETRYABLE_STATUS:
                    backoff = min(
                        self.INITIAL_BACKOFF * (2 ** attempt),
                        self.MAX_BACKOFF
                    )
                    self.stats['retries'] += 1
                    logger.warning(
                        f"HTTP {status}, retry {attempt + 1}/{self.MAX_RETRIES} "
                        f"in {backoff}s..."
                    )
                    time.sleep(backoff)
                    last_exception = e
                else:
                    raise
            except (ConnectionError, TimeoutError, IOError) as e:
                backoff = min(
                    self.INITIAL_BACKOFF * (2 ** attempt),
                    self.MAX_BACKOFF
                )
                self.stats['retries'] += 1
                logger.warning(
                    f"Connection error: {e}, retry {attempt + 1}/{self.MAX_RETRIES} "
                    f"in {backoff}s..."
                )
                time.sleep(backoff)
                last_exception = e
        
        raise last_exception
    
    def _get_or_create_folder(self, folder_name: str, parent_id: str) -> str:
        """
        Get existing folder or create new one.
        
        Returns folder ID.
        """
        # Check if folder already exists
        query = (
            f"'{parent_id}' in parents and "
            f"name = '{folder_name.replace(chr(39), chr(92)+chr(39))}' and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"trashed = false"
        )
        
        def _list():
            return self._service.files().list(
                q=query,
                fields='files(id, name)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
        
        results = self._retry_with_backoff(_list)
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
        
        # Create folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        
        def _create():
            return self._service.files().create(
                body=file_metadata,
                fields='id',
                supportsAllDrives=True
            ).execute()
        
        folder = self._retry_with_backoff(_create)
        logger.info(f"Created folder: {folder_name}")
        return folder['id']
    
    def _ensure_folder_path(self, relative_path: str) -> str:
        """
        Ensure all folders in path exist, return the deepest folder ID.
        
        Uses caching to avoid redundant API calls.
        """
        # Get the directory part of the path
        dir_path = os.path.dirname(relative_path)
        
        if not dir_path or dir_path == '.':
            return self.root_folder_id
        
        # Check cache
        if dir_path in self._folder_cache:
            return self._folder_cache[dir_path]
        
        # Build folder structure incrementally
        parts = dir_path.replace('\\', '/').split('/')
        current_path = ''
        parent_id = self.root_folder_id
        
        for part in parts:
            if not part:
                continue
            
            current_path = f"{current_path}/{part}" if current_path else part
            
            if current_path in self._folder_cache:
                parent_id = self._folder_cache[current_path]
                continue
            
            parent_id = self._get_or_create_folder(part, parent_id)
            self._folder_cache[current_path] = parent_id
        
        return parent_id
    
    def _check_file_exists(self, file_name: str, parent_id: str, expected_size: int = 0) -> Optional[str]:
        """
        Check if file already exists in the target folder with matching size.
        
        Returns file ID if exists and size matches, None otherwise.
        """
        safe_name = file_name.replace("'", "\\'")
        query = (
            f"'{parent_id}' in parents and "
            f"name = '{safe_name}' and "
            f"trashed = false"
        )
        
        def _list():
            return self._service.files().list(
                q=query,
                fields='files(id, name, size)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
        
        results = self._retry_with_backoff(_list)
        files = results.get('files', [])
        
        if files:
            existing_size = int(files[0].get('size', 0))
            if expected_size > 0 and existing_size == expected_size:
                return files[0]['id']
            elif expected_size == 0:
                return files[0]['id']
        
        return None
    
    def upload_file(self, local_path: str, relative_path: str, skip_existing: bool = True) -> bool:
        """
        Upload a local file to Google Drive, preserving folder structure.
        
        Args:
            local_path: Path to local file
            relative_path: Relative path for Google Drive (preserves structure)
            skip_existing: Skip if file with same name and size exists
            
        Returns:
            True if upload successful or skipped
        """
        if not os.path.exists(local_path):
            logger.error(f"Local file not found: {local_path}")
            self.stats['failed'] += 1
            return False
        
        file_size = os.path.getsize(local_path)
        file_name = os.path.basename(relative_path)
        
        try:
            # Ensure folder structure exists
            parent_id = self._ensure_folder_path(relative_path)
            
            # Check if file already exists
            if skip_existing:
                existing_id = self._check_file_exists(file_name, parent_id, file_size)
                if existing_id:
                    logger.info(f"Skipping (exists): {relative_path}")
                    self.stats['skipped'] += 1
                    return True
            
            # Upload file with resumable upload
            file_metadata = {
                'name': file_name,
                'parents': [parent_id]
            }
            
            media = MediaFileUpload(
                local_path,
                resumable=True,
                chunksize=self.CHUNK_SIZE
            )
            
            def _create():
                request = self._service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,name,size',
                    supportsAllDrives=True
                )
                
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        pct = int(status.progress() * 100)
                        logger.debug(f"Upload {relative_path}: {pct}%")
                
                return response
            
            result = self._retry_with_backoff(_create)
            
            # Verify upload
            uploaded_size = int(result.get('size', 0))
            if file_size > 0 and uploaded_size != file_size:
                logger.error(
                    f"Size mismatch for {relative_path}: "
                    f"local={file_size}, remote={uploaded_size}"
                )
                self.stats['failed'] += 1
                return False
            
            self.stats['uploaded'] += 1
            self.stats['bytes_uploaded'] += file_size
            self._uploaded_files.add(relative_path)
            
            logger.info(
                f"Uploaded: {relative_path} ({self._format_size(file_size)})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload {relative_path}: {e}")
            self.stats['failed'] += 1
            return False
    
    def upload_stream(self, data: bytes, relative_path: str, skip_existing: bool = True) -> bool:
        """
        Upload data directly from memory to Google Drive.
        
        Args:
            data: File content as bytes
            relative_path: Relative path for Google Drive
            skip_existing: Skip if file with same name and size exists
            
        Returns:
            True if upload successful
        """
        file_name = os.path.basename(relative_path)
        file_size = len(data)
        
        try:
            parent_id = self._ensure_folder_path(relative_path)
            
            if skip_existing:
                existing_id = self._check_file_exists(file_name, parent_id, file_size)
                if existing_id:
                    logger.info(f"Skipping (exists): {relative_path}")
                    self.stats['skipped'] += 1
                    return True
            
            file_metadata = {
                'name': file_name,
                'parents': [parent_id]
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(data),
                mimetype='application/octet-stream',
                resumable=True,
                chunksize=self.CHUNK_SIZE
            )
            
            def _create():
                return self._service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,name,size',
                    supportsAllDrives=True
                ).execute()
            
            result = self._retry_with_backoff(_create)
            
            uploaded_size = int(result.get('size', 0))
            if file_size > 0 and uploaded_size != file_size:
                logger.error(
                    f"Size mismatch for {relative_path}: "
                    f"local={file_size}, remote={uploaded_size}"
                )
                self.stats['failed'] += 1
                return False
            
            self.stats['uploaded'] += 1
            self.stats['bytes_uploaded'] += file_size
            self._uploaded_files.add(relative_path)
            
            logger.info(
                f"Uploaded: {relative_path} ({self._format_size(file_size)})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload {relative_path}: {e}")
            self.stats['failed'] += 1
            return False
    
    def get_stats_summary(self) -> str:
        """Return human-readable stats summary."""
        s = self.stats
        return (
            f"GDrive: {s['uploaded']} uploaded, "
            f"{s['skipped']} skipped, "
            f"{s['failed']} failed, "
            f"{self._format_size(s['bytes_uploaded'])} total, "
            f"{s['retries']} retries"
        )
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
