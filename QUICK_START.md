# Quick Start Guide

## What This Tool Does

Downloads all files from Tor hidden service directories (ransomware leak sites) with:
- Automatic resume if connection drops
- Skip already downloaded files
- Real-time progress tracking
- Works through Tor for anonymity

**Important**: Leak sites typically have two formats:
1. **Large archive** (e.g., 261 GB .7z file) - single file, hard to resume
2. **Unpacked directory** (e.g., /unpack/) - thousands of files, 200+ GB total

This tool is designed for option 2 - downloading unpacked directories file-by-file with resume capability.

## Installation

```bash
# Install Tor
sudo apt install tor
sudo systemctl start tor

# Install Python dependencies
pip3 install --break-system-packages requests beautifulsoup4 lxml PySocks
```

## Basic Usage

### Download entire directory

```bash
cd /home/ubuntu/CascadeProjects/tor-parser-demo

python3 cli.py \
  "http://lockbitwnklgh3lt6umrbiztgzl6qujtovdtcovdjhavepp7bpvcmfid.onion/secret/8aa7b9d90019fa9987bcf7a3c1cce477-e4045a91-e06d-3a8c-b658-2ec374f1337f/kioti.com/" \
  -o /data/kioti
```

### What happens:
1. Connects through Tor
2. Crawls all directories recursively
3. Downloads files as they are found
4. Saves progress to `/data/kioti/.progress.json`
5. Skips already downloaded files automatically

### If download is interrupted:

Just run the same command again. It will:
- Load previous progress
- Skip already downloaded files
- Continue from where it stopped

**No need for special resume flag** - it's automatic.

## Real World Example

### Typical Lockbit Site Structure
```
kioti.com/
├── kioti.com.7z              # 261 GB archive (hard to download)
├── kioti.com.7z-file-tree.txt # 65 MB file list
├── kioti.com.7z.torrent       # 21 MB torrent
└── unpack/                    # 200+ GB unpacked files (USE THIS)
    ├── Accounting/
    ├── HR/
    ├── Finance/
    └── ...
```

### Download Full Unpacked Directory (200+ GB)
```bash
python3 cli.py \
  "http://lockbitwnklgh3lt6umrbiztgzl6qujtovdtcovdjhavepp7bpvcmfid.onion/secret/8aa7b9d90019fa9987bcf7a3c1cce477-e4045a91-e06d-3a8c-b658-2ec374f1337f/kioti.com/unpack/" \
  -o /data/kioti-leak \
  --max-depth 10

# This will download ALL files from unpack/ directory
# Expected size: 200+ GB
# Time: Several hours to days (depending on Tor speed)
```

### Download Specific Department Only
```bash
# Only Accounting department (~20-50 GB)
python3 cli.py \
  "http://.../kioti.com/unpack/Accounting/" \
  -o /data/accounting-only

# Only HR department (~5-10 GB)
python3 cli.py \
  "http://.../kioti.com/unpack/HR/" \
  -o /data/hr-only
```

### Output Structure
```
/data/kioti-leak/
├── Accounting/
│   ├── Controller/
│   │   ├── Budget/
│   │   │   └── 2024-Q1.xlsx
│   │   └── Tax/
│   └── ...
├── HR/
├── Finance/
└── .progress.json (tracking file)
```

## Options

```bash
python3 cli.py <URL> [options]

Required:
  URL                    Target .onion URL to download

Options:
  -o, --output DIR       Output directory (default: downloads)
  --max-depth N          Maximum directory depth (default: 10)
  --tor-proxy PROXY      Tor proxy (default: socks5h://127.0.0.1:9050)
```

## Progress Tracking

The tool shows real-time progress:

```
Crawling depth 3... Found 1247 files, Downloaded 856, Skipped 234, Failed 2
[857/1247] Downloading: Accounting/Controller/Budget/2024-Q1.xlsx
```

Progress is saved after each file, so you can:
- Stop anytime (Ctrl+C)
- Restart later
- Check what failed in `.progress.json`

## Output Structure

```
/data/kioti/
├── .progress.json          # Progress tracking (don't delete!)
├── Accounting/             # Mirrors site structure
│   ├── file1.xlsx
│   └── Controller/
│       └── file2.pdf
└── download.log            # Detailed logs
```

## Troubleshooting

### "Connection refused"
Tor is not running:
```bash
sudo systemctl start tor
sudo systemctl status tor
```

### "Timeout"
Tor is slow, just wait or restart:
```bash
sudo systemctl restart tor
```

### Check what failed
```bash
cat /data/kioti/.progress.json | grep -A 5 "failed"
```

### Re-download failed files
Delete them from `.progress.json` "failed" list and run again.

## Performance

- **Speed**: ~500 KB/s through Tor (varies, can be slower)
- **Memory**: ~150 MB total
- **Resume**: Instant (loads from .progress.json)
- **Duplicates**: Automatically skipped

### Expected Download Times

| Data Size | Estimated Time | Notes |
|-----------|---------------|-------|
| 1 GB | ~30-60 minutes | Single department |
| 10 GB | ~5-10 hours | Multiple departments |
| 50 GB | ~1-2 days | Large leak |
| 200+ GB | ~3-7 days | Full unpacked directory |

**Note**: Tor speed varies significantly. These are rough estimates.

### Disk Space Requirements

Before downloading, check available space:
```bash
df -h /data
```

For full leak downloads, ensure you have:
- **300+ GB free** for safety (200 GB data + overhead)
- **SSD recommended** for better performance

## What Gets Downloaded

Everything in the directory structure:
- Documents (.pdf, .docx, .xlsx)
- Archives (.zip, .7z, .rar)
- Images (.jpg, .png)
- Databases (.sql, .db)
- Any other files

## Security Notes

- All traffic goes through Tor
- Your IP is hidden from the target site
- Files are saved locally only
- No data is sent anywhere else

## For Automation

Run in background:
```bash
nohup python3 cli.py "http://..." -o /data/output > /tmp/download.log 2>&1 &
```

Check progress:
```bash
tail -f /tmp/download.log
```

## Common Use Cases

### 1. Download specific subdirectory
```bash
python3 cli.py \
  "http://site.onion/leak/company/Accounting/" \
  -o /data/accounting-only
```

### 2. Limit depth for faster crawl
```bash
python3 cli.py \
  "http://site.onion/leak/" \
  -o /data/leak \
  --max-depth 3
```

### 3. Resume after interruption
```bash
# Just run the same command again
python3 cli.py "http://site.onion/leak/" -o /data/leak
```

## File Verification

Check downloaded files:
```bash
# Count files
find /data/kioti -type f | wc -l

# Check sizes
du -sh /data/kioti

# List largest files
find /data/kioti -type f -exec du -h {} + | sort -rh | head -20
```

## That's It!

The tool is designed to be simple:
1. Run command
2. Wait (or come back later)
3. All files downloaded

No complex configuration needed.
