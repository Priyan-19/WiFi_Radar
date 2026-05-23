import socket   # type: ignore  (MicroPython built-in)
import network  # type: ignore  (MicroPython built-in)
import gc
from wifi_scanner import WiFiScanner
import utils
import config
import logger
from machine import Pin  # type: ignore  (MicroPython built-in, not available in desktop Python)
import time

class WebServer:
    def __init__(self, port=80):
        self.port = port
        self.scanner = WiFiScanner()
        self.setup_ap()
        
    def setup_ap(self):
        """Start Access Point to serve the webpage so user can connect to ESP32."""
        self.ap = network.WLAN(network.AP_IF)
        self.ap.active(True)
        # Use WPA2 if a password is configured, otherwise open network
        if config.AP_PASSWORD:
            self.ap.config(essid=config.AP_SSID, password=config.AP_PASSWORD, authmode=3)
            print("Access Point started! (WPA2 Protected)")
        else:
            self.ap.config(essid=config.AP_SSID, authmode=0)
            print("Access Point started! (Open Network)")
        print("Connect to Wi-Fi network: '{}'".format(config.AP_SSID))
        print("Then open browser to http://{}".format(self.ap.ifconfig()[0]))

    def read_html_template(self):
        """Read the HTML file from the filesystem."""
        try:
            with open('index.html', 'r') as f:
                return f.read()
        except Exception as e:
            return "<html><body><h1>Error loading index.html</h1><p>{}</p></body></html>".format(e)

    def generate_table_rows(self, networks):
        """Generate HTML table rows dynamically for each network."""
        rows = ""
        for net in networks:
            # Handle potential hidden SSIDs which might be empty
            ssid = net[0].decode('utf-8', 'ignore') if net[0] else "<i>Hidden Network</i>"
            bssid = utils.format_bssid(net[1])
            channel = net[2]
            rssi = net[3]
            auth_mode = net[4]
            
            encryption = utils.get_encryption_name(auth_mode)
            dist = utils.calculate_distance(rssi)
            pct = utils.rssi_to_percent(rssi)
            color_class = utils.get_signal_color_class(rssi)
            
            # Highlight Open networks in cyan
            enc_class = "open" if auth_mode == 0 else ""
            
            row = (
                "<tr>"
                "<td>{ssid}</td>"
                "<td class='mac-addr'>{bssid}</td>"
                "<td>{ch}</td>"
                "<td>{rssi}</td>"
                "<td>~{dist}m</td>"
                "<td><div class='progress-bg'>"
                "<div class='progress-fill {cls}' style='width:{pct}%'></div>"
                "</div></td>"
                "<td class='{enc_cls}'>{enc}</td>"
                "</tr>"
            ).format(
                ssid=ssid, bssid=bssid, ch=channel, rssi=rssi,
                dist=dist, cls=color_class, pct=pct,
                enc_cls=enc_class, enc=encryption
            )
            rows += row
        return rows

    def generate_channel_heatmap(self, networks):
        """Generate a CSS channel congestion bar chart for 2.4GHz channels 1-13."""
        counts = {}
        for net in networks:
            ch = net[2]
            if 1 <= ch <= 13:
                counts[ch] = counts.get(ch, 0) + 1
        max_count = max(counts.values()) if counts else 1
        bars = ""
        for ch in range(1, 14):
            count = counts.get(ch, 0)
            pct = int((count / max_count) * 100) if max_count else 0
            busy_class = "heatmap-high" if count >= 3 else ("heatmap-mid" if count >= 1 else "heatmap-low")
            bars += """<div class="heatmap-col">
                <div class="heatmap-bar-wrap">
                    <div class="heatmap-bar {busy}" style="height:{pct}%"></div>
                </div>
                <div class="heatmap-label">CH{ch}</div>
                <div class="heatmap-count">{count}</div>
            </div>""".format(busy=busy_class, pct=pct, ch=ch, count=count)
        return bars

    def parse_user_agent(self, raw_request):
        """Extract and decode OS, device type and browser from the User-Agent header."""
        ua = ""
        for line in raw_request.split('\r\n'):
            if line.lower().startswith('user-agent:'):
                ua = line[11:].strip()
                break
        if not ua:
            return "Unknown Device", "Unknown Browser", ua

        # Detect OS / device
        ua_lower = ua.lower()
        if 'iphone' in ua_lower:
            device = "iPhone"
        elif 'ipad' in ua_lower:
            device = "iPad"
        elif 'android' in ua_lower:
            device = "Android Phone" if 'mobile' in ua_lower else "Android Tablet"
        elif 'windows' in ua_lower:
            device = "Windows PC"
        elif 'macintosh' in ua_lower or 'mac os' in ua_lower:
            device = "Mac"
        elif 'linux' in ua_lower:
            device = "Linux PC"
        else:
            device = "Unknown Device"

        # Detect browser
        if 'edg/' in ua_lower or 'edge/' in ua_lower:
            browser = "Edge"
        elif 'chrome/' in ua_lower and 'safari/' in ua_lower:
            browser = "Chrome"
        elif 'firefox/' in ua_lower:
            browser = "Firefox"
        elif 'safari/' in ua_lower:
            browser = "Safari"
        elif 'opera' in ua_lower or 'opr/' in ua_lower:
            browser = "Opera"
        else:
            browser = "Browser"

        return device, browser, ua

    def get_client_mac(self, client_ip):
        """Look up the client MAC address from the AP station list."""
        try:
            stations = self.ap.status('stations')  # [(mac_bytes, rssi), ...]
            if stations:
                # In AP mode all clients get 192.168.4.x; usually only 1 client at a time
                mac_bytes = stations[0][0]
                return ':'.join('{:02X}'.format(b) for b in mac_bytes)
        except Exception:
            pass
        return "--:--:--:--:--:--"

    def start(self):
        """Start the socket web server to listen for client connections."""
        addr = socket.getaddrinfo('0.0.0.0', self.port)[0][-1]
        s = socket.socket()
        
        # Prevent "Address already in use" errors during quick restarts
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(5)  # Queue up to 5 connections while busy
        s.settimeout(1.0) # 1-second timeout so it doesn't block forever
        print('Web server listening on', addr)
        
        # Initialize onboard LED pin from config
        led = Pin(config.LED_PIN, Pin.OUT)
        led.value(0) # Ensure it's off initially
        
        start_time = time.ticks_ms()

        # Pre-scan on boot so the first page load is instant
        print("Performing initial scan...")
        cached_networks = self.scanner.scan()
        last_scan_time = time.ticks_ms()
        SCAN_INTERVAL_MS = 15000  # Re-scan every 15s during idle
        print("Initial scan complete — {} networks found.".format(len(cached_networks)))

        while True:
            try:
                cl, client_addr = s.accept()

                # Parse the HTTP request path to avoid unnecessary scans
                # (browsers fetch /favicon.ico on every page load — skip it)
                raw_request = cl.recv(1024).decode('utf-8', 'ignore')
                if not raw_request:
                    cl.close()
                    continue

                request_line = raw_request.split('\r\n')[0]  # e.g. "GET / HTTP/1.1"
                parts = request_line.split(' ')
                path = parts[1] if len(parts) > 1 else '/'
                
                print("[HTTP] Requested path:", path)

                if path.startswith('/log'):
                    print("[HTTP] Serving log file...")
                    cl.sendall(b'HTTP/1.1 200 OK\r\n')
                    cl.sendall(b'Content-Type: text/html; charset=utf-8\r\n')
                    cl.sendall(b'Connection: close\r\n\r\n')
                    
                    # Send a basic HTML header
                    cl.sendall(b'<html><head><meta name="viewport" content="width=device-width, initial-scale=1">')
                    cl.sendall(b'<style>body{background:#000;color:#0f0;font-family:monospace;padding:20px;}</style>')
                    cl.sendall(b'</head><body><h2>[ INTERCEPTED CLIENT LOG ]</h2><pre>')
                    
                    # Stream log directly from flash
                    try:
                        with open('/client_log.txt', 'r') as f:
                            has_logs = False
                            while True:
                                chunk = f.read(256)
                                if not chunk:
                                    break
                                has_logs = True
                                cl.sendall(chunk.encode('utf-8'))
                            if not has_logs:
                                cl.sendall(b"No connections recorded yet. Visit the main dashboard first!")
                    except OSError:
                        cl.sendall(b"No connections recorded yet. Visit the main dashboard first!")
                        
                    cl.sendall(b'</pre><br><a href="/" style="color:#0ff;">&lt; BACK TO RADAR</a></body></html>')
                    cl.close()
                    gc.collect()
                    continue

                if path != '/':
                    print("[HTTP] 404 Not Found:", path)
                    cl.send('HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n')
                    cl.close()
                    gc.collect()
                    continue

                # Identify who connected
                device, browser, ua_full = self.parse_user_agent(raw_request)
                client_mac = self.get_client_mac(client_addr[0])
                print("-" * 40)
                print("CLIENT IDENTIFIED")
                print("  IP      : {}".format(client_addr[0]))
                print("  MAC     : {}".format(client_mac))
                print("  Device  : {}".format(device))
                print("  Browser : {}".format(browser))
                print("  UA      : {}".format(ua_full[:80]))
                print("-" * 40)

                # Persist to flash so it's readable after powerbank sessions
                logger.log_client(client_addr[0], client_mac, device, browser)

                # Flush RAM before building response
                gc.collect()
                print("  RAM before HTML build: {} KB free".format(gc.mem_free() // 1024))

                networks = cached_networks

                # Build each injectable value and substitute one at a time,
                # deleting the intermediate string immediately to free RAM before next step
                html = self.read_html_template()
                gc.collect()

                table_rows = self.generate_table_rows(networks)
                html = html.replace('{{TABLE_ROWS}}', table_rows)
                del table_rows
                gc.collect()

                channel_heatmap = self.generate_channel_heatmap(networks)
                html = html.replace('{{CHANNEL_HEATMAP}}', channel_heatmap)
                del channel_heatmap
                gc.collect()

                strongest_signal = networks[0][3] if networks else "--"
                uptime_sec = time.ticks_diff(time.ticks_ms(), start_time) // 1000
                client_info_html = "{} via {} | MAC: {}".format(device, browser, client_mac)

                proximity_alert = ""
                if networks and networks[0][3] >= config.PROXIMITY_THRESHOLD_DBM:
                    proximity_alert = "<div class='alert-banner'>&#9888; PROXIMITY ALERT: TARGET EXTREMELY CLOSE &#9888;</div>"

                html = html.replace('{{TOTAL_NETWORKS}}', str(len(networks)))
                html = html.replace('{{STRONGEST_SIGNAL}}', str(strongest_signal))
                html = html.replace('{{UPTIME}}', "{:02d}m {:02d}s".format(uptime_sec // 60, uptime_sec % 60))
                html = html.replace('{{FREE_RAM}}', "{} KB".format(gc.mem_free() // 1024))
                html = html.replace('{{CLIENT_INFO}}', client_info_html)
                html = html.replace('{{PROXIMITY_ALERT}}', proximity_alert)
                gc.collect()

                print("  RAM after HTML build : {} KB free".format(gc.mem_free() // 1024))
                print("  HTML size            : {} bytes".format(len(html)))

                # Send HTTP response
                cl.send('HTTP/1.1 200 OK\r\n')
                cl.send('Content-Type: text/html\r\n')
                cl.send('Connection: close\r\n\r\n')

                for i in range(0, len(html), config.CHUNK_SIZE):
                    cl.send(html[i:i+config.CHUNK_SIZE])

                cl.close()
                del html


                # Update the cache AFTER the response is sent (non-blocking for client)
                cached_networks = self.scanner.scan()
                last_scan_time = time.ticks_ms()

                # Manually trigger garbage collection after each request to keep RAM free
                gc.collect() 
            except OSError:
                # s.accept() timed out — idle period, good time to refresh scan cache
                if time.ticks_diff(time.ticks_ms(), last_scan_time) >= SCAN_INTERVAL_MS:
                    cached_networks = self.scanner.scan()
                    last_scan_time = time.ticks_ms()
                    gc.collect()
            except Exception as e:
                print("Server error:", e)
                try:
                    cl.close()
                except:
                    pass

            # Update LED based on actual AP station association.
            # This is checked every ~1 second (socket timeout) and is
            # perfectly accurate: ON when any device is connected to the
            # hotspot, OFF the instant they disconnect.
            try:
                led.value(1 if self.ap.status('stations') else 0)
            except Exception:
                pass
