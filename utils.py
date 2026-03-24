"""
Shared utility helpers used across the Tor Parser project.
"""

import os
import time
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Formatting ─────────────────────────────────────────────────────

def fmt_size(n: float) -> str:
    """Human-readable file size (e.g. 261.7 GB)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def fmt_duration(seconds: float) -> str:
    """Human-readable duration (e.g. 2h 15m 30s)."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(seconds), 60)
    hours, mins = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}h {mins}m {secs}s"
    return f"{mins}m {secs}s"


def fmt_speed(bytes_per_sec: float) -> str:
    """Human-readable transfer speed (e.g. 1.5 MB/s)."""
    return f"{fmt_size(bytes_per_sec)}/s"


def fmt_eta(remaining_bytes: float, speed: float) -> str:
    """Estimated time of arrival based on remaining bytes and speed."""
    if speed <= 0:
        return "∞"
    return fmt_duration(remaining_bytes / speed)


# ─── File helpers ───────────────────────────────────────────────────

def file_sha256(path: str, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_filename(name: str) -> str:
    """
    Sanitise a filename for safe filesystem storage.
    Replaces problematic characters with underscores.
    """
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_()")
    return "".join(c if c in keep else "_" for c in name).strip("_") or "unnamed"


def ensure_dir(path: str) -> str:
    """Create directory (and parents) if it doesn't exist. Returns path."""
    os.makedirs(path, exist_ok=True)
    return path


def is_file_complete(file_path: str, expected_size: Optional[int] = None) -> bool:
    """Check if a file exists and optionally matches expected size."""
    if not os.path.exists(file_path):
        return False
    if expected_size is not None and os.path.getsize(file_path) != expected_size:
        return False
    return True


# ─── Progress persistence ──────────────────────────────────────────

def save_progress(downloaded: set, failed: set, output_file: str):
    """Save download progress to JSON."""
    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "downloaded_count": len(downloaded),
                "failed_count": len(failed),
                "downloaded": sorted(downloaded),
                "failed": sorted(failed),
            },
            f,
            indent=2,
        )


def load_progress(progress_file: str) -> Tuple[set, set]:
    """Load download progress from JSON. Returns (downloaded, failed) sets."""
    if not os.path.exists(progress_file):
        return set(), set()
    try:
        with open(progress_file, "r") as f:
            data = json.load(f)
        return set(data.get("downloaded", [])), set(data.get("failed", []))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Corrupted progress file {progress_file}: {e}")
        return set(), set()


# ─── Network helpers ────────────────────────────────────────────────

def extract_onion_host(url: str) -> Optional[str]:
    """Extract the .onion hostname from a URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host.endswith(".onion"):
        return host
    return None


def is_tor_running(proxy: str = "socks5h://127.0.0.1:9050") -> bool:
    """Quick check if Tor SOCKS proxy is accepting connections."""
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(proxy)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9050
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except (ConnectionRefusedError, OSError):
        return False


# ─── Timing ─────────────────────────────────────────────────────────

class RateLimiter:
    """
    Simple token-bucket rate limiter.

    Usage:
        limiter = RateLimiter(calls_per_second=2)
        limiter.wait()  # blocks if needed
        do_request()
    """

    def __init__(self, calls_per_second: float = 2.0):
        self.min_interval = 1.0 / calls_per_second
        self._last_call = 0.0

    def wait(self):
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()


class Timer:
    """Context-manager stopwatch."""

    def __init__(self):
        self.start = None
        self.elapsed = 0.0

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed = time.time() - self.start

    def __str__(self):
        return fmt_duration(self.elapsed)
