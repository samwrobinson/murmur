#!/usr/bin/env bash
# Murmur — Raspberry Pi setup script
# Run once on a fresh Raspberry Pi OS Lite install:
#   sudo bash setup/setup.sh
set -euo pipefail

MURMUR_HOME="/home/murmur/murmur"
SHARE_DIR="/home/murmur/share"

echo "=============================="
echo "  Murmur — Pi Setup"
echo "=============================="

# --- 1. System packages ---
echo ""
echo "[1/6] Updating system and installing packages..."
apt-get update -y
apt-get install -y \
    python3 python3-pip python3-venv \
    nginx samba avahi-daemon \
    ffmpeg

# --- 2. Python dependencies ---
echo ""
echo "[2/6] Installing Python dependencies..."
python3 -m pip install --break-system-packages \
    flask flask-cors openai-whisper

# --- 3. Create directories ---
echo ""
echo "[3/6] Creating directories..."
mkdir -p "$SHARE_DIR/entries"
mkdir -p "$SHARE_DIR/audio"
mkdir -p "$SHARE_DIR/favorites"
mkdir -p "$MURMUR_HOME/api/audio"
chown -R murmur:murmur "$SHARE_DIR"
chown -R murmur:murmur "$MURMUR_HOME"

# --- 4. nginx ---
echo ""
echo "[4/6] Configuring nginx..."
cp "$MURMUR_HOME/setup/nginx-murmur.conf" /etc/nginx/sites-available/murmur
ln -sf /etc/nginx/sites-available/murmur /etc/nginx/sites-enabled/murmur
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx

# --- 5. Samba ---
echo ""
echo "[5/6] Configuring Samba share..."
# Append Murmur share config if not already present
if ! grep -q "\[Murmur\]" /etc/samba/smb.conf; then
    cat "$MURMUR_HOME/setup/smb-murmur.conf" >> /etc/samba/smb.conf
fi
systemctl enable smbd
systemctl restart smbd

# --- 6. systemd services ---
echo ""
echo "[6/6] Installing systemd services..."
cp "$MURMUR_HOME/setup/murmur-api.service" /etc/systemd/system/
cp "$MURMUR_HOME/setup/murmur-sync.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable murmur-api
systemctl enable murmur-sync
systemctl start murmur-api
systemctl start murmur-sync

echo ""
echo "=============================="
echo "  Setup complete!"
echo ""
echo "  Web app:       http://murmur.local"
echo "  Shared folder:  smb://murmur.local/Murmur"
echo ""
echo "  Reboot now:  sudo reboot"
echo "=============================="
