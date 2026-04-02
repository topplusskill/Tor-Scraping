# Installation Guide

## Option 1: Using pipx (Recommended - No venv needed)

```bash
# Install pipx
sudo apt update
sudo apt install -y pipx
pipx ensurepath

# Install the tool
cd Tor-Scraping
pipx install .

# Now you can run from anywhere
tor-downloader lockbit-kioti
```

## Option 2: Using pip with --break-system-packages

```bash
cd Tor-Scraping
pip3 install --break-system-packages -r requirements.txt

# Run
python3 tor_downloader.py lockbit-kioti
```

## Option 3: Using virtual environment

```bash
cd Tor-Scraping
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
python3 tor_downloader.py lockbit-kioti

# Deactivate when done
deactivate
```

## Option 4: System-wide with apt (if available)

```bash
# Install Python packages via apt
sudo apt update
sudo apt install -y python3-requests python3-bs4 python3-lxml python3-socks

# Run directly
python3 tor_downloader.py lockbit-kioti
```

## Prerequisites (All Options)

```bash
# Tor is required
sudo apt update && sudo apt install -y tor
sudo systemctl enable --now tor
```

## Troubleshooting Binary

If `./dist/tor-downloader` shows library errors, install missing libraries:

```bash
# Common missing libraries
sudo apt install -y zlib1g libssl3 libffi8

# Check what's missing
ldd ./dist/tor-downloader | grep "not found"
```

**Recommendation**: Use Option 1 (pipx) or Option 4 (apt packages) for simplest setup.
