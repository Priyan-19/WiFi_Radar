import network  # type: ignore  (MicroPython built-in)
import time

class WiFiScanner:
    def __init__(self):
        # Initialize the ESP32 in Station (STA) mode to scan for networks
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)

    def scan(self, passes=3, delay_ms=200):
        """
        Scans for nearby Wi-Fi networks using multiple passes to overcome
        the AP+STA coexistence channel-dwell limitation on ESP32.
        Each pass captures a different subset of channels; merging them
        gives a much more complete picture than a single scan.
        Returns networks sorted by signal strength (strongest first).
        """
        seen = {}  # keyed by BSSID bytes to deduplicate across passes

        for i in range(passes):
            print("Scan pass {}/{}...".format(i + 1, passes))
            results = self.wlan.scan()
            for net in results:
                bssid = net[1]
                # Keep the entry with the strongest RSSI if seen before
                if bssid not in seen or net[3] > seen[bssid][3]:
                    seen[bssid] = net
            if i < passes - 1:
                time.sleep_ms(delay_ms)  # brief pause between passes

        networks = list(seen.values())
        networks.sort(key=lambda x: x[3], reverse=True)
        print("Total unique networks found: {}".format(len(networks)))
        return networks
