#!/usr/bin/env bash
# Murmur — Fallback WiFi hotspot
#
# Runs at boot after NetworkManager. Waits 30 seconds for a WiFi connection.
# If none is established, creates an open access point named "Murmur-Setup"
# at 10.42.0.1 so the user can connect and configure WiFi via the settings page.
#
set -euo pipefail

WAIT_SECONDS=30
HOTSPOT_SSID="Murmur-Setup"
HOTSPOT_IF="wlan0"

echo "Murmur hotspot: waiting ${WAIT_SECONDS}s for WiFi connection..."

for i in $(seq 1 $WAIT_SECONDS); do
    # Check if wlan0 has an IP (meaning WiFi connected)
    if nmcli -t -f IP4.ADDRESS dev show "$HOTSPOT_IF" 2>/dev/null | grep -q "IP4.ADDRESS"; then
        echo "Murmur hotspot: WiFi connected, no hotspot needed."
        exit 0
    fi
    sleep 1
done

echo "Murmur hotspot: No WiFi connection after ${WAIT_SECONDS}s. Starting hotspot..."

# Remove stale hotspot profile if it exists
nmcli connection delete "$HOTSPOT_SSID" 2>/dev/null || true

# Create open AP
nmcli device wifi hotspot \
    ifname "$HOTSPOT_IF" \
    con-name "$HOTSPOT_SSID" \
    ssid "$HOTSPOT_SSID" \
    band bg \
    password "" || {
    # Some nmcli versions require a password — use a dummy 8-char one
    # but we'll make it open via the 802-11-wireless-security settings
    nmcli device wifi hotspot \
        ifname "$HOTSPOT_IF" \
        con-name "$HOTSPOT_SSID" \
        ssid "$HOTSPOT_SSID" \
        band bg \
        password "00000000"
    # Remove the password to make it open
    nmcli connection modify "$HOTSPOT_SSID" 802-11-wireless-security.key-mgmt none
    nmcli connection up "$HOTSPOT_SSID"
}

echo "Murmur hotspot: AP '$HOTSPOT_SSID' active at 10.42.0.1"
echo "Murmur hotspot: User should connect and visit http://10.42.0.1/settings"
