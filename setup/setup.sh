#!/usr/bin/env bash
# Murmur — Raspberry Pi full setup script
#
# Run once on a fresh Raspberry Pi OS install after cloning the repo:
#   cd ~/murmur && sudo bash setup/setup.sh
#
# Prerequisites:
#   - Raspberry Pi OS (Bookworm/Trixie) with WiFi configured via Imager
#   - WhisPlay HAT driver already installed (~/Whisplay/Driver/)
#   - Git repo cloned to ~/murmur
#   - Frontend already built (public/ directory populated via deploy.sh from Mac)
#
set -euo pipefail

MURMUR_HOME="/home/murmur/murmur"
SHARE_DIR="/home/murmur/share"

echo "=============================="
echo "  Murmur — Pi Setup"
echo "=============================="

# --- 1. System packages ---
echo ""
echo "[1/7] Installing system packages..."
apt-get update -y
apt-get install -y \
    python3 python3-flask python3-flask-cors python3-requests \
    python3-pil \
    nginx samba avahi-daemon \
    alsa-utils \
    sox

echo ""
echo "[2/7] Skipping local whisper — cloud transcription is used"

# --- 3. Create directories ---
echo ""
echo "[3/7] Creating directories..."
mkdir -p "$SHARE_DIR/entries"
mkdir -p "$SHARE_DIR/audio"
mkdir -p "$SHARE_DIR/favorites"
mkdir -p "$MURMUR_HOME/api/audio"
chown -R murmur:murmur "$SHARE_DIR"
chown -R murmur:murmur "$MURMUR_HOME"

# --- 4. nginx ---
echo ""
echo "[4/7] Configuring nginx..."
cp "$MURMUR_HOME/setup/nginx-murmur.conf" /etc/nginx/sites-available/murmur
ln -sf /etc/nginx/sites-available/murmur /etc/nginx/sites-enabled/murmur
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx

# --- 5. Samba ---
echo ""
echo "[5/7] Configuring Samba share..."
if ! grep -q "\[Murmur\]" /etc/samba/smb.conf; then
    cat "$MURMUR_HOME/setup/smb-murmur.conf" >> /etc/samba/smb.conf
fi
systemctl enable smbd
systemctl restart smbd

# --- 6. systemd services ---
echo ""
echo "[6/7] Installing systemd services..."
cp "$MURMUR_HOME/setup/murmur-api.service" /etc/systemd/system/
cp "$MURMUR_HOME/setup/murmur-sync.service" /etc/systemd/system/
cp "$MURMUR_HOME/setup/murmur-recorder.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable murmur-api murmur-sync murmur-recorder
systemctl start murmur-api
systemctl start murmur-sync
# Recorder starts but may show errors until reboot loads WM8960 overlay
systemctl start murmur-recorder || echo "  Note: recorder may need reboot for audio HAT"

# --- 7. Verify ---
echo ""
echo "[7/7] Verifying..."
sleep 2

if systemctl is-active --quiet murmur-api; then
    echo "  murmur-api:      RUNNING"
else
    echo "  murmur-api:      FAILED (check: sudo journalctl -u murmur-api)"
fi

if systemctl is-active --quiet murmur-sync; then
    echo "  murmur-sync:     RUNNING"
else
    echo "  murmur-sync:     FAILED (check: sudo journalctl -u murmur-sync)"
fi

if systemctl is-active --quiet murmur-recorder; then
    echo "  murmur-recorder: RUNNING"
else
    echo "  murmur-recorder: NOT RUNNING (normal before reboot)"
fi

if systemctl is-active --quiet nginx; then
    echo "  nginx:           RUNNING"
else
    echo "  nginx:           FAILED (check: sudo journalctl -u nginx)"
fi

echo ""
echo "=============================="
echo "  Setup complete!"
echo ""
echo "  Web app:        http://murmur.local"
echo "  API:            http://murmur.local:5001"
echo "  Samba share:    smb://murmur.local/Murmur"
echo ""
echo "  IMPORTANT: If this is a fresh install, you need to"
echo "  deploy the frontend from your Mac first:"
echo "    cd ~/Desktop/Murmur/murmur"
echo "    bash setup/deploy.sh"
echo ""
echo "  Then reboot:    sudo reboot"
echo "=============================="
