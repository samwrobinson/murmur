"""
Murmur — WiFi management via NetworkManager (nmcli).

All functions shell out to `nmcli -t` (terse/machine-parseable output)
with subprocess timeouts so nothing blocks the Flask request forever.
"""

import subprocess

NMCLI_TIMEOUT = 10  # seconds for most commands
SCAN_TIMEOUT = 30   # scanning can be slow


def _run(cmd, timeout=NMCLI_TIMEOUT):
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def get_wifi_status():
    """Return current WiFi connection info: ssid, ip, signal, active."""
    # Get active WiFi connection
    rc, out, _ = _run([
        "nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,FREQ", "dev", "wifi",
    ])
    if rc != 0:
        return {"active": False, "ssid": None, "signal": None, "ip": None}

    ssid = None
    signal = None
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[0] == "yes":
            ssid = parts[1]
            signal = int(parts[2]) if parts[2].isdigit() else None
            break

    # Get IP address
    ip = None
    if ssid:
        rc2, out2, _ = _run([
            "nmcli", "-t", "-f", "IP4.ADDRESS", "dev", "show", "wlan0",
        ])
        if rc2 == 0:
            for line in out2.splitlines():
                if line.startswith("IP4.ADDRESS"):
                    # Format: IP4.ADDRESS[1]:192.168.1.5/24
                    addr = line.split(":", 1)[1] if ":" in line else ""
                    ip = addr.split("/")[0] if addr else None
                    break

    return {
        "active": ssid is not None,
        "ssid": ssid,
        "signal": signal,
        "ip": ip,
    }


def scan_networks():
    """Trigger a WiFi rescan and return available networks (deduplicated, sorted by signal)."""
    # Trigger rescan
    _run(["nmcli", "dev", "wifi", "rescan"], timeout=SCAN_TIMEOUT)

    # List networks
    rc, out, _ = _run([
        "nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,BARS", "dev", "wifi", "list",
    ])
    if rc != 0:
        return []

    seen = {}
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 3:
            continue
        ssid = parts[0]
        if not ssid:
            continue
        signal = int(parts[1]) if parts[1].isdigit() else 0
        security = parts[2] if len(parts) > 2 else ""

        # Keep the strongest signal for each SSID
        if ssid not in seen or signal > seen[ssid]["signal"]:
            seen[ssid] = {
                "ssid": ssid,
                "signal": signal,
                "security": security,
                "secured": security != "" and security != "--",
            }

    # Sort by signal strength descending
    networks = sorted(seen.values(), key=lambda n: n["signal"], reverse=True)
    return networks


def get_saved_networks():
    """List saved WiFi connection profiles."""
    rc, out, _ = _run([
        "nmcli", "-t", "-f", "NAME,TYPE", "connection", "show",
    ])
    if rc != 0:
        return []

    saved = []
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and "wireless" in parts[1]:
            saved.append({"ssid": parts[0]})
    return saved


def _deactivate_hotspot():
    """Tear down the fallback hotspot connection if it's active."""
    rc, out, _ = _run([
        "nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active",
    ])
    if rc != 0:
        return
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[0] == "Murmur-Setup":
            _run(["nmcli", "connection", "down", "Murmur-Setup"])
            break


def connect_to_network(ssid, password=None):
    """Connect to a WiFi network. Reuses saved profile if it exists."""
    # First, tear down hotspot if active
    _deactivate_hotspot()

    # Check if we already have a saved profile for this SSID
    saved = get_saved_networks()
    saved_ssids = [n["ssid"] for n in saved]

    if ssid in saved_ssids:
        # Reuse existing profile
        rc, out, err = _run(["nmcli", "connection", "up", ssid], timeout=SCAN_TIMEOUT)
    elif password:
        # Connect with password
        rc, out, err = _run([
            "nmcli", "dev", "wifi", "connect", ssid, "password", password,
        ], timeout=SCAN_TIMEOUT)
    else:
        # Open network
        rc, out, err = _run([
            "nmcli", "dev", "wifi", "connect", ssid,
        ], timeout=SCAN_TIMEOUT)

    if rc == 0:
        return {"success": True, "message": f"Connected to {ssid}"}
    else:
        return {"success": False, "message": err or "Connection failed"}


def forget_network(ssid):
    """Remove a saved WiFi connection profile."""
    rc, out, err = _run(["nmcli", "connection", "delete", ssid])
    if rc == 0:
        return {"success": True, "message": f"Forgot {ssid}"}
    else:
        return {"success": False, "message": err or "Failed to forget network"}
