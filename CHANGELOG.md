# Changelog

All notable changes to PixelPi will be documented in this file.

## [1.0.0] - 2026-02-15

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
- IP assignment handled via hostapd ExecStartPre (not boot-time service)
- No boot-blocking services
- Safe reboot behavior
- IP configured when WiFi AP starts, not during system boot

### Supported Hardware
- Raspberry Pi 5 (recommended) or Pi 4
- USB Ethernet adapters (RTL8153 chipset)
- Any WLED-compatible controller

### Services
- pixelpi.service - Main web application
- usb-adapter-init.service - Boot-time adapter initialization
- hostapd.service - WiFi Access Point (with IP assignment override)
- dnsmasq.service - DHCP server

### Known Issues
- None - production ready
