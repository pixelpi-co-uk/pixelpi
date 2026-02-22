#!/bin/bash

# PixelPi Installation Script
# For Raspberry Pi 5 running Raspberry Pi OS

set -e  # Exit on any error

echo "========================================="
echo "PixelPi Installation"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run as root (use sudo)"
    exit 1
fi

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo "WARNING: This script is designed for Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Step 1: Updating system packages..."
# Use DEBIAN_FRONTEND=noninteractive to avoid prompts during piped installation
export DEBIAN_FRONTEND=noninteractive
apt update
# Only upgrade if not running in a pipe, otherwise skip to avoid prompts
if [ -t 0 ]; then
    apt upgrade -y
else
    echo "Skipping system upgrade in non-interactive mode (run 'sudo apt upgrade' manually later)"
fi

echo ""
echo "Step 2: Installing dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    dnsmasq \
    arp-scan \
    nmap \
    git \
    network-manager \
    usb-modeswitch \
    usb-modeswitch-data

echo ""
echo "Step 3: Configuring USB Ethernet adapter support..."
# Fix for Realtek adapters that appear as CD-ROM
echo 'ACTION=="add", SUBSYSTEMS=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="8151", RUN+="/bin/sh -c \"echo 0bda 8151 > /sys/bus/usb/drivers/r8152/new_id\""' > /etc/udev/rules.d/50-usb-realtek-net.rules
udevadm control --reload-rules
echo "USB adapter support configured"

# Fix dnsmasq timing issue - make it wait for NetworkManager
mkdir -p /etc/systemd/system/dnsmasq.service.d
cat > /etc/systemd/system/dnsmasq.service.d/wait-for-network.conf << 'EOF'
[Unit]
After=NetworkManager.service network-online.target
Wants=network-online.target
EOF
echo "dnsmasq timing fix applied"

# Ensure system dnsmasq doesn't bind to wlan0
# NetworkManager runs its own dnsmasq for WiFi AP shared mode,
# so the system dnsmasq must stay off wlan0 to avoid port conflicts
# Use sed to remove any existing line first (idempotent), then add it fresh
sed -i '/^except-interface=wlan0$/d' /etc/dnsmasq.conf
echo "except-interface=wlan0" >> /etc/dnsmasq.conf
systemctl restart dnsmasq 2>/dev/null || true
echo "dnsmasq: excluded wlan0 (reserved for WiFi AP)"

echo ""
echo "Step 4: Creating installation directory..."
INSTALL_DIR="/opt/pixelpi"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# If running from a git clone, copy files
if [ -f "$(dirname "$0")/src/app.py" ]; then
    echo "Copying files from current directory..."
    cp -r "$(dirname "$0")"/* "$INSTALL_DIR/"
else
    # Otherwise clone from GitHub
    echo "Cloning from GitHub..."
    git clone https://github.com/pixelpi-co-uk/pixelpi.git temp_clone
    cp -r temp_clone/* "$INSTALL_DIR/"
    rm -rf temp_clone
fi

echo ""
echo "Step 5: Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Step 5.5: Downloading Bootstrap for offline use..."
mkdir -p "$INSTALL_DIR/web/static/css"
mkdir -p "$INSTALL_DIR/web/static/js"
mkdir -p "$INSTALL_DIR/web/static/fonts"

# Download Bootstrap CSS and JS
curl -sL https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css -o "$INSTALL_DIR/web/static/css/bootstrap.min.css" 2>/dev/null || echo "  Warning: Could not download Bootstrap CSS (will fallback to CDN)"
curl -sL https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js -o "$INSTALL_DIR/web/static/js/bootstrap.bundle.min.js" 2>/dev/null || echo "  Warning: Could not download Bootstrap JS (will fallback to CDN)"

# Download Bootstrap Icons
curl -sL https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.min.css -o "$INSTALL_DIR/web/static/css/bootstrap-icons.min.css" 2>/dev/null || echo "  Warning: Could not download Bootstrap Icons CSS (will fallback to CDN)"
curl -sL https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/fonts/bootstrap-icons.woff2 -o "$INSTALL_DIR/web/static/fonts/bootstrap-icons.woff2" 2>/dev/null || true
curl -sL https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/fonts/bootstrap-icons.woff -o "$INSTALL_DIR/web/static/fonts/bootstrap-icons.woff" 2>/dev/null || true

if [ -f "$INSTALL_DIR/web/static/css/bootstrap.min.css" ]; then
    echo "  Bootstrap files downloaded successfully for offline use"
else
    echo "  Bootstrap download failed - will use CDN (requires internet on client devices)"
fi

echo ""
echo "Step 6: Creating configuration directory..."
mkdir -p /etc/pixelpi
if [ ! -f /etc/pixelpi/config.yaml ]; then
    cp config/config.yaml /etc/pixelpi/config.yaml
fi

echo ""
echo "Step 7: Installing systemd services..."
# Make scripts executable
chmod +x "$INSTALL_DIR/scripts/"*.sh 2>/dev/null || true
cp systemd/pixelpi.service /etc/systemd/system/
cp systemd/usb-adapter-init.service /etc/systemd/system/
cp systemd/pixelpi-wifi-ap.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable pixelpi
systemctl enable usb-adapter-init
# Enable NetworkManager-wait-online so network-online.target works
# (required for WiFi AP delayed-start service)
systemctl enable NetworkManager-wait-online.service
systemctl start pixelpi
echo "Boot-time USB adapter initialization enabled"
echo "WiFi AP uses NetworkManager (auto-starts when enabled via dashboard)"

echo ""
echo "Step 8: Configuring firewall (if active)..."
if systemctl is-active --quiet ufw; then
    ufw allow 8080/tcp
    echo "Firewall configured to allow port 8080"
fi

echo ""
echo "Step 9: WiFi Access Point (optional)..."
echo "Would you like to install WiFi Access Point support?"
echo "This allows iPads to connect wirelessly instead of via Ethernet."

# Check if running in a pipe (non-interactive)
if [ -t 0 ]; then
    read -p "Install WiFi AP? (y/n) " -n 1 -r
    echo
else
    echo "Non-interactive mode detected. Installing WiFi AP by default..."
    REPLY="y"
fi

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing WiFi AP support..."
    export DEBIAN_FRONTEND=noninteractive
    apt install -y hostapd
    
    # Unmask hostapd (NetworkManager uses it internally for AP mode)
    systemctl unmask hostapd
    
    # Clean up old delayed-start service from previous versions (safe to fail on fresh install)
    systemctl stop wifi-ap-delayed-start.service 2>/dev/null || true
    systemctl disable wifi-ap-delayed-start.service 2>/dev/null || true
    rm -f /etc/systemd/system/wifi-ap-delayed-start.service
    
    # Ensure NM autoconnect is off if connection already exists (safe to fail on fresh install)
    # (the pixelpi-wifi-ap.service handles boot activation safely)
    nmcli connection modify pixelpi-ap autoconnect no 2>/dev/null || true
    
    systemctl daemon-reload
    
    echo "WiFi AP support installed!"
    echo "Configure it via the web interface at: http://$(hostname -I | awk '{print $1}'):8080/wifi"
else
    echo "Skipping WiFi AP installation"
    echo "You can install it later by running:"
    echo "  sudo apt install -y hostapd"
fi

echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "Access PixelPi at:"
echo "  http://$(hostname).local:8080"
echo "  or"
echo "  http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "Service status:"
systemctl status pixelpi --no-pager -l
echo ""
echo "To view logs: sudo journalctl -u pixelpi -f"
echo "To restart: sudo systemctl restart pixelpi"
echo ""
