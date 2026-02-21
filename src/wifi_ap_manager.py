"""
WiFi AP Manager - WiFi Access Point Management
Manages hostapd configuration for creating a WiFi hotspot
"""

import subprocess
import os
import logging
import time
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
        
        # Cache to reduce nmcli subprocess calls
        self._status_cache = {}
        self._cache_timeout = 5  # seconds
    
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
    
    def _get_cached(self, key: str, fetch_func):
        """Get cached value or fetch new one if expired"""
        now = time.time()
        if key in self._status_cache:
            cached_time, cached_value = self._status_cache[key]
            if now - cached_time < self._cache_timeout:
                return cached_value
        
        # Cache expired or doesn't exist - fetch new value
        value = fetch_func()
        self._status_cache[key] = (now, value)
        return value
    
    def _clear_cache(self):
        """Clear status cache after configuration changes"""
        self._status_cache = {}
    
    def is_installed(self) -> bool:
        """Check if WiFi AP connection exists"""
        def _check():
            try:
                result = subprocess.run(
                    ['/usr/bin/nmcli', 'connection', 'show', 'pixelpi-ap'],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            except:
                return False
        
        return self._get_cached('is_installed', _check)
    
    def is_enabled(self) -> bool:
        """Check if WiFi AP is enabled (will auto-start on boot)"""
        def _check():
            try:
                result = subprocess.run(
                    ['/usr/bin/nmcli', '-t', '-f', 'AUTOCONNECT', 'connection', 'show', 'pixelpi-ap'],
                    capture_output=True,
                    text=True
                )
                return 'yes' in result.stdout
            except:
                return False
        
        return self._get_cached('is_enabled', _check)
    
    def is_active(self) -> bool:
        """Check if WiFi AP is currently running"""
        def _check():
            try:
                result = subprocess.run(
                    ['/usr/bin/nmcli', 'connection', 'show', '--active'],
                    capture_output=True,
                    text=True
                )
                return 'pixelpi-ap' in result.stdout
            except:
                return False
        
        return self._get_cached('is_active', _check)
    
    def get_config(self) -> Optional[Dict]:
        """Get current WiFi AP configuration from NetworkManager"""
        if not self.is_installed():
            return None
        
        config = {
            'ssid': self.default_ssid,
            'channel': self.default_channel,
            'interface': self.interface,
            'ip_address': self.default_ip
        }
        
        try:
            # Get SSID
            result = subprocess.run(
                ['/usr/bin/nmcli', '-t', '-f', '802-11-wireless.ssid', 'connection', 'show', 'pixelpi-ap'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                ssid_line = result.stdout.strip()
                if ':' in ssid_line:
                    config['ssid'] = ssid_line.split(':', 1)[1]
            
            # Get channel
            result = subprocess.run(
                ['/usr/bin/nmcli', '-t', '-f', '802-11-wireless.channel', 'connection', 'show', 'pixelpi-ap'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                channel_line = result.stdout.strip()
                if ':' in channel_line:
                    try:
                        config['channel'] = int(channel_line.split(':', 1)[1])
                    except:
                        pass
            
            # Get IP
            result = subprocess.run(
                ['/usr/bin/nmcli', '-t', '-f', 'ipv4.addresses', 'connection', 'show', 'pixelpi-ap'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                ip_line = result.stdout.strip()
                if ':' in ip_line:
                    ip_with_mask = ip_line.split(':', 1)[1]
                    if '/' in ip_with_mask:
                        config['ip_address'] = ip_with_mask.split('/')[0]
                        
        except Exception as e:
            logger.error(f"Error reading NetworkManager config: {e}")
        
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
        Configure WiFi AP using NetworkManager
        
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
            
            # Calculate DHCP range for dnsmasq
            ip_parts = ip_address.split('.')
            network_prefix = '.'.join(ip_parts[:3])
            dhcp_start = f"{network_prefix}.10"
            dhcp_end = f"{network_prefix}.50"
            
            # Delete existing connection if it exists
            subprocess.run(
                ['/usr/bin/nmcli', 'connection', 'delete', 'pixelpi-ap'],
                capture_output=True
            )
            
            # Create NetworkManager AP connection
            # Note: autoconnect=no because delayed-start service handles activation
            cmd = [
                '/usr/bin/nmcli', 'connection', 'add',
                'type', 'wifi',
                'ifname', self.interface,
                'con-name', 'pixelpi-ap',
                'autoconnect', 'no',
                'ssid', ssid,
                '802-11-wireless.mode', 'ap',
                '802-11-wireless.band', 'bg',
                '802-11-wireless.channel', str(channel),
                'ipv4.method', 'shared',
                'ipv4.addresses', f'{ip_address}/24',
                'wifi-sec.key-mgmt', 'wpa-psk',
                'wifi-sec.psk', password
            ]
            
            success, output, error = self._run_command(cmd)
            
            if not success:
                logger.error(f"Failed to create NetworkManager AP connection: {error}")
                return False
            
            logger.info(f"Created NetworkManager AP connection for SSID: {ssid}")
            
            # Configure dnsmasq for WiFi AP DHCP
            self._configure_dnsmasq(ip_address)
            
            # Clear cache after configuration change
            self._clear_cache()
            
            logger.info("WiFi AP configured successfully using NetworkManager")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring WiFi AP: {e}")
            return False
            
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
            config_modified = False
            
            if os.path.exists(dnsmasq_conf):
                with open(dnsmasq_conf, 'r') as f:
                    config = f.read()
            
            # Ensure port=0 is set (prevents DNS port conflict with NetworkManager)
            if 'port=0' not in config:
                config = "# Don't listen on port 53 (DNS) - only provide DHCP\nport=0\n\n" + config
                config_modified = True
                logger.info("Added port=0 to dnsmasq config to prevent DNS conflicts")
            
            # Check if wlan0 already configured
            if f'interface={self.interface}' in config:
                # Write back config if we modified it
                if config_modified:
                    with open(dnsmasq_conf, 'w') as f:
                        f.write(config)
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
            
            # Write complete config
            with open(dnsmasq_conf, 'w') as f:
                f.write(config + wifi_config)
            
            logger.info(f"Added dnsmasq configuration for {self.interface}")
            
            # Restart dnsmasq to load new configuration
            subprocess.run(
                ['/usr/bin/systemctl', 'restart', 'dnsmasq'],
                capture_output=True
            )
            logger.info("Restarted dnsmasq to load WiFi AP DHCP configuration")
            
            return True
            
        except Exception as e:
            logger.error(f"Error configuring dnsmasq: {e}")
            return False
    
    def enable(self) -> bool:
        """Enable WiFi AP (activate NetworkManager connection)"""
        try:
            # Unblock WiFi (in case it's soft-blocked)
            subprocess.run(
                ['/usr/sbin/rfkill', 'unblock', 'wifi'],
                capture_output=True
            )
            
            # Create delayed-start systemd service for reliable boot
            service_content = """[Unit]
Description=Delayed WiFi AP Activation
After=graphical.target NetworkManager.target
Wants=graphical.target NetworkManager.target

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 300
ExecStart=/usr/bin/nmcli connection up pixelpi-ap
RemainAfterExit=yes

[Install]
WantedBy=graphical.target
"""
            with open('/etc/systemd/system/wifi-ap-delayed-start.service', 'w') as f:
                f.write(service_content)
            
            # Enable the delayed-start service
            subprocess.run(['/usr/bin/systemctl', 'daemon-reload'], capture_output=True)
            subprocess.run(['/usr/bin/systemctl', 'enable', 'wifi-ap-delayed-start.service'], capture_output=True)
            
            # Activate WiFi AP NOW for immediate use
            success, _, error = self._run_command([
                '/usr/bin/nmcli', 'connection', 'up', 'pixelpi-ap'
            ])
            
            if not success:
                logger.error(f"Failed to activate WiFi AP: {error}")
                return False
            
            # Ensure dnsmasq is running
            subprocess.run(
                ['/usr/bin/systemctl', 'enable', 'dnsmasq'],
                capture_output=True
            )
            subprocess.run(
                ['/usr/bin/systemctl', 'start', 'dnsmasq'],
                capture_output=True
            )
            
            # Clear cache after enabling
            self._clear_cache()
            
            logger.info("WiFi AP enabled - will auto-start 5 minutes after boot")
            return True
                
        except Exception as e:
            logger.error(f"Error enabling WiFi AP: {e}")
            return False
    
    def _assign_ip(self) -> bool:
        """Assign IP address to wlan0 interface"""
        try:
            # Read saved IP or use default
            ip_address = self.default_ip
            if os.path.exists('/etc/hostapd/wlan0-ip.conf'):
                with open('/etc/hostapd/wlan0-ip.conf', 'r') as f:
                    ip_address = f.read().strip()
            
            # Flush existing IP
            subprocess.run(
                ['/usr/sbin/ip', 'addr', 'flush', 'dev', self.interface],
                capture_output=True
            )
            
            # Assign new IP
            success, _, error = self._run_command([
                '/usr/sbin/ip', 'addr', 'add', f'{ip_address}/24', 'dev', self.interface
            ])
            
            if not success:
                logger.warning(f"Could not assign IP to {self.interface}: {error}")
                return False
            
            # Bring interface up
            subprocess.run(
                ['/usr/sbin/ip', 'link', 'set', self.interface, 'up'],
                capture_output=True
            )
            
            logger.info(f"Assigned IP {ip_address} to {self.interface}")
            return True
            
        except Exception as e:
            logger.error(f"Error assigning IP: {e}")
            return False
    
    def disable(self) -> bool:
        """Disable WiFi AP"""
        try:
            # Deactivate the NetworkManager AP connection
            success, _, error = self._run_command([
                '/usr/bin/nmcli', 'connection', 'down', 'pixelpi-ap'
            ])
            
            if not success:
                logger.warning(f"Could not deactivate WiFi AP (may not be active): {error}")
            
            # Disable autoconnect
            subprocess.run(
                ['/usr/bin/nmcli', 'connection', 'modify', 'pixelpi-ap', 'autoconnect', 'no'],
                capture_output=True
            )
            
            # Disable and remove delayed-start service
            subprocess.run(['/usr/bin/systemctl', 'stop', 'wifi-ap-delayed-start.service'], capture_output=True)
            subprocess.run(['/usr/bin/systemctl', 'disable', 'wifi-ap-delayed-start.service'], capture_output=True)
            
            # Remove service file
            try:
                os.remove('/etc/systemd/system/wifi-ap-delayed-start.service')
            except:
                pass
            
            subprocess.run(['/usr/bin/systemctl', 'daemon-reload'], capture_output=True)
            
            # Clear cache after disabling
            self._clear_cache()
            
            logger.info("WiFi AP disabled - will not auto-start on boot")
            return True
                
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
