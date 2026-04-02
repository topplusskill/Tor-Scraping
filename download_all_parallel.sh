#!/bin/bash
# Parallel downloader for all DragonForce companies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${1:-downloads}"
WORKERS="${2:-8}"
DRAGONFORCE_URL="http://dragonforxxbp3awc7mzs5dkswrua3znqyx5roefmi4smjrsdi22xwqd.onion/"

echo "=== DragonForce Parallel Downloader ==="
echo "Output: $OUTPUT_DIR"
echo "Workers: $WORKERS"
echo ""

# Step 1: Get list of all companies
echo "[1/3] Fetching company list..."
python3 "$SCRIPT_DIR/tor_downloader.py" "$DRAGONFORCE_URL" --all --list-only -o "$OUTPUT_DIR"

COMPANIES_FILE="$OUTPUT_DIR/companies.json"

if [ ! -f "$COMPANIES_FILE" ]; then
    echo "Error: companies.json not found"
    exit 1
fi

TOTAL=$(jq length "$COMPANIES_FILE")
echo ""
echo "[2/3] Found $TOTAL companies"
echo ""

# Step 2: Create download script for each company
echo "[3/3] Starting parallel download with $WORKERS workers..."
echo ""

# Function to download one company
download_company() {
    local url="$1"
    local output_dir="$2"
    local company_name=$(echo "$url" | sed 's|.*/||' | sed 's|/$||')
    local log_file="$output_dir/$company_name.log"
    
    echo "[$(date '+%H:%M:%S')] Starting: $company_name"
    
    python3 "$SCRIPT_DIR/tor_downloader.py" "$url" -o "$output_dir/$company_name" \
        --log-file "$log_file" 2>&1 | tee -a "$log_file" | grep -E "(Found|Downloaded|Error)" || true
    
    echo "[$(date '+%H:%M:%S')] Completed: $company_name"
}

export -f download_company
export SCRIPT_DIR OUTPUT_DIR

# Run in parallel using xargs
jq -r '.[].url' "$COMPANIES_FILE" | \
    xargs -P "$WORKERS" -I {} bash -c 'download_company "{}" "$OUTPUT_DIR"'

echo ""
echo "=== Download Complete ==="
echo "Check logs in: $OUTPUT_DIR/*.log"
