"""
WLED Scanner - Discover WLED Controllers on Network
Uses system commands and HTTP probing (no GPL libraries)
"""

import subprocess
import re
import requests
import logging
from typing import List, Dict, Optional
import socket

logger = logging.getLogger(__name__)


class WLEDScanner:
    """Scans network for WLED controllers"""
    
    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.wled_port = 80
    
    def _run_command(self, cmd: List[str]) -> str:
        """Execute system command and return output"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}: {e.stderr}")
            return ""
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            return ""
    
    def _get_network_from_interface(self, interface: str) -> Optional[str]:
        """Get network address from interface (e.g., '10.0.0.0/24')"""
        try:
            output = self._run_command(['/usr/sbin/ip', 'addr', 'show', interface])
            match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', output)
            if match:
                ip = match.group(1)
                cidr = match.group(2)
                # Convert to network address
                # For simplicity, assume /24 network
                network_prefix = '.'.join(ip.split('.')[0:3])
                return f"{network_prefix}.0/24"
        except Exception as e:
            logger.error(f"Failed to get network from {interface}: {e}")
        return None
    
    def _arp_scan(self, interface: str) -> List[Dict]:
        """
        Scan network using arp-scan
        Returns list of devices with IP and MAC
        """
        devices = []
        
        try:
            # Run arp-scan
            output = self._run_command(['/usr/bin/sudo', '/usr/sbin/arp-scan', '--interface', interface, '--localnet'])
            
            # Parse output
            for line in output.split('\n'):
                # Look for lines with IP and MAC (e.g., "10.0.0.15	aa:bb:cc:dd:ee:ff	...")
                match = re.match(r'^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f:]+)', line, re.IGNORECASE)
                if match:
                    devices.append({
                        'ip': match.group(1),
                        'mac': match.group(2).lower()
                    })
        
        except Exception as e:
            logger.warning(f"arp-scan failed, trying alternative method: {e}")
            # Fallback to nmap if arp-scan fails
            devices = self._nmap_scan(interface)
        
        return devices
    
    def _nmap_scan(self, interface: str) -> List[Dict]:
        """
        Fallback scan using nmap
        Returns list of devices with IP
        """
        devices = []
        network = self._get_network_from_interface(interface)
        
        if not network:
            return devices
        
        try:
            # Run nmap host discovery
            output = self._run_command(['/usr/bin/nmap', '-sn', network])
            
            # Parse output for IP addresses
            for line in output.split('\n'):
                match = re.search(r'Nmap scan report for (\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    ip = match.group(1)
                    # Try to get MAC from arp table
                    mac = self._get_mac_from_arp(ip)
                    devices.append({
                        'ip': ip,
                        'mac': mac if mac else 'unknown'
                    })
        
        except Exception as e:
            logger.error(f"nmap scan failed: {e}")
        
        return devices
    
    def _get_mac_from_arp(self, ip: str) -> Optional[str]:
        """Get MAC address from system ARP table"""
        try:
            output = self._run_command(['/usr/sbin/arp', '-n', ip])
            match = re.search(r'([0-9a-f:]{17})', output, re.IGNORECASE)
            if match:
                return match.group(1).lower()
        except:
            pass
        return None
    
    def _probe_wled(self, ip: str) -> Optional[Dict]:
        """
        Check if device is a WLED controller
        Returns WLED info if found, None otherwise
        """
        try:
            # Try to get WLED JSON API
            url = f"http://{ip}/json/info"
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify it's actually WLED
                if 'ver' in data or 'name' in data:
                    return {
                        'name': data.get('name', 'Unknown'),
                        'version': data.get('ver', 'Unknown'),
                        'brand': data.get('brand', 'WLED'),
                        'product': data.get('product', 'Unknown'),
                        'mac': data.get('mac', 'Unknown'),
                        'arch': data.get('arch', 'Unknown')
                    }
        
        except requests.exceptions.RequestException:
            # Not a WLED device or not responding
            pass
        except Exception as e:
            logger.debug(f"Error probing {ip}: {e}")
        
        return None
    
    def scan_network(self, interface: str) -> List[Dict]:
        """
        Scan network for WLED controllers
        
        Args:
            interface: Network interface to scan (e.g., 'eth1')
        
        Returns:
            List of WLED devices with details
        """
        logger.info(f"Scanning for WLED devices on {interface}")
        wled_devices = []
        
        # First, discover all devices on network
        devices = self._arp_scan(interface)
        
        logger.info(f"Found {len(devices)} devices, probing for WLED...")
        
        # Probe each device to see if it's WLED
        for device in devices:
            ip = device['ip']
            mac = device['mac']
            
            wled_info = self._probe_wled(ip)
            
            if wled_info:
                logger.info(f"Found WLED device at {ip}: {wled_info['name']}")
                wled_devices.append({
                    'ip': ip,
                    'mac': mac,
                    'name': wled_info['name'],
                    'version': wled_info['version'],
                    'brand': wled_info['brand'],
                    'product': wled_info.get('product', 'Unknown'),
                    'arch': wled_info.get('arch', 'Unknown')
                })
        
        logger.info(f"Scan complete: found {len(wled_devices)} WLED devices")
        return wled_devices
    
    def test_wled_connection(self, ip: str) -> bool:
        """Test if WLED controller is reachable"""
        wled_info = self._probe_wled(ip)
        return wled_info is not None
    
    def get_wled_info(self, ip: str) -> Optional[Dict]:
        """Get detailed information about a WLED controller"""
        return self._probe_wled(ip)
