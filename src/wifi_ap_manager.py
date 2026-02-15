"""
WiFi AP Manager - WiFi Access Point Management
Manages hostapd configuration for creating a WiFi hotspot
"""

import subprocess
import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class WiFiAPManager:
    """Manages WiFi Access Point configuration and status"""
    
    def __init__(self):
        self.hostapd_conf = '/etc/hostapd/hostapd.conf'
        self.hostapd_default = '/etc/default/hostapd'
        self.interface = 'wlan0'
        self.default_ssid = 'WLED-Manager-AP'
        self.default_channel = 6
        self.default_ip = '10.0.2.1'
    
    def _run_command(self, cmd: List[str]) -> tuple:
        """Execute system command and return (success, output, error)"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return (True, result.stdout, "")
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}: {e.stderr}")
            return (False, "", e.stderr)
    
    def is_installed(self) -> bool:
        """Check if WiFi AP is installed"""
        return os.path.exists('/usr/sbin/hostapd')
    
    def is_enabled(self) -> bool:
        """Check if WiFi AP is enabled"""
        if not self.is_installed():
            return False
        
        try:
            result = subprocess.run(
                ['/usr/bin/systemctl', 'is-enabled', 'hostapd'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def is_active(self) -> bool:
        """Check if WiFi AP is currently running"""
        if not self.is_installed():
            return False
        
        try:
            result = subprocess.run(
                ['/usr/bin/systemctl', 'is-active', 'hostapd'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def get_config(self) -> Optional[Dict]:
        """Get current WiFi AP configuration"""
        if not os.path.exists(self.hostapd_conf):
            return None
        
        config = {
            'ssid': self.default_ssid,
            'channel': self.default_channel,
            'interface': self.interface,
            'ip_address': self.default_ip
        }
        
        try:
            with open(self.hostapd_conf, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('ssid='):
                        config['ssid'] = line.split('=', 1)[1]
                    elif line.startswith('channel='):
                        config['channel'] = int(line.split('=', 1)[1])
                    elif line.startswith('interface='):
                        config['interface'] = line.split('=', 1)[1]
        except Exception as e:
            logger.error(f"Error reading hostapd config: {e}")
        
        # Get IP from NetworkManager
        try:
            output = subprocess.run(
                ['/usr/sbin/ip', 'addr', 'show', self.interface],
                capture_output=True,
                text=True
            ).stdout
            
            import re
            match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', output)
            if match:
                config['ip_address'] = match.group(1)
        except:
            pass
        
        return config
    
    def get_connected_clients(self) -> List[Dict]:
        """Get list of connected WiFi clients"""
        clients = []
        
        if not self.is_active():
            return clients
        
        try:
            # Get clients from ARP table on wlan0
            output = subprocess.run(
                ['/usr/sbin/ip', 'neigh', 'show', 'dev', self.interface],
                capture_output=True,
                text=True
            ).stdout
            
            for line in output.split('\n'):
                if 'REACHABLE' in line or 'STALE' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        clients.append({
                            'ip': parts[0],
                            'mac': parts[4],
                            'state': 'REACHABLE' if 'REACHABLE' in line else 'STALE'
                        })
        except Exception as e:
            logger.error(f"Error getting connected clients: {e}")
        
        return clients
    
    def configure(self, ssid: str, password: str, channel: int = 6, 
                 ip_address: str = '10.0.2.1') -> bool:
        """
        Configure WiFi AP
        
        Args:
            ssid: Network name
            password: WPA2 password (min 8 characters)
            channel: WiFi channel (1-11)
            ip_address: IP address for the AP
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate inputs
            if len(password) < 8:
                logger.error("Password must be at least 8 characters")
                return False
            
            if not 1 <= channel <= 11:
                logger.error("Channel must be between 1 and 11")
                return False
            
            # Create hostapd configuration
            hostapd_config = f"""interface={self.interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=GB
"""
            
            # Write hostapd configuration
            with open(self.hostapd_conf, 'w') as f:
                f.write(hostapd_config)
            
            logger.info(f"Created hostapd configuration for SSID: {ssid}")
            
            # Configure default hostapd file
            with open(self.hostapd_default, 'w') as f:
                f.write(f'DAEMON_CONF="{self.hostapd_conf}"\n')
            
            # Assign static IP to wlan0 directly (hostapd makes it unmanaged by NetworkManager)
            # Remove any existing IP first
            subprocess.run(
                ['/usr/sbin/ip', 'addr', 'flush', 'dev', self.interface],
                capture_output=True
            )
            
            # Assign new IP
            success, _, error = self._run_command([
                '/usr/sbin/ip', 'addr', 'add', f'{ip_address}/24', 'dev', self.interface
            ])
            
            if not success:
                logger.error(f"Failed to assign IP to {self.interface}: {error}")
                return False
            
            # Bring interface up
            subprocess.run(
                ['/usr/sbin/ip', 'link', 'set', self.interface, 'up'],
                capture_output=True
            )
            
            logger.info(f"Assigned IP {ip_address} to {self.interface}")
            
            # Save IP address for boot service
            with open('/etc/hostapd/wlan0-ip.conf', 'w') as f:
                f.write(f'{ip_address}\n')
            
            # Configure dnsmasq for WiFi AP
            self._configure_dnsmasq(ip_address)
            
            logger.info("WiFi AP configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring WiFi AP: {e}")
            return False
    
    def _configure_dnsmasq(self, ip_address: str) -> bool:
        """Configure dnsmasq for WiFi AP interface"""
        try:
            dnsmasq_conf = '/etc/dnsmasq.conf'
            
            # Read current config if file exists, otherwise start with empty config
            config = ""
            if os.path.exists(dnsmasq_conf):
                with open(dnsmasq_conf, 'r') as f:
                    config = f.read()
            
            # Check if wlan0 already configured
            if f'interface={self.interface}' in config:
                logger.info("dnsmasq already configured for wlan0")
                return True
            
            # Calculate DHCP range
            ip_parts = ip_address.split('.')
            network_prefix = '.'.join(ip_parts[:3])
            dhcp_start = f"{network_prefix}.10"
            dhcp_end = f"{network_prefix}.50"
            
            # Add WiFi AP configuration
            wifi_config = f"\n# {self.interface} - WiFi Access Point\n"
            wifi_config += f"interface={self.interface}\n"
            wifi_config += f"dhcp-range={self.interface},{dhcp_start},{dhcp_end},24h\n"
            wifi_config += f"dhcp-option={self.interface},3,{ip_address}\n"
            wifi_config += f"dhcp-option={self.interface},6,8.8.8.8,8.8.4.4\n"
            wifi_config += "bind-interfaces\n"
            
            # Write config (create or append)
            with open(dnsmasq_conf, 'a') as f:
                f.write(wifi_config)
            
            logger.info(f"Added dnsmasq configuration for {self.interface}")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring dnsmasq: {e}")
            return False
    
    def enable(self) -> bool:
        """Enable WiFi AP (start on boot)"""
        try:
            # Stop NetworkManager from managing wlan0
            subprocess.run(
                ['/usr/bin/nmcli', 'device', 'set', self.interface, 'managed', 'no'],
                capture_output=True
            )
            
            # Enable and start wlan0-ip service (assigns IP on boot)
            subprocess.run(
                ['/usr/bin/systemctl', 'enable', 'wlan0-ip'],
                capture_output=True
            )
            subprocess.run(
                ['/usr/bin/systemctl', 'start', 'wlan0-ip'],
                capture_output=True
            )
            
            # Enable and start hostapd
            subprocess.run(
                ['/usr/bin/systemctl', 'unmask', 'hostapd'],
                capture_output=True
            )
            
            success1, _, _ = self._run_command(['/usr/bin/systemctl', 'enable', 'hostapd'])
            success2, _, _ = self._run_command(['/usr/bin/systemctl', 'start', 'hostapd'])
            
            # Enable and restart dnsmasq (persistent)
            subprocess.run(
                ['/usr/bin/systemctl', 'enable', 'dnsmasq'],
                capture_output=True
            )
            subprocess.run(
                ['/usr/bin/systemctl', 'restart', 'dnsmasq'],
                capture_output=True
            )
            
            if success1 and success2:
                logger.info("WiFi AP enabled and started (persistent across reboots)")
                return True
            else:
                logger.error("Failed to enable WiFi AP")
                return False
                
        except Exception as e:
            logger.error(f"Error enabling WiFi AP: {e}")
            return False
    
    def disable(self) -> bool:
        """Disable WiFi AP"""
        try:
            success1, _, _ = self._run_command(['/usr/bin/systemctl', 'stop', 'hostapd'])
            success2, _, _ = self._run_command(['/usr/bin/systemctl', 'disable', 'hostapd'])
            
            # Disable wlan0-ip service
            subprocess.run(
                ['/usr/bin/systemctl', 'stop', 'wlan0-ip'],
                capture_output=True
            )
            subprocess.run(
                ['/usr/bin/systemctl', 'disable', 'wlan0-ip'],
                capture_output=True
            )
            
            # Allow NetworkManager to manage wlan0 again
            subprocess.run(
                ['/usr/bin/nmcli', 'device', 'set', self.interface, 'managed', 'yes'],
                capture_output=True
            )
            
            if success1 and success2:
                logger.info("WiFi AP disabled")
                return True
            else:
                logger.error("Failed to disable WiFi AP")
                return False
                
        except Exception as e:
            logger.error(f"Error disabling WiFi AP: {e}")
            return False
    
    def restart(self) -> bool:
        """Restart WiFi AP service"""
        try:
            success, _, _ = self._run_command(['/usr/bin/systemctl', 'restart', 'hostapd'])
            
            # Also restart dnsmasq
            subprocess.run(
                ['/usr/bin/systemctl', 'restart', 'dnsmasq'],
                capture_output=True
            )
            
            if success:
                logger.info("WiFi AP restarted")
                return True
            else:
                logger.error("Failed to restart WiFi AP")
                return False
                
        except Exception as e:
            logger.error(f"Error restarting WiFi AP: {e}")
            return False
