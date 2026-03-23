"""
Google Drive sync via rclone mount.

Mounts Google Drive folder locally via rclone and writes files directly.
Handles mount/unmount, health checks, and automatic remount on failure.

Requires:
- rclone installed and configured with [gdrive] remote
- Service account with domain-wide delegation
- rclone.conf with impersonate = user@domain
"""

import os
import time
import shutil
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class GDriveMount:
    """
    Manages rclone mount lifecycle and provides the mount path for direct file writes.
    
    Usage:
        mount = GDriveMount()
        mount.ensure_mounted()
        # Now just use mount.path as output directory
        # Files written there go straight to Google Drive
    """
    
    MOUNT_POINT = '/mnt/gdrive'
    RCLONE_REMOTE = 'gdrive:'
    HEALTH_CHECK_INTERVAL = 30  # seconds
    MAX_MOUNT_RETRIES = 5
    MOUNT_TIMEOUT = 30  # seconds to wait for mount
    
    def __init__(self, mount_point: str = None, remote: str = None):
        self.path = mount_point or self.MOUNT_POINT
        self.remote = remote or self.RCLONE_REMOTE
        self._last_health_check = 0
        self._mount_retries = 0
    
    def is_mounted(self) -> bool:
        """Check if rclone mount is active and writable."""
        try:
            result = subprocess.run(
                ['mountpoint', '-q', self.path],
                capture_output=True, timeout=5
            )
            if result.returncode != 0:
                return False
            
            # Verify it's actually responsive (not stale)
            test_path = os.path.join(self.path, '.mount_check')
            try:
                Path(test_path).touch()
                os.remove(test_path)
                return True
            except (OSError, IOError):
                return False
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False
    
    def mount(self) -> bool:
        """Mount Google Drive via rclone."""
        logger.info(f"Mounting {self.remote} -> {self.path}")
        
        # Ensure mount point exists
        os.makedirs(self.path, exist_ok=True)
        
        # Unmount stale mount if any
        self._force_unmount()
        time.sleep(1)
        
        # Clear VFS cache to avoid stale data
        cache_dir = os.path.expanduser('~/.cache/rclone/vfs/gdrive')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir, ignore_errors=True)
        
        meta_dir = os.path.expanduser('~/.cache/rclone/vfsMeta/gdrive')
        if os.path.exists(meta_dir):
            shutil.rmtree(meta_dir, ignore_errors=True)
        
        try:
            subprocess.run([
                'rclone', 'mount', self.remote, self.path,
                '--vfs-cache-mode', 'writes',
                '--vfs-write-back', '5s',
                '--vfs-cache-max-size', '2G',
                '--dir-cache-time', '30s',
                '--log-file', '/tmp/rclone-mount.log',
                '--log-level', 'INFO',
                '--daemon',
            ], capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            pass
        
        # Wait for mount to become available
        for i in range(self.MOUNT_TIMEOUT):
            if self.is_mounted():
                logger.info(f"Mounted successfully: {self.path}")
                self._mount_retries = 0
                return True
            time.sleep(1)
        
        logger.error(f"Mount failed after {self.MOUNT_TIMEOUT}s")
        return False
    
    def _force_unmount(self):
        """Force unmount, ignoring errors."""
        subprocess.run(
            ['fusermount', '-uz', self.path],
            capture_output=True, timeout=10
        )
    
    def unmount(self):
        """Cleanly unmount."""
        logger.info(f"Unmounting {self.path}")
        self._force_unmount()
    
    def ensure_mounted(self) -> bool:
        """
        Ensure mount is active. Remount with retry if down.
        
        Call this periodically or before critical writes.
        Returns True if mount is healthy.
        """
        now = time.time()
        
        # Skip check if recently verified
        if now - self._last_health_check < self.HEALTH_CHECK_INTERVAL:
            return True
        
        self._last_health_check = now
        
        if self.is_mounted():
            return True
        
        # Mount is down, try to remount with backoff
        for attempt in range(self.MAX_MOUNT_RETRIES):
            backoff = min(2 ** attempt, 30)
            logger.warning(
                f"Mount down, remount attempt {attempt + 1}/{self.MAX_MOUNT_RETRIES}"
            )
            
            if self.mount():
                return True
            
            logger.warning(f"Remount failed, waiting {backoff}s...")
            time.sleep(backoff)
        
        logger.error("All remount attempts failed")
        return False
    
    def write_ok(self, file_path: str) -> bool:
        """
        Verify a file was written successfully to the mount.
        
        Args:
            file_path: Full path to the file on the mount
            
        Returns:
            True if file exists and has non-zero size
        """
        try:
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        except OSError:
            return False
