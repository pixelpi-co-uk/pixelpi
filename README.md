# PixelPi

<p align="center">
  <img src="web/static/img/pixelpi-logo.png" alt="PixelPi Logo" height="100">
</p>

Open-source network management system for WLED controllers on Raspberry Pi
PixelPi simplifies the management of WLED LED controllers by providing an intuitive web interface for configuring USB Ethernet adapters, scanning for devices, and managing network settings. Perfect for lighting installations, pixel art displays, and home automation projects.
✨ Features

USB Ethernet Adapter Management - Automatic detection and configuration
WiFi Access Point - Wireless network for iPad/device connectivity
WLED Controller Discovery - Scan and discover controllers on your network
IP Reservation - MAC-based DHCP reservations
Web Interface - Easy browser-based configuration at port 8080
Offline Support - Works without internet on client devices
iOS Compatible - Full iPad support via WiFi or Ethernet

🚀 Quick Start
Pre-Install Requirements
Before running the installer, ensure the following:

USB Ethernet adapter must be plugged in — the installer pins interface names by MAC address during setup (Step 3.5). If the adapter is not connected at install time, this step will be skipped and interface names may swap unexpectedly after a reboot. You can run pin-interfaces.sh manually afterwards if needed.
The PixelPi network architecture uses a single USB Ethernet adapter connected to an unmanaged switch, with all WLED controllers hanging off that switch. Do not use multiple USB Ethernet adapters — add more WLED controllers via the switch instead.

One-Command Installation
curl -sSL https://raw.githubusercontent.com/pixelpi-co-uk/pixelpi/main/install.sh | sudo bash
Requirements

Raspberry Pi 5 (recommended) or Pi 4
Raspberry Pi OS (Full or Lite)
Internet connection for initial setup
USB Ethernet adapter with RTL8153 chipset (plugged in before install)

Access Dashboard
http://[your-pi-ip]:8080
📖 Basic Usage

Configure Adapters - Set up USB Ethernet with static IPs
Scan for WLED - Discover controllers on your network
Reserve IPs - Assign static IPs via MAC address
WiFi AP (Optional) - Enable wireless access

🛠 Technical Details

Backend: Python 3 + Flask
Frontend: Bootstrap 5 (offline-capable)
Services: dnsmasq, NetworkManager
Default Port: 8080

Network Architecture
PixelPi uses a fixed two-interface architecture:
InterfaceRoleeth0Onboard LAN — admin access, gets DHCP from your routereth1USB Ethernet adapter — point-to-point link to unmanaged switch for WLED controllerswlan0WiFi AP — wireless access for iPads and control devices
Interface names are pinned by MAC address during install using a udev rule, ensuring they remain stable across reboots regardless of boot enumeration order.
WiFi Access Point Architecture
The WiFi AP uses NetworkManager in shared mode, which handles DHCP for connected WiFi clients internally. This keeps the system dnsmasq dedicated to USB Ethernet adapter DHCP reservations, avoiding port conflicts.
On boot, a dedicated systemd service (pixelpi-wifi-ap.service) waits for the WiFi hardware and NetworkManager to be fully ready before activating the AP. This prevents race conditions that can cause crashes on Pi 5 where the WiFi firmware takes several seconds to initialise.
Key files:

src/wifi_ap_manager.py - WiFi AP configuration and control
scripts/wifi-ap-start.sh - Boot-time startup script with hardware readiness checks
systemd/pixelpi-wifi-ap.service - Systemd service for delayed AP activation

🔧 Upgrading
From v1.0.0 to v1.1.0 (WiFi AP Fix)
If you previously had WiFi AP auto-start issues (Pi crashing/hanging on reboot), update the following files and clean up the old service:
bash# Stop PixelPi
sudo systemctl stop pixelpi

# Backup and replace wifi_ap_manager.py
sudo cp /opt/pixelpi/src/wifi_ap_manager.py /opt/pixelpi/src/wifi_ap_manager.py.backup
sudo cp src/wifi_ap_manager.py /opt/pixelpi/src/

# Install new startup script and service
sudo cp scripts/wifi-ap-start.sh /opt/pixelpi/scripts/
sudo chmod +x /opt/pixelpi/scripts/wifi-ap-start.sh
sudo cp systemd/pixelpi-wifi-ap.service /etc/systemd/system/

# Clean up old delayed-start service
sudo systemctl stop wifi-ap-delayed-start.service 2>/dev/null
sudo systemctl disable wifi-ap-delayed-start.service 2>/dev/null
sudo rm -f /etc/systemd/system/wifi-ap-delayed-start.service

# Ensure NM autoconnect is off (the new service handles boot activation)
sudo nmcli connection modify pixelpi-ap autoconnect no 2>/dev/null

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl start pixelpi
Then re-enable the WiFi AP from the dashboard to install the new boot service, and reboot to verify.
🚑 Troubleshooting
eth0 not getting an IP address after reboot
This can happen if the interface names swapped during a reboot (e.g. after a case change or hardware swap) before the udev pin rule was in place. The symptom is eth0 showing as UP but with no IP address in ip addr show eth0.
First, run the interface pin script if you haven't already:
bashchmod +x pin-interfaces.sh
./pin-interfaces.sh
sudo reboot
If eth0 still doesn't get an IP after rebooting, the NetworkManager connection profile may be bound to the wrong interface. Fix it with:
bashsudo nmcli connection delete netplan-eth0
sudo nmcli connection add type ethernet ifname eth0 con-name lan autoconnect yes ipv4.method auto
sudo nmcli connection up lan
sudo reboot
After the reboot, confirm eth0 has an IP:
baship addr show eth0
USB Ethernet adapter not detected at install time
If Step 3.5 was skipped during install because the adapter wasn't connected, plug it in and run the pin script manually:
bashchmod +x pin-interfaces.sh
./pin-interfaces.sh
sudo reboot
📝 Documentation

CHANGELOG - Version history
OFFLINE SUPPORT - Offline configuration guide

🤝 Contributing
Contributions welcome! Submit a Pull Request on GitHub.
📄 License
MIT License - See LICENSE file.
Made by keep-on-walking
🔗 Links

GitHub: https://github.com/pixelpi-co-uk/pixelpi
Issues: https://github.com/pixelpi-co-uk/pixelpi/issues
WLED Project: https://kno.wled.ge/

Made with ❤️ for the WLED community
