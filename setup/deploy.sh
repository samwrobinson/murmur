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
echo ""
echo "[3/3] Uploading API, setup, and recorder..."
scp -r api/ "$PI_HOST:$PI_DIR/"
scp -r setup/ "$PI_HOST:$PI_DIR/"
scp murmur_recorder.py "$PI_HOST:$PI_DIR/"
echo "  Files uploaded."

echo ""
echo "=============================="
echo "  Deploy complete!"
echo ""
echo "  Visit: http://murmur.local"
echo "=============================="
