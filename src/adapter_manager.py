"""
Adapter Manager - USB Ethernet Adapter Detection and Configuration
Uses system commands (no GPL libraries) for commercial compatibility
"""

import subprocess
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class AdapterManager:
    """Manages network adapter detection and configuration"""
    
    def __init__(self):
        self.builtin_interface = 'eth0'  # Raspberry Pi built-in Ethernet
    
    def _run_command(self, cmd: List[str]) -> str:
        """Execute system command and return output"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}: {e.stderr}")
            return ""
    
    def list_adapters(self) -> List[Dict]:
        """List all network adapters"""
        adapters = []
        
        # Get list of network interfaces
        output = self._run_command(['/usr/sbin/ip', 'link', 'show'])
        
        # Parse output
        for line in output.split('\n'):
            # Look for interface lines (e.g., "2: eth0: <BROADCAST...")
            match = re.match(r'^\d+:\s+(\w+):\s+<([^>]+)>', line)
            if match:
                interface = match.group(1)
                flags = match.group(2)
                
                # Skip loopback
                if interface == 'lo':
                    continue
                
                # Get additional info
                info = self._get_adapter_info(interface)
                info['interface'] = interface
                info['flags'] = flags
                info['up'] = 'UP' in flags
                info['connected'] = 'LOWER_UP' in flags
                
                adapters.append(info)
        
        return adapters
    
    def list_usb_adapters(self) -> List[Dict]:
        """List only USB Ethernet adapters (exclude built-in eth0)"""
        all_adapters = self.list_adapters()
        
        # Filter out built-in Ethernet and wireless
        usb_adapters = [
            adapter for adapter in all_adapters
            if adapter['interface'] not in [self.builtin_interface, 'wlan0']
            and adapter['interface'].startswith(('eth', 'usb'))
        ]
        
        return usb_adapters
    
    def _get_adapter_info(self, interface: str) -> Dict:
        """Get detailed information about an adapter"""
        info = {
            'mac_address': None,
            'ip_address': None,
            'subnet_mask': None,
            'driver': None,
            'speed': None
        }
        
        # Get MAC address
        output = self._run_command(['/usr/sbin/ip', 'link', 'show', interface])
        mac_match = re.search(r'link/ether\s+([0-9a-f:]+)', output)
        if mac_match:
            info['mac_address'] = mac_match.group(1)
        
        # Get IP address
        output = self._run_command(['/usr/sbin/ip', 'addr', 'show', interface])
        ip_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', output)
        if ip_match:
            info['ip_address'] = ip_match.group(1)
            info['subnet_mask'] = ip_match.group(2)
        
        # Try to get driver info (may not work on all systems)
        try:
            driver_path = f'/sys/class/net/{interface}/device/driver'
            result = subprocess.run(
                ['readlink', '-f', driver_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                info['driver'] = result.stdout.strip().split('/')[-1]
        except:
            pass
        
        return info
    
    def configure_adapter(self, interface: str, ip_address: str, subnet_mask: str = '24') -> bool:
        """
        Configure adapter with static IP using NetworkManager and set up DHCP
        
        Args:
            interface: Network interface name (e.g., 'eth1')
            ip_address: IP address (e.g., '10.0.0.1')
            subnet_mask: Subnet mask in CIDR notation (e.g., '24')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            connection_name = f"{interface}-static"
            
            # Check if connection already exists
            existing = self._run_command(['/usr/bin/nmcli', 'connection', 'show', connection_name])
            
            if existing:
                # Modify existing connection
                logger.info(f"Modifying existing connection: {connection_name}")
                cmd = [
                    '/usr/bin/nmcli', 'connection', 'modify', connection_name,
                    'ipv4.addresses', f'{ip_address}/{subnet_mask}',
                    'ipv4.method', 'manual'
                ]
            else:
                # Create new connection
                logger.info(f"Creating new connection: {connection_name}")
                cmd = [
                    '/usr/bin/nmcli', 'connection', 'add',
                    'type', 'ethernet',
                    'ifname', interface,
                    'con-name', connection_name,
                    'ipv4.addresses', f'{ip_address}/{subnet_mask}',
                    'ipv4.method', 'manual',
                    'connection.autoconnect', 'yes'
                ]
            
            self._run_command(cmd)
            
            # Activate connection
            self._run_command(['/usr/bin/nmcli', 'connection', 'up', connection_name])
            
            # Configure DHCP for this interface
            if not self._configure_dhcp(interface, ip_address, subnet_mask):
                logger.warning(f"Network configured but DHCP setup failed for {interface}")
            
            logger.info(f"Configured {interface} with IP {ip_address}/{subnet_mask}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure adapter {interface}: {e}")
            return False
    
    def _configure_dhcp(self, interface: str, ip_address: str, subnet_mask: str) -> bool:
        """
        Configure dnsmasq DHCP for the interface
        
        Args:
            interface: Network interface name
            ip_address: Gateway IP (e.g., '10.0.0.1')
            subnet_mask: Subnet mask in CIDR notation (e.g., '24')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            dnsmasq_conf = '/etc/dnsmasq.conf'
            
            # Read current config
            try:
                with open(dnsmasq_conf, 'r') as f:
                    config = f.read()
            except FileNotFoundError:
                config = ""
            
            # Check if this interface is already configured
            interface_marker = f"# {interface} - USB Ethernet Adapter"
            if interface_marker in config:
                logger.info(f"DHCP already configured for {interface}")
                return True
            
            # Calculate DHCP range based on IP
            # e.g., 10.0.0.1 -> range 10.0.0.10 to 10.0.0.50
            ip_parts = ip_address.split('.')
            network_prefix = '.'.join(ip_parts[:3])
            dhcp_start = f"{network_prefix}.10"
            dhcp_end = f"{network_prefix}.50"
            
            # Add DHCP configuration for this interface
            dhcp_config = f"\n{interface_marker}\n"
            dhcp_config += f"interface={interface}\n"
            dhcp_config += f"dhcp-range={interface},{dhcp_start},{dhcp_end},24h\n"
            # Add gateway and DNS options for iOS/iPad compatibility
            dhcp_config += f"dhcp-option={interface},3,{ip_address}\n"  # Gateway
            dhcp_config += f"dhcp-option={interface},6,8.8.8.8,8.8.4.4\n"  # DNS servers
            
            # If this is the first interface being configured, add bind-interfaces
            if 'bind-interfaces' not in config:
                dhcp_config += "bind-interfaces\n"
            
            # Append to config
            with open(dnsmasq_conf, 'a') as f:
                f.write(dhcp_config)
            
            logger.info(f"Added DHCP configuration for {interface}: {dhcp_start}-{dhcp_end}")
            
            # Restart dnsmasq to apply changes
            restart_result = subprocess.run(
                ['/usr/bin/sudo', '/usr/bin/systemctl', 'restart', 'dnsmasq'],
                capture_output=True,
                text=True
            )
            
            if restart_result.returncode == 0:
                logger.info("dnsmasq restarted successfully")
                return True
            else:
                logger.error(f"Failed to restart dnsmasq: {restart_result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error configuring DHCP for {interface}: {e}")
            return False
    
    def check_networkmanager_status(self) -> bool:
        """Check if NetworkManager is running"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'NetworkManager'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def get_adapter_status(self, interface: str) -> Optional[Dict]:
        """Get current status of specific adapter"""
        adapters = self.list_adapters()
        for adapter in adapters:
            if adapter['interface'] == interface:
                return adapter
        return None
