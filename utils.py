def get_encryption_name(auth_mode):
    """Convert MicroPython auth mode integer to a human-readable string."""
    auth_modes = {
        0: "Open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK",
        4: "WPA/WPA2-PSK", 5: "WPA2-ENTERPRISE", 6: "WPA3-PSK", 7: "WPA2/WPA3-PSK"
    }
    return auth_modes.get(auth_mode, "Unknown")

def get_signal_color_class(rssi):
    """Return a CSS class name based on signal strength."""
    if rssi >= -65: return "good"
    elif rssi >= -80: return "fair"
    else: return "weak"

def format_bssid(bssid_bytes):
    """Format BSSID bytes to a MAC address string."""
    return ":".join("{:02X}".format(b) for b in bssid_bytes)

def calculate_distance(rssi):
    """Estimate distance in meters using simplified Free Space Path Loss for 2.4GHz."""
    # Simplified formula: Distance = 10 ^ ((abs(RSSI) - 40.09) / 20)
    exp = (abs(rssi) - 40.09) / 20.0
    dist = 10 ** exp
    return round(dist, 1)

def rssi_to_percent(rssi):
    """Convert RSSI to a 0-100 percentage for the CSS visual progress bar."""
    pct = 2 * (rssi + 95)
    if pct < 0: return 0
    if pct > 100: return 100
    return int(pct)
