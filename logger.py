# logger.py — Persistent client log to ESP32 flash memory
# Logs are stored in /client_log.txt and survive reboots.
# Read back via Thonny: open('/client_log.txt') or Tools > Open system shell

MAX_LOG_LINES = 50  # Keep last 50 entries to avoid filling flash

def log_client(ip, mac, device, browser):
    """Append a timestamped client entry to the log file."""
    try:
        import time
        ts = time.localtime()  # (year, month, day, hour, min, sec, weekday, yearday)
        timestamp = "{:02d}:{:02d}:{:02d}".format(ts[3], ts[4], ts[5])
        entry = "[{}] IP:{} MAC:{} | {} via {}\n".format(
            timestamp, ip, mac, device, browser)

        # Read existing lines
        try:
            with open('/client_log.txt', 'r') as f:
                lines = f.readlines()
        except OSError:
            lines = []

        # Append new entry, keep last MAX_LOG_LINES
        lines.append(entry)
        if len(lines) > MAX_LOG_LINES:
            lines = lines[-MAX_LOG_LINES:]

        # Write back
        with open('/client_log.txt', 'w') as f:
            f.writelines(lines)

    except Exception as e:
        print("Logger error:", e)

def read_log():
    """Return all log entries as a string (for /log HTTP route)."""
    try:
        with open('/client_log.txt', 'r') as f:
            return f.read()
    except OSError:
        return "No log entries yet."

def clear_log():
    """Wipe the log file."""
    try:
        with open('/client_log.txt', 'w') as f:
            f.write("")
    except Exception as e:
        print("Clear log error:", e)
