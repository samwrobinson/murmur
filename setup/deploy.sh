#!/usr/bin/env bash
# Murmur — Build frontend on Mac and deploy to Pi
#
# Run from the project root on your Mac:
#   bash setup/deploy.sh
#
set -euo pipefail

PI_HOST="${MURMUR_PI_HOST:-murmur@murmur.local}"
PI_DIR="/home/murmur/murmur"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=============================="
echo "  Murmur — Deploy to Pi"
echo "=============================="

# --- 1. Build frontend ---
echo ""
echo "[1/3] Building frontend..."
cd "$PROJECT_DIR"
npm install
npm run build

if [ ! -f "public/index.html" ]; then
    echo "ERROR: Build failed — public/index.html not found"
    exit 1
fi
echo "  Build complete."

# --- 2. Upload built files ---
echo ""
echo "[2/3] Uploading to Pi ($PI_HOST)..."
scp -r public/ "$PI_HOST:$PI_DIR/"
echo "  Frontend uploaded."

# --- 3. Upload API, setup, and recorder ---
# Use rsync for api/ to exclude data files that live only on the Pi
echo ""
echo "[3/3] Uploading API, setup, and recorder..."
rsync -av --exclude 'journal.db*' --exclude 'audio/' --exclude 'settings.json' --exclude '__pycache__/' api/ "$PI_HOST:$PI_DIR/api/"
scp -r setup/ "$PI_HOST:$PI_DIR/"
scp murmur_recorder.py "$PI_HOST:$PI_DIR/"
echo "  Files uploaded."

# --- 4. Restart services ---
echo ""
echo "[4/4] Restarting services on Pi..."
ssh "$PI_HOST" "sudo systemctl restart murmur-api murmur-recorder"
echo "  Services restarted."

echo ""
echo "=============================="
echo "  Deploy complete!"
echo ""
echo "  Visit: http://murmur.local"
echo "=============================="
