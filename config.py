# config.py — Centralized Configuration for WiFi Radar
# Edit these values to customize your deployment.

# --- Access Point Settings ---
AP_SSID     = "WiFi_Radar"
AP_PASSWORD = "00000000"          # Set a password string to enable WPA2. Leave "" for open network.

# --- Server Settings ---
SERVER_PORT = 80
CHUNK_SIZE  = 512         # HTTP response chunk size in bytes

# --- Hardware Settings ---
LED_PIN     = 2           # GPIO pin for the onboard LED (GPIO 2 on most ESP32 DevKits)

# --- Behavior Settings ---
LED_TIMEOUT_MS         = 8000   # ms of inactivity before LED turns off
PROXIMITY_THRESHOLD_DBM = -45   # dBm — trigger proximity alert above this level
