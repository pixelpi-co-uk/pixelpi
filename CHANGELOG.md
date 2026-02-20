# Changelog

All notable changes to PixelPi will be documented in this file.

## [1.0.0] - 2026-02-20

### Initial Release

**PixelPi - Open-source WLED management for Raspberry Pi**

### Features
- USB Ethernet adapter management with automatic configuration
- WiFi Access Point for wireless device connectivity
- WLED controller discovery and scanning
- MAC-based IP reservations
- Web interface on port 8080
- Offline Bootstrap support (works without internet)
- iOS/iPad compatibility
- Automatic DHCP configuration
- Network isolation between adapters

### Technical
- Python 3 + Flask backend
- Bootstrap 5 frontend (offline-capable)
- dnsmasq for DHCP
- hostapd for WiFi AP
- NetworkManager integration
- Systemd service management

### WiFi AP Implementation
- Systemd timer-based startup: WiFi AP starts 120 seconds AFTER boot completes
- Completely non-blocking: Timer runs asynchronously, cannot block boot
- Production stable on Raspberry Pi OS Full with desktop
- Safe reboot behavior verified through extensive testing
- Automatic rfkill unblock (handles soft-blocked WiFi on fresh installs)
- IP assignment script runs when timer triggers hostapd start

### Supported Hardware
- Raspberry Pi 5 (recommended) or Pi 4
- USB Ethernet adapters (RTL8153 chipset)
- Any WLED-compatible controller

### Services
- pixelpi.service - Main web application
- usb-adapter-init.service - Boot-time adapter initialization  
- wifi-ap-startup.timer - WiFi AP startup timer (triggers 120s after boot)
- wifi-ap-startup.service - WiFi AP startup (triggered by timer)
- hostapd.service - WiFi Access Point (started by timer)
- dnsmasq.service - DHCP server

### Known Issues
- None - production ready
