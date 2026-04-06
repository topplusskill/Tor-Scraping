# Tor Parser

A robust Python CLI tool for downloading files from Tor hidden services (.onion)
with automatic resume, fault tolerance, and Google Drive synchronization via rclone.

## Features

- **Multi-site support** — Lockbit, DragonForce, INC Ransom with site-specific parsers
- **Resume large downloads** — HTTP Range-based resume survives connection drops (261 GB+ tested)
- **Retry with backoff** — exponential backoff up to 50 attempts per file
- **Google Drive sync** — download locally, then copy to rclone-mounted GDrive folder
- **Batch mode** — run all targets in parallel tmux sessions via `run_all.py`
- **Auto-detection** — site type inferred from URL pattern
- **Progress tracking** — real-time CLI output + JSON progress persistence
- **Centralized config** — all constants in `config.py`, environment variable overrides

## Supported Sites

| Site | Parser | Auth | Notes |
|------|--------|------|-------|
| **Lockbit** | `LockbitParser` | None | Apache-style directory listing. Skips `unpack/` by default. |
| **DragonForce** | `DragonForceParser` | JWT (auto) | Token extracted from iframe, auto-refreshed before expiry. |
| **INC Ransom** | `INCRansomParser` | API + CDN | REST API backend, optional password, CAPTCHA bypass via cookies. |

## Prerequisites

- Python 3.8+
- Tor service on `localhost:9050`
- rclone (for Google Drive sync)

## Installation

```bash
# Only Tor is required!
sudo apt update && sudo apt install -y tor
sudo systemctl enable --now tor

# No Python dependencies needed - use the binary!
```

## Quick Start

### Simple - Use Binary (Recommended)
```bash
# Just the target name from targets.json
./dist/tor-downloader lockbit-kioti
./dist/tor-downloader dragonforce-hartmann
./dist/tor-downloader incransom-68001f58
```

### Or Use Full URL
```bash
./dist/tor-downloader "http://lockbit...onion/secret/.../company.com/"
```

### Download Specific Folder
```bash
./dist/tor-downloader dragonforce-hartmann --path "/Accounting"
```

### Custom Output Directory
```bash
# Download to custom location (supports paths with spaces)
./dist/tor-downloader lockbit-kioti -o "/media/psf/FNI DW 1/downloads/lockbit-kioti"

# Resume download in existing directory
python3 tor_downloader.py lockbit-kioti -o "/path/to/existing/folder"

# Relative path
./dist/tor-downloader dragonforce-hartmann -o "./my-downloads/hartmann"
```

**Default behavior:**
- Downloads to `downloads/<target-name>/` folder relative to script
- Downloads ALL files (unlimited depth)
- Auto-detects site type
- Resume support enabled (HTTP Range) - continues from where it stopped
- Retry up to 50 times per file
- **No Python installation needed!**

### Alternative: Use Python Script
```bash
# If you prefer Python script
pip3 install -r requirements.txt
python3 tor_downloader.py lockbit-kioti
```

## CLI Reference

```
./dist/tor-downloader <TARGET> [options]

Required:
  TARGET                     Target name from targets.json OR full .onion URL

Options:
  -o, --output DIR           Output directory (default: downloads/)
  --path PATH                Specific folder path (default: download ALL)
  --max-depth N              Max recursion depth (default: 999 = unlimited)
  --site-type TYPE           auto | lockbit | dragonforce | incransom (default: auto)
  --tor-proxy URL            Tor SOCKS5 proxy (default: socks5h://127.0.0.1:9050)
  --password PASS            Password for INC Ransom
  --cookies FILE             Cookies file for INC Ransom CAPTCHA bypass
  --resume                   Resume from previous run
  --log-file FILE            Log file (default: download.log)
```

Available targets in targets.json:
- lockbit-kioti
- dragonforce-hartmann
- incransom-68001f58

## Architecture

```
Tor-Scraping/
├── dist/
│   └── tor-downloader      # Standalone binary (18MB) - NO DEPENDENCIES!
├── tor_downloader.py       # Main CLI script (if using Python)
├── downloader.py           # HTTP Range resume engine
├── config.py               # Constants and tunables
├── utils.py                # Shared helpers
├── targets.json            # Target definitions with simple names
├── parsers/
│   ├── __init__.py         # Parser registry
│   ├── base.py             # Abstract base class
│   ├── lockbit.py          # Apache directory listing
│   ├── dragonforce.py      # JWT auth + auto token refresh
│   └── incransom.py        # REST API + CDN downloads
├── README.md               # Full documentation
├── QUICK_START.md          # Quick start guide
└── requirements.txt        # Python dependencies (only if not using binary)
```

### Data Flow

```
┌─────────────┐     Tor/SOCKS5     ┌──────────────┐
│  .onion     │ ◄───────────────── │  cli.py       │
│  site       │ ──────────────────►│  + parser     │
└─────────────┘    crawl / download└──────┬───────┘
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                    /tmp/tor-local-*   .progress.json   logs
                          │
                    shutil.copy2
                          │
                          ▼
                    /mnt/gdrive/*  (rclone mount)
                          │
                    Google Drive
```

### Key Modules

- **`config.py`** — all timeouts, chunk sizes, mount paths, site-specific constants
- **`utils.py`** — `fmt_size()`, `fmt_duration()`, `file_sha256()`, `RateLimiter`, `Timer`
- **`downloader.py`** — `TorDownloader` with `(120s, ∞)` timeout, 256KB chunks, resume loop
- **`cloud_sync.py`** — `GDriveMount` class: auto-mount, health check, remount on failure
- **`parsers/base.py`** — `BaseParser` ABC with `parse_directory()`, `get_download_url()`, `crawl_recursive()`

## Google Drive via rclone

### Setup

```bash
# Configure rclone with service account
rclone config
# → New remote: gdrive
# → Type: Google Drive
# → Service account file: /path/to/sa.json
# → Impersonate: user@domain.com
# → Root folder ID: <shared folder ID>
```

### How it works

1. `run_all.py` (or `--mount-gdrive`) mounts `gdrive:` at `/mnt/gdrive`
2. Files download to `/tmp/tor-local-<target>/` first (fast local I/O)
3. After each file completes, `shutil.copy2` copies it to `/mnt/gdrive/<target>/`
4. Mount health is checked periodically; auto-remount on failure

### Manual upload (if mount was lost)

```bash
rclone copy /tmp/tor-local-lockbit-kioti/ gdrive:lockbit-kioti/ --progress
```

## Configuration

All constants live in `config.py` and can be overridden via environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `TOR_PROXY` | `socks5h://127.0.0.1:9050` | Tor SOCKS5 proxy URL |
| `GDRIVE_MOUNT` | `/mnt/gdrive` | rclone mount point |
| `RCLONE_REMOTE` | `gdrive:` | rclone remote name |

## Troubleshooting

### Tor connection failed / TTL expired
```bash
sudo systemctl restart tor
# Wait 10-15 seconds for circuits to rebuild
```

### Download stuck at same percentage
The .onion site may be throttling or overloaded. The downloader will keep
retrying with exponential backoff (up to 50 attempts). Restart Tor to get
a fresh circuit.

### rclone mount not responsive
```bash
fusermount -uz /mnt/gdrive
# Then re-run your command; it will auto-remount
```

### Verify downloaded file integrity
```bash
python3 -c "from utils import file_sha256; print(file_sha256('/path/to/file'))"
```

## Performance

| Metric | Typical | Notes |
|--------|---------|-------|
| Tor speed | 0.5–5 MB/s | Varies by circuit and hidden service load |
| Resume overhead | < 1s | Reads `.progress.json`, sends Range header |
| Memory usage | ~150 MB | Streaming downloads, no full file buffering |

## License

This project is provided as-is for educational and legitimate data recovery purposes only.
