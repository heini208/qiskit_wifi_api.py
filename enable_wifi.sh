#!/bin/bash
set -e

HOTSPOT_SSID="Roberta_Lab_Pi"

echo "Restoring normal Wi-Fi configuration..."

# 1. Stop the hotspot if it's active
if nmcli connection show --active | grep -q "$HOTSPOT_SSID"; then
    echo "Stopping active hotspot..."
    sudo nmcli connection down "$HOTSPOT_SSID"
fi

# 2. Delete the hotspot connection profile
if nmcli connection show "$HOTSPOT_SSID" >/dev/null 2>&1; then
    echo "Deleting hotspot profile '$HOTSPOT_SSID'..."
    sudo nmcli connection delete "$HOTSPOT_SSID"
else
    echo "Hotspot profile not found (already deleted?)."
fi

# 3. Ensure Wi-Fi radio is on
echo "Ensuring Wi-Fi radio is ON..."
sudo nmcli radio wifi on

echo "------------------------------------------------"
echo "Hotspot removed."
echo "The Pi will now attempt to auto-connect to previously known networks."
echo "------------------------------------------------"
echo "If it does not connect automatically, run:"
echo "sudo nmcli device wifi connect 'YOUR_WIFI_NAME' password 'YOUR_PASSWORD'"