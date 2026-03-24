"""
Centralized configuration for Tor Parser.

All tunable constants in one place. Import from here instead of
hardcoding values across modules.
"""

import os

# ─── Tor ────────────────────────────────────────────────────────────
TOR_PROXY = os.environ.get("TOR_PROXY", "socks5h://127.0.0.1:9050")
TOR_CONNECT_TIMEOUT = 120          # seconds to establish connection
TOR_READ_TIMEOUT = None            # None = wait forever for data
TOR_TIMEOUT = (TOR_CONNECT_TIMEOUT, TOR_READ_TIMEOUT)

# ─── Download ───────────────────────────────────────────────────────
CHUNK_SIZE = 256 * 1024            # 256 KB per read
MAX_RETRIES = 50                   # resume-retry attempts for large files
SMALL_FILE_RETRIES = 3             # retries for small/API downloads
BACKOFF_BASE = 2                   # exponential backoff base (seconds)
BACKOFF_MAX = 120                  # maximum backoff cap (seconds)
PROGRESS_LOG_INTERVAL = 30         # log download progress every N seconds

# HTTP status codes that trigger automatic retry
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

# ─── Crawling ───────────────────────────────────────────────────────
DEFAULT_MAX_DEPTH = 10
DEFAULT_OUTPUT_DIR = "downloads"

# ─── Google Drive / rclone ──────────────────────────────────────────
GDRIVE_MOUNT_POINT = os.environ.get("GDRIVE_MOUNT", "/mnt/gdrive")
RCLONE_REMOTE = os.environ.get("RCLONE_REMOTE", "gdrive:")
RCLONE_VFS_CACHE_MODE = "writes"
RCLONE_VFS_WRITE_BACK = "5s"
RCLONE_VFS_CACHE_MAX = "2G"
RCLONE_DIR_CACHE_TIME = "30s"
RCLONE_LOG_FILE = "/tmp/rclone-mount.log"

MOUNT_HEALTH_CHECK_INTERVAL = 30   # seconds between mount checks
MOUNT_MAX_RETRIES = 5
MOUNT_TIMEOUT = 30                 # seconds to wait for mount to appear

# ─── Paths ──────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGETS_FILE = os.path.join(PROJECT_DIR, "targets.json")
LOCAL_DOWNLOAD_PREFIX = "/tmp/tor-local-"
LOG_DIR = "/tmp"

# ─── Site-specific ──────────────────────────────────────────────────
LOCKBIT_SKIP_DIRS = {"unpack/", "unpack"}

DRAGONFORCE_TOKEN_REFRESH_MARGIN = 300  # refresh JWT 5 min before expiry
DRAGONFORCE_KNOWN_FILE_SERVERS = [
    "dragonfscjlox5bnhgjv22m42anurgpyeh3bfmhokqtix3hsnsqajead.onion",
    "fsguestuctexqqaoxuahuydfa6ovxuhtng66pgyr5gqcrsi7qgchpkad.onion",
]

INCRANSOM_API_SERVER = "incbacg6bfwtrlzwdbqc55gsfl763s3twdtwhp27dzuik6s6rwdcityd.onion"
INCRANSOM_CDN_SERVER = "inccdnlqq4jffxjrynglk755gsqkorblvutyeyw7uaiyscc5ueiyxnid.onion"
