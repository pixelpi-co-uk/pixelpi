"""
Dnsmasq Configuration Manager - Handle DHCP Reservations
Manages /etc/dnsmasq.conf for MAC-based IP reservations
"""

import subprocess
import re
import logging
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)


class DnsmasqConfig:
    """Manages dnsmasq configuration for DHCP reservations"""
    
    def __init__(self, config_file: str = '/etc/dnsmasq.conf'):
        self.config_file = config_file
        self.backup_file = f"{config_file}.backup"
    
    def _run_command(self, cmd: List[str]) -> bool:
        """Execute system command"""
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}: {e.stderr}")
            return False
    
    def _read_config(self) -> str:
        """Read dnsmasq configuration file"""
        try:
            with open(self.config_file, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Config file {self.config_file} not found")
            return ""
        except Exception as e:
            logger.error(f"Error reading config file: {e}")
            return ""
    
    def _write_config(self, content: str) -> bool:
        """Write dnsmasq configuration file"""
        try:
            # Backup existing config
            if os.path.exists(self.config_file):
                with open(self.backup_file, 'w') as f:
                    f.write(self._read_config())
            
            # Write new config
            with open(self.config_file, 'w') as f:
                f.write(content)
            
            return True
        except Exception as e:
            logger.error(f"Error writing config file: {e}")
            return False
    
    def add_reservation(self, mac_address: str, ip_address: str, hostname: str = "") -> bool:
        """
        Add DHCP reservation for a device
        
        Args:
            mac_address: MAC address (e.g., 'aa:bb:cc:dd:ee:ff')
            ip_address: IP address to reserve (e.g., '10.0.0.10')
            hostname: Optional hostname for the device
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Normalize MAC address
            mac_address = mac_address.lower()
            
            # Read current config
            config = self._read_config()
            
            # Check if reservation already exists for this MAC
            pattern = f"dhcp-host={mac_address}"
            if pattern in config.lower():
                # Remove old reservation
                config = self._remove_reservation_from_config(config, mac_address)
            
            # Create new reservation line
            if hostname:
                reservation = f"dhcp-host={mac_address},{hostname},{ip_address}"
            else:
                reservation = f"dhcp-host={mac_address},{ip_address}"
            
            # Add to config
            # Look for WLED reservations section, or create it
            if "# WLED Reservations" not in config:
                config += "\n# WLED Reservations\n"
            
            config += f"{reservation}\n"
            
            # Write config
            if self._write_config(config):
                # Restart dnsmasq to apply changes
                if self.restart_service():
                    logger.info(f"Added reservation: {mac_address} -> {ip_address}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error adding reservation: {e}")
            return False
    
    def _remove_reservation_from_config(self, config: str, mac_address: str) -> str:
        """Remove reservation line from config"""
        lines = config.split('\n')
        filtered_lines = [
            line for line in lines
            if not line.startswith(f"dhcp-host={mac_address}")
        ]
        return '\n'.join(filtered_lines)
    
    def remove_reservation(self, mac_address: str) -> bool:
        """Remove DHCP reservation for a device"""
        try:
            mac_address = mac_address.lower()
            config = self._read_config()
            new_config = self._remove_reservation_from_config(config, mac_address)
            
            if self._write_config(new_config):
                if self.restart_service():
                    logger.info(f"Removed reservation for {mac_address}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing reservation: {e}")
            return False
    
    def list_reservations(self) -> List[Dict]:
        """List all DHCP reservations"""
        reservations = []
        
        try:
            config = self._read_config()
            
            # Parse dhcp-host lines
            for line in config.split('\n'):
                line = line.strip()
                if line.startswith('dhcp-host='):
                    # Parse: dhcp-host=mac,hostname,ip or dhcp-host=mac,ip
                    parts = line.replace('dhcp-host=', '').split(',')
                    
                    if len(parts) >= 2:
                        reservation = {
                            'mac': parts[0].lower(),
                            'ip': parts[-1],  # IP is always last
                            'hostname': parts[1] if len(parts) == 3 else ''
                        }
                        reservations.append(reservation)
        
        except Exception as e:
            logger.error(f"Error listing reservations: {e}")
        
        return reservations
    
    def restart_service(self) -> bool:
        """Restart dnsmasq service"""
        logger.info("Restarting dnsmasq service...")
        return self._run_command(['/usr/bin/sudo', '/usr/bin/systemctl', 'restart', 'dnsmasq'])
    
    def check_service_status(self) -> bool:
        """Check if dnsmasq service is running"""
        try:
            result = subprocess.run(
                ['/usr/bin/systemctl', 'is-active', 'dnsmasq'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def validate_reservation(self, mac_address: str, ip_address: str) -> bool:
        """
        Validate that MAC and IP addresses are properly formatted
        
        Args:
            mac_address: MAC address to validate
            ip_address: IP address to validate
        
        Returns:
            True if valid, False otherwise
        """
        # Validate MAC address format
        mac_pattern = r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$'
        if not re.match(mac_pattern, mac_address.lower()):
            logger.error(f"Invalid MAC address format: {mac_address}")
            return False
        
        # Validate IP address format
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, ip_address):
            logger.error(f"Invalid IP address format: {ip_address}")
            return False
        
        # Check IP octets are in valid range
        octets = ip_address.split('.')
        for octet in octets:
            if int(octet) > 255:
                logger.error(f"Invalid IP address: {ip_address}")
                return False
        
        return True
