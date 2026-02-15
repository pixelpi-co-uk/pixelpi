# PixelPi

<p align="center">
  <img src="web/static/img/pixelpi-logo.png" alt="PixelPi Logo" height="100">
</p>

**Open-source network management system for WLED controllers on Raspberry Pi**

PixelPi simplifies the management of WLED LED controllers by providing an intuitive web interface for configuring USB Ethernet adapters, scanning for devices, and managing network settings. Perfect for lighting installations, pixel art displays, and home automation projects.

## ✨ Features

- **USB Ethernet Adapter Management** - Automatic detection and configuration
- **WiFi Access Point** - Wireless network for iPad/device connectivity
- **WLED Controller Discovery** - Scan and discover controllers on your network
- **IP Reservation** - MAC-based DHCP reservations
- **Web Interface** - Easy browser-based configuration at port 8080
- **Offline Support** - Works without internet on client devices
- **iOS Compatible** - Full iPad support via WiFi or Ethernet

## 🚀 Quick Start

### One-Command Installation

```bash
curl -sSL https://raw.githubusercontent.com/pixelpi-co-uk/pixelpi/main/install.sh | sudo bash
```

### Requirements

- Raspberry Pi 5 (recommended) or Pi 4
- Raspberry Pi OS (Full or Lite)  
- Internet connection for initial setup
- USB Ethernet adapters with RTL8153 chipset

### Access Dashboard

```
http://[your-pi-ip]:8080
```

## 📖 Basic Usage

1. **Configure Adapters** - Set up USB Ethernet with static IPs
2. **Scan for WLED** - Discover controllers on your network
3. **Reserve IPs** - Assign static IPs via MAC address
4. **WiFi AP (Optional)** - Enable wireless access

## 🛠 Technical Details

- **Backend:** Python 3 + Flask
- **Frontend:** Bootstrap 5 (offline-capable)
- **Services:** dnsmasq, hostapd, NetworkManager
- **Default Port:** 8080

## 📝 Documentation

- [CHANGELOG](CHANGELOG.md) - Version history
- [OFFLINE SUPPORT](OFFLINE-SUPPORT.md) - Offline configuration guide

## 🤝 Contributing

Contributions welcome! Submit a Pull Request on GitHub.

## 📄 License

MIT License - See [LICENSE](LICENSE) file.

**** by keep-on-walking

## 🔗 Links

- **GitHub:** https://github.com/pixelpi-co-uk/pixelpi
- **Issues:** https://github.com/pixelpi-co-uk/pixelpi/issues  
- **WLED Project:** https://kno.wled.ge/

---

Made with ❤️ for the WLED community
