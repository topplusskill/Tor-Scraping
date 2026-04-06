"""
Path utilities for handling custom output directories.

Supports:
- Paths with spaces (e.g., "/media/psf/FNI DW 1/downloads/")
- Network-mounted directories (Parallels, NFS, SMB, etc.)
- Relative and absolute paths
- Path validation and permission checks
"""

import os
from pathlib import Path
from typing import Tuple, Optional


def validate_output_path(path_str: str) -> Tuple[bool, Optional[Path], str]:
    """
    Validate and normalize output path.
    
    Args:
        path_str: Path string (can contain spaces, be relative or absolute)
        
    Returns:
        (success, normalized_path, error_message)
    """
    try:
        # Expand user home directory and resolve to absolute path
        path = Path(path_str).expanduser().resolve()
        
        # Check if parent directory exists
        if not path.parent.exists():
            return False, None, f"Parent directory does not exist: {path.parent}"
        
        # Check if we can write to parent directory
        if not os.access(path.parent, os.W_OK):
            return False, None, f"No write permission for parent directory: {path.parent}"
        
        # If path exists, check if it's writable
        if path.exists():
            if not path.is_dir():
                return False, None, f"Path exists but is not a directory: {path}"
            if not os.access(path, os.W_OK):
                return False, None, f"No write permission for directory: {path}"
        
        return True, path, ""
        
    except Exception as e:
        return False, None, f"Invalid path: {e}"


def get_disk_stats(path: Path) -> Tuple[float, float, float]:
    """
    Get disk usage statistics for path.
    
    Returns:
        (free_gb, total_gb, used_gb)
    """
    import shutil
    try:
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024**3)
        total_gb = stat.total / (1024**3)
        used_gb = stat.used / (1024**3)
        return free_gb, total_gb, used_gb
    except Exception:
        return 0.0, 0.0, 0.0


def get_directory_stats(path: Path) -> Tuple[int, float]:
    """
    Get statistics for existing files in directory.
    
    Returns:
        (file_count, total_size_gb)
    """
    try:
        files = [f for f in path.glob('**/*') if f.is_file()]
        total_size = sum(f.stat().st_size for f in files)
        size_gb = total_size / (1024**3)
        return len(files), size_gb
    except Exception:
        return 0, 0.0


def format_path_for_display(path: Path) -> str:
    """
    Format path for user-friendly display.
    Handles long paths and special characters.
    """
    path_str = str(path)
    
    # Shorten very long paths
    if len(path_str) > 80:
        parts = path.parts
        if len(parts) > 3:
            return f"{parts[0]}/.../{'/'.join(parts[-2:])}"
    
    return path_str
