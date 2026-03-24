# Quick Start Guide

## What This Tool Does

Downloads all files from Tor hidden service directories (ransomware leak sites) with:
- Automatic resume if connection drops
- Skip already downloaded files
- Real-time progress tracking
- Works through Tor for anonymity
- **Multi-site support**: Lockbit, DragonForce, INC Ransom
- **Google Drive sync**: Download locally first, then sync to rclone-mounted GDrive
- **Batch mode**: Download from all targets in parallel via `run_all.py`
- **Centralized config**: All constants in `config.py`, shared helpers in `utils.py`

**Download strategy**: Files are downloaded to local `/tmp/` first for speed,
then copied to the rclone-mounted Google Drive folder. This avoids issues with
mount instability during long Tor downloads.

## Supported Sites

| Site | URL Pattern | Status |
|------|-------------|--------|
| **Lockbit** | `lockbit*.onion` | Fully supported |
| **INC Ransom** | `incblog*.onion` | Fully supported (API-based) |
| **DragonForce** | `dragonfor*.onion` | Fully supported (JWT auth) |

Site type is auto-detected from URL, or can be specified manually with `--site-type`.

## Installation

```bash
# Install Tor
sudo apt install tor
sudo systemctl start tor

# Install Python dependencies
pip3 install --break-system-packages requests beautifulsoup4 lxml PySocks

# For Google Drive sync
pip3 install --break-system-packages google-api-python-client google-auth google-auth-httplib2
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
  --site-type TYPE       Site type: auto, lockbit, dragonforce, incransom (default: auto)
  --password PASS        Password for protected disclosures (INC Ransom only)

Google Drive options:
  --mount-gdrive         Download locally, copy to rclone-mounted GDrive
```

## Site-Specific Examples

### Lockbit (Apache-style directory listing)
```bash
python3 cli.py \
  "http://lockbitwnklgh3lt6umrbiztgzl6qujtovdtcovdjhavepp7bpvcmfid.onion/secret/.../company.com/unpack/" \
  -o /data/lockbit-leak
```

### DragonForce (JWT-authenticated file server)
```bash
python3 cli.py \
  "http://dragonforxxbp3awc7mzs5dkswrua3znqyx5roefmi4smjrsdi22xwqd.onion/company.com" \
  -o /data/dragonforce-leak \
  --site-type dragonforce
```

### INC Ransom (API-based with optional password)
```bash
# Public disclosure
python3 cli.py \
  "http://incblog6qu4y4mm4zvw5nrmue6qbwtgjsxpw6b7ixzssu36tsajldoad.onion/blog/disclosures/68001f58516e69ca61f381d6" \
  -o /data/inc-leak \
  --site-type incransom

# Password-protected disclosure
python3 cli.py \
  "http://incblog6qu4y4mm4zvw5nrmue6qbwtgjsxpw6b7ixzssu36tsajldoad.onion/blog/disclosures/..." \
  -o /data/inc-leak \
  --site-type incransom \
  --password "secret123"
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

## Google Drive Sync (rclone mount)

Download via Tor to local disk, then sync to GDrive:

```bash
# Option 1: Automatic via CLI flag
python3 cli.py \
  "http://dragonfor...onion/company.com" \
  -o dragonforce-leak \
  --site-type dragonforce \
  --mount-gdrive

# Option 2: Manual upload after download
rclone copy /tmp/tor-local-dragonforce-leak/ gdrive:dragonforce-leak/ --progress
```

Requires:
1. rclone configured with Google Drive remote (`rclone config`)
2. Service account JSON with domain-wide delegation
3. `impersonate` set in `~/.config/rclone/rclone.conf`

## Batch Mode (run_all.py)

All targets are defined in `targets.json`. Download everything in parallel:

```bash
# Start all targets in separate tmux sessions
python3 run_all.py

# Check status
python3 run_all.py --status

# Stop all
python3 run_all.py --stop

# Attach to specific session
tmux attach -t dl-dragonforce-hartmann-bau
```

Add new targets to `targets.json`:
```json
{
  "name": "new-target",
  "site_type": "dragonforce",
  "url": "http://dragonfor...onion/company.com"
}
```

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
