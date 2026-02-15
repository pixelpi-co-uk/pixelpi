#!/bin/bash
# WiFi AP IP Assignment - runs when hostapd starts
# This is called by hostapd.service ExecStartPre

WLAN0_IP=$(cat /etc/hostapd/wlan0-ip.conf 2>/dev/null || echo "10.0.2.1")

# Flush any existing IP
/usr/sbin/ip addr flush dev wlan0 2>/dev/null || true

# Assign IP
/usr/sbin/ip addr add ${WLAN0_IP}/24 dev wlan0 2>/dev/null || true

# Bring interface up
/usr/sbin/ip link set wlan0 up 2>/dev/null || true

exit 0
