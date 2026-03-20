# Tor Parser Demo

A Python-based tool for downloading files from Tor hidden services with resume capability and fault tolerance.

## Features

- SOCKS5 proxy support for Tor network
- Resume interrupted downloads using HTTP Range headers
- Recursive directory crawling
- Retry logic with exponential backoff
- CLI interface for automation
- **Multi-site support**: Lockbit, DragonForce, INC Ransom
- Auto-detection of site type from URL
- Site-specific parsers with API support

## Prerequisites

- Python 3.8+
- Tor service running on localhost:9050

## Installation

### 1. Install Tor

```bash
sudo apt update
sudo apt install tor
sudo systemctl start tor
sudo systemctl enable tor
```

Verify Tor is running:
```bash
sudo systemctl status tor
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

## Usage

### CLI

Basic usage:

```bash
python cli.py http://example.onion/path/ -o downloads
```

Options:
- `-o, --output`: Output directory (default: downloads)
- `-r, --resume`: Resume from previous run
- `--max-depth`: Maximum recursion depth (default: 10)
- `--tor-proxy`: Tor SOCKS5 proxy (default: socks5h://127.0.0.1:9050)

Example with all options:

```bash
python cli.py http://example.onion/path/ \
  -o /path/to/downloads \
  --max-depth 5 \
  --tor-proxy socks5h://127.0.0.1:9050
```

Resume interrupted download:

```bash
python cli.py http://example.onion/path/ -o downloads -r
```

## Architecture

### Core Components

1. **downloader.py**: Handles file downloads with resume capability
   - Creates Tor session with SOCKS5 proxy
   - Implements chunked streaming downloads
   - Supports HTTP Range headers for resume
   - Retry logic with exponential backoff

2. **parser.py**: Parses directory structures
   - Extracts file and directory links
   - Recursive crawling with depth limit
   - Filters navigation elements

3. **cli.py**: Command-line interface
   - Argument parsing
   - Progress tracking
   - Session persistence
   - Real-time progress display
   - Auto-detection of site type

4. **parsers/**: Site-specific parsing modules
   - `base.py`: Abstract base class for parsers
   - `lockbit.py`: Apache-style directory listings
   - `dragonforce.py`: JWT-authenticated file server
   - `incransom.py`: API-based with CDN support

## Configuration

### Tor Settings

Default Tor SOCKS5 proxy: `127.0.0.1:9050`

To use a different port, edit `/etc/tor/torrc`:

```
SocksPort 9050
```

Restart Tor after changes:

```bash
sudo systemctl restart tor
```

### Download Settings

Edit in code or pass as CLI arguments:
- Timeout: 60 seconds (default)
- Chunk size: 8192 bytes
- Max retries: 3-5 attempts
- Backoff factor: 2x

## Troubleshooting

### Tor connection failed

Check Tor service:
```bash
sudo systemctl status tor
```

Test Tor connectivity:
```bash
curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org
```

### Downloads timing out

Increase timeout in `downloader.py`:
```python
TorDownloader(timeout=120)
```

### Permission errors

Ensure output directory is writable:
```bash
chmod 755 downloads
```

## Security Notes

- This tool is designed for legitimate data recovery and archival purposes
- Always verify you have authorization to download content
- Tor provides anonymity but not complete security
- Use responsibly and in compliance with applicable laws

## Development

Project structure:
```
tor-parser-demo/
├── downloader.py       # Core download logic
├── parser.py           # Legacy directory parsing
├── cli.py              # CLI interface
├── parsers/            # Site-specific parsers
│   ├── __init__.py
│   ├── base.py         # Abstract base class
│   ├── lockbit.py      # Lockbit parser
│   ├── dragonforce.py  # DragonForce parser
│   └── incransom.py    # INC Ransom parser
├── requirements.txt    # Python dependencies
├── README.md           # Documentation
├── QUICK_START.md      # Quick start guide
└── setup.sh            # Installation script
```

## Troubleshooting

### Connection Issues

If you encounter connection errors:

1. Check Tor service status:
```bash
sudo systemctl status tor@default
```

2. Restart Tor if needed:
```bash
sudo systemctl restart tor
```

3. Verify Tor connectivity:
```bash
curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip
```

### Slow Download Speed

Tor network speed varies significantly. Typical speeds are 200-500 KB/s. If downloads are extremely slow:

- Try restarting Tor to get a new circuit
- Check your internet connection
- Consider downloading during off-peak hours

### Resume Not Working

If resume functionality doesn't work:

- Check that `.progress.json` exists in output directory
- Verify file permissions on output directory
- Ensure you're using the same output path

## License

This project is provided as-is for educational and legitimate use cases only.
