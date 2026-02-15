#!/bin/bash
# Force Realtek USB Ethernet adapters to network mode on boot
# This handles adapters that are plugged in before boot

# Wait for USB subsystem to be ready
sleep 5

# Load the r8152 driver
modprobe r8152

# Force all Realtek RTL8151 devices to use r8152 driver
for device in /sys/bus/usb/devices/*; do
    if [ -f "$device/idVendor" ] && [ -f "$device/idProduct" ]; then
        vendor=$(cat "$device/idVendor")
        product=$(cat "$device/idProduct")
        
        # Check if it's a Realtek RTL8151
        if [ "$vendor" = "0bda" ] && [ "$product" = "8151" ]; then
            echo "Found Realtek RTL8151 at $device, forcing network mode..."
            echo "0bda 8151" > /sys/bus/usb/drivers/r8152/new_id 2>/dev/null || true
            break
        fi
    fi
done

# Wait a moment for interfaces to appear
sleep 3

# Bring up any configured NetworkManager connections
nmcli connection show | grep -E "eth[0-9]+-static" | awk '{print $1}' | while read conn; do
    echo "Activating connection: $conn"
    nmcli connection up "$conn" 2>/dev/null || true
done

echo "USB adapter initialization complete"
