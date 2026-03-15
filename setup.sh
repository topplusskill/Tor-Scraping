#!/bin/bash

set -e

echo "=== Tor Parser Demo Setup ==="
echo ""

echo "[1/4] Installing system dependencies..."
sudo apt update
sudo apt install -y tor python3-pip python3-venv

echo ""
echo "[2/4] Starting Tor service..."
sudo systemctl start tor
sudo systemctl enable tor

echo ""
echo "[3/4] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo ""
echo "[4/4] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the web UI:"
echo "  source venv/bin/activate"
echo "  python web_ui.py"
echo ""
echo "To use CLI:"
echo "  source venv/bin/activate"
echo "  python cli.py <url> -o downloads"
echo ""
echo "Web UI will be available at: http://localhost:5000"
echo "Demo site: http://torparserdemo.duckdns.org"
