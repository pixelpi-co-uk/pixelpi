#!/usr/bin/env python3
"""
PixelPi - Main Application
Web-based network management for USB Ethernet adapters and WLED controllers
"""

import os
import sys
import yaml
import logging
from flask import Flask, render_template, jsonify, request
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapter_manager import AdapterManager
from wled_scanner import WLEDScanner
from dnsmasq_config import DnsmasqConfig
from wifi_ap_manager import WiFiAPManager

# Configuration
CONFIG_FILE = os.environ.get('PIXELPI_CONFIG', '/etc/pixelpi/config.yaml')

# Initialize Flask app
app = Flask(__name__, 
            template_folder='../web/templates',
            static_folder='../web/static')

# Load configuration
def load_config():
    """Load configuration from YAML file"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return yaml.safe_load(f)
    else:
        # Return default config
        return {
            'web': {'host': '0.0.0.0', 'port': 8080, 'debug': False},
            'network': {'default_subnet': '10.0.0.0/24'},
            'wled': {'default_port': 80, 'scan_timeout': 5},
            'logging': {'level': 'INFO'}
        }

config = load_config()

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.get('logging', {}).get('level', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize managers
adapter_manager = AdapterManager()
wled_scanner = WLEDScanner()
dnsmasq_config = DnsmasqConfig()
wifi_ap_manager = WiFiAPManager()

# Routes
@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')

@app.route('/adapters')
def adapters_page():
    """Adapters management page"""
    return render_template('adapters.html')

@app.route('/wled')
def wled_page():
    """WLED devices management page"""
    return render_template('wled.html')

@app.route('/wifi')
def wifi_page():
    """WiFi Access Point management page"""
    return render_template('wifi_ap.html')

@app.route('/api/adapters')
def get_adapters():
    """Get list of all network adapters"""
    try:
        adapters = adapter_manager.list_adapters()
        return jsonify({'success': True, 'adapters': adapters})
    except Exception as e:
        logger.error(f"Error listing adapters: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/adapters/usb')
def get_usb_adapters():
    """Get list of USB Ethernet adapters only"""
    try:
        adapters = adapter_manager.list_usb_adapters()
        return jsonify({'success': True, 'adapters': adapters})
    except Exception as e:
        logger.error(f"Error listing USB adapters: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/adapters/<interface>/configure', methods=['POST'])
def configure_adapter(interface):
    """Configure a network adapter"""
    try:
        data = request.json
        ip_address = data.get('ip_address')
        subnet_mask = data.get('subnet_mask', '24')
        
        result = adapter_manager.configure_adapter(interface, ip_address, subnet_mask)
        
        if result:
            return jsonify({'success': True, 'message': f'Adapter {interface} configured'})
        else:
            return jsonify({'success': False, 'error': 'Configuration failed'}), 500
            
    except Exception as e:
        logger.error(f"Error configuring adapter {interface}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wled/scan', methods=['POST'])
def scan_wled():
    """Scan for WLED controllers on specified interface"""
    try:
        data = request.json
        interface = data.get('interface')
        
        if not interface:
            return jsonify({'success': False, 'error': 'Interface not specified'}), 400
        
        devices = wled_scanner.scan_network(interface)
        return jsonify({'success': True, 'devices': devices})
        
    except Exception as e:
        logger.error(f"Error scanning for WLED devices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wled/reserve', methods=['POST'])
def reserve_wled_ip():
    """Reserve IP address for WLED controller by MAC"""
    try:
        data = request.json
        mac_address = data.get('mac_address')
        ip_address = data.get('ip_address')
        hostname = data.get('hostname', '')
        
        if not mac_address or not ip_address:
            return jsonify({'success': False, 'error': 'MAC and IP required'}), 400
        
        result = dnsmasq_config.add_reservation(mac_address, ip_address, hostname)
        
        if result:
            return jsonify({'success': True, 'message': 'IP reservation added'})
        else:
            return jsonify({'success': False, 'error': 'Failed to add reservation'}), 500
            
    except Exception as e:
        logger.error(f"Error adding IP reservation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wled/reservations')
def get_wled_reservations():
    """Get all WLED IP reservations"""
    try:
        reservations = dnsmasq_config.list_reservations()
        return jsonify({'success': True, 'reservations': reservations})
    except Exception as e:
        logger.error(f"Error listing reservations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/system/status')
def system_status():
    """Get overall system status"""
    try:
        status = {
            'dnsmasq': dnsmasq_config.check_service_status(),
            'networkmanager': adapter_manager.check_networkmanager_status(),
            'adapters_count': len(adapter_manager.list_usb_adapters()),
            'reservations_count': len(dnsmasq_config.list_reservations())
        }
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# WiFi AP Routes
@app.route('/api/wifi/status')
def wifi_status():
    """Get WiFi AP status"""
    try:
        status = {
            'installed': wifi_ap_manager.is_installed(),
            'enabled': wifi_ap_manager.is_enabled(),
            'active': wifi_ap_manager.is_active(),
            'config': wifi_ap_manager.get_config(),
            'clients': wifi_ap_manager.get_connected_clients()
        }
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        logger.error(f"Error getting WiFi AP status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wifi/configure', methods=['POST'])
def configure_wifi():
    """Configure WiFi AP"""
    try:
        data = request.json
        ssid = data.get('ssid')
        password = data.get('password')
        channel = data.get('channel', 6)
        ip_address = data.get('ip_address', '10.0.2.1')
        
        if not ssid or not password:
            return jsonify({'success': False, 'error': 'SSID and password required'}), 400
        
        result = wifi_ap_manager.configure(ssid, password, channel, ip_address)
        
        if result:
            return jsonify({'success': True, 'message': 'WiFi AP configured successfully'})
        else:
            return jsonify({'success': False, 'error': 'Configuration failed'}), 500
            
    except Exception as e:
        logger.error(f"Error configuring WiFi AP: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wifi/enable', methods=['POST'])
def enable_wifi():
    """Enable WiFi AP"""
    try:
        result = wifi_ap_manager.enable()
        
        if result:
            return jsonify({'success': True, 'message': 'WiFi AP enabled'})
        else:
            return jsonify({'success': False, 'error': 'Failed to enable WiFi AP'}), 500
            
    except Exception as e:
        logger.error(f"Error enabling WiFi AP: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wifi/disable', methods=['POST'])
def disable_wifi():
    """Disable WiFi AP"""
    try:
        result = wifi_ap_manager.disable()
        
        if result:
            return jsonify({'success': True, 'message': 'WiFi AP disabled'})
        else:
            return jsonify({'success': False, 'error': 'Failed to disable WiFi AP'}), 500
            
    except Exception as e:
        logger.error(f"Error disabling WiFi AP: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wifi/restart', methods=['POST'])
def restart_wifi():
    """Restart WiFi AP"""
    try:
        result = wifi_ap_manager.restart()
        
        if result:
            return jsonify({'success': True, 'message': 'WiFi AP restarted'})
        else:
            return jsonify({'success': False, 'error': 'Failed to restart WiFi AP'}), 500
            
    except Exception as e:
        logger.error(f"Error restarting WiFi AP: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting PixelPi")
    logger.info(f"Web interface: http://0.0.0.0:{config['web']['port']}")
    
    app.run(
        host=config['web']['host'],
        port=config['web']['port'],
        debug=config['web']['debug']
    )
