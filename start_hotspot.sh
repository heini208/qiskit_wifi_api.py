#!/bin/bash
set -euo pipefail

# Configuration
HOTSPOT_SSID="Roberta_Lab_Pi"
HOTSPOT_PASSWORD="robertapi"
GATEWAY_IP="192.168.4.1"
DHCP_RANGE_START="192.168.4.2"
DHCP_RANGE_END="192.168.4.20"

echo "Checking for NetworkManager..."
if ! command -v nmcli >/dev/null 2>&1; then
    echo "Error: NetworkManager (nmcli) is not installed. Are you on Raspberry Pi OS Lite or an older version?"
    exit 1
fi

# Delete existing connection if it exists to avoid duplicates
if nmcli connection show "$HOTSPOT_SSID" >/dev/null 2>&1; then
    echo "Removing existing hotspot connection '$HOTSPOT_SSID'..."
    sudo nmcli connection delete "$HOTSPOT_SSID"
fi

echo "Creating new Hotspot connection..."

# 1. Create the connection
sudo nmcli con add type wifi ifname wlan0 con-name "$HOTSPOT_SSID" autoconnect yes ssid "$HOTSPOT_SSID"

# 2. Set mode to Access Point
sudo nmcli con modify "$HOTSPOT_SSID" 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared

# 3. Set Security (WPA2)
sudo nmcli con modify "$HOTSPOT_SSID" wifi-sec.key-mgmt wpa-psk
sudo nmcli con modify "$HOTSPOT_SSID" wifi-sec.psk "$HOTSPOT_PASSWORD"

# 4. Set Static IP for the Pi (Gateway)
# "ipv4.addresses" sets the Pi's IP. "ipv4.gateway" is usually left empty for isolated networks,
# or set to the same IP, but NetworkManager "shared" method handles DHCP automatically.
sudo nmcli con modify "$HOTSPOT_SSID" ipv4.addresses "$GATEWAY_IP/24"

# 5. Bring the connection up
echo "Activating hotspot..."
sudo nmcli con up "$HOTSPOT_SSID"

echo "------------------------------------------------"
echo "Hotspot Created Successfully!"
echo "SSID:      $HOTSPOT_SSID"
echo "Password:  $HOTSPOT_PASSWORD"
echo "Pi IP:     $GATEWAY_IP"
echo "------------------------------------------------"
echo "Your microcontroller should connect to this SSID."
echo "Send data to: $GATEWAY_IP"