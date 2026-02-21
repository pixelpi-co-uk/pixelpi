# WiFi AP Boot Crash Fix

## What was wrong

The Pi was crashing/hanging on boot when the WiFi AP was set to auto-start. 
Four issues were identified and fixed:

### 1. Dual dnsmasq conflict (primary crash cause)
The old code used `ipv4.method=shared` in NetworkManager (which spawns its own 
dnsmasq for WiFi DHCP) AND separately configured the system dnsmasq to listen 
on wlan0. Both tried to bind port 67 on the same interface → crash.

**Fix:** Removed all wlan0 dnsmasq configuration. NM shared mode handles WiFi 
DHCP internally. System dnsmasq now only handles USB Ethernet DHCP reservations.

### 2. 300-second sleep in a oneshot service
`ExecStartPre=/bin/sleep 300` exceeds systemd's default timeout for oneshot 
services (~90s), causing systemd to kill the service and trigger cascading 
dependency failures.

**Fix:** Replaced with a smart startup script (`wifi-ap-start.sh`) that actively 
polls for wlan0 and NetworkManager readiness with retries, typically completing 
in 10-20 seconds instead of blindly waiting 5 minutes.

### 3. `autoconnect yes` race condition  
Setting `autoconnect yes` on the NM connection causes NetworkManager to try 
bringing up the AP before WiFi firmware is loaded on Pi 5.

**Fix:** `autoconnect` is always set to `no`. A dedicated systemd service 
(`pixelpi-wifi-ap.service`) handles boot activation after confirming hardware 
readiness.

### 4. Dead code and mixed approaches
The old `restart()` called `hostapd` but the AP uses NetworkManager. 
`configure()` had unreachable duplicate try/except blocks. `_assign_ip()` 
manually set IPs but NM shared mode already handles this.

**Fix:** All methods now consistently use NetworkManager. Dead code removed.

---

## Files changed/added

```
src/wifi_ap_manager.py          - Rewritten (replaces old version)
scripts/wifi-ap-start.sh        - NEW: Smart startup script with hardware checks
systemd/pixelpi-wifi-ap.service - NEW: Systemd service for boot activation
```

## Deployment to Pi

### Option A: Replace files manually
```bash
# SSH into your Pi
# Stop the service
sudo systemctl stop pixelpi

# Backup old file
sudo cp /opt/pixelpi/src/wifi_ap_manager.py /opt/pixelpi/src/wifi_ap_manager.py.backup

# Copy new files
sudo cp wifi_ap_manager.py /opt/pixelpi/src/
sudo cp wifi-ap-start.sh /opt/pixelpi/scripts/
sudo chmod +x /opt/pixelpi/scripts/wifi-ap-start.sh
sudo cp pixelpi-wifi-ap.service /etc/systemd/system/

# Clean up old service if it exists
sudo systemctl stop wifi-ap-delayed-start.service 2>/dev/null
sudo systemctl disable wifi-ap-delayed-start.service 2>/dev/null
sudo rm -f /etc/systemd/system/wifi-ap-delayed-start.service

# Ensure autoconnect is off on the NM connection
sudo nmcli connection modify pixelpi-ap autoconnect no 2>/dev/null

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl start pixelpi
```

### Option B: Re-enable WiFi AP from dashboard
After deploying the new `wifi_ap_manager.py`, simply:
1. Open PixelPi dashboard → WiFi AP page
2. Disable WiFi AP (cleans up old config)
3. Re-enable WiFi AP (installs new startup script + service)
4. Reboot to test

### Verify after reboot
```bash
# Check if the AP came up
sudo systemctl status pixelpi-wifi-ap.service

# Check AP logs
sudo journalctl -u pixelpi-wifi-ap.service

# Check if AP is active
nmcli connection show --active | grep pixelpi-ap
```
