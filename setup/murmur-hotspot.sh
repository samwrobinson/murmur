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
    # Check if wlan0 has an actual IP address (not just the field name)
    IP_LINE=$(nmcli -t -f IP4.ADDRESS dev show "$HOTSPOT_IF" 2>/dev/null | grep "IP4.ADDRESS" || true)
    if [ -n "$IP_LINE" ]; then
        # Extract the value after the colon — e.g. "IP4.ADDRESS[1]:192.168.1.5/24"
        IP_VAL="${IP_LINE#*:}"
        if [ -n "$IP_VAL" ]; then
            echo "Murmur hotspot: WiFi connected ($IP_VAL), no hotspot needed."
            exit 0
        fi
    fi
    sleep 1
done

echo "Murmur hotspot: No WiFi connection after ${WAIT_SECONDS}s. Starting hotspot..."

# Remove stale hotspot profile if it exists
nmcli connection delete "$HOTSPOT_SSID" 2>/dev/null || true

# Create AP with a simple password (open networks are unreliable across nmcli versions)
nmcli device wifi hotspot \
    ifname "$HOTSPOT_IF" \
    con-name "$HOTSPOT_SSID" \
    ssid "$HOTSPOT_SSID" \
    band bg \
    password "murmur42" || {
    echo "Murmur hotspot: first attempt failed, retrying..."
    nmcli connection delete "$HOTSPOT_SSID" 2>/dev/null || true
    sleep 2
    nmcli device wifi hotspot \
        ifname "$HOTSPOT_IF" \
        con-name "$HOTSPOT_SSID" \
        ssid "$HOTSPOT_SSID" \
        band bg \
        password "murmur42"
}

echo "Murmur hotspot: AP '$HOTSPOT_SSID' active at 10.42.0.1 (password: murmur42)"
echo "Murmur hotspot: User should connect and visit http://10.42.0.1/settings"
