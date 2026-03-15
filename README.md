# Tor Parser Demo

A Python-based tool for downloading files from Tor hidden services with resume capability and fault tolerance.

## Features

- SOCKS5 proxy support for Tor network
- Resume interrupted downloads using HTTP Range headers
- Recursive directory crawling
- Retry logic with exponential backoff
- CLI interface for automation

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
├── parser.py           # Directory parsing
├── cli.py              # CLI interface
├── requirements.txt    # Python dependencies
├── README.md           # Documentation
├── QUICK_START.md      # Quick start guide
└── setup.sh            # Installation script
```

## License

This project is provided as-is for educational and legitimate use cases only.
