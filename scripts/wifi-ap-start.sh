#!/bin/bash
# PixelPi WiFi AP Startup Script
# Waits for WiFi hardware to be ready before activating the AP
# This avoids race conditions that cause crashes on Pi 5
#
# This script is installed to /opt/pixelpi/scripts/wifi-ap-start.sh
# and called by the pixelpi-wifi-ap.service systemd unit

CONNECTION="pixelpi-ap"
INTERFACE="wlan0"
MAX_WAIT=60
WAIT_INTERVAL=3

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [pixelpi-wifi-ap] $1"
}

# Ensure WiFi is unblocked
/usr/sbin/rfkill unblock wifi 2>/dev/null

# Wait for wlan0 to appear
log_msg "Waiting for $INTERFACE to be available..."
waited=0
while [ $waited -lt $MAX_WAIT ]; do
    if /usr/sbin/ip link show "$INTERFACE" >/dev/null 2>&1; then
        log_msg "$INTERFACE is available"
        break
    fi
    sleep $WAIT_INTERVAL
    waited=$((waited + WAIT_INTERVAL))
done

if [ $waited -ge $MAX_WAIT ]; then
    log_msg "ERROR: $INTERFACE did not appear after ${MAX_WAIT}s - aborting"
    exit 1
fi

# Wait for NetworkManager to be fully operational
log_msg "Waiting for NetworkManager..."
waited=0
while [ $waited -lt $MAX_WAIT ]; do
    if /usr/bin/nmcli general status >/dev/null 2>&1; then
        log_msg "NetworkManager is ready"
        break
    fi
    sleep $WAIT_INTERVAL
    waited=$((waited + WAIT_INTERVAL))
done

if [ $waited -ge $MAX_WAIT ]; then
    log_msg "ERROR: NetworkManager not ready after ${MAX_WAIT}s - aborting"
    exit 1
fi

# Check the connection exists
if ! /usr/bin/nmcli connection show "$CONNECTION" >/dev/null 2>&1; then
    log_msg "ERROR: Connection '$CONNECTION' does not exist"
    exit 1
fi

# Additional delay for Pi 5 WiFi firmware to fully initialise
sleep 5

# Activate the AP with retries
log_msg "Activating WiFi AP..."
for attempt in 1 2 3; do
    if /usr/bin/nmcli connection up "$CONNECTION" 2>&1; then
        log_msg "WiFi AP activated successfully on attempt $attempt"
        exit 0
    fi
    log_msg "Attempt $attempt failed, retrying in 5s..."
    sleep 5
done

log_msg "ERROR: Failed to activate WiFi AP after 3 attempts"
exit 1
