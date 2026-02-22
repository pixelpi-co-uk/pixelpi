"""
WiFi AP Manager - WiFi Access Point Management
Manages NetworkManager-based WiFi hotspot on Raspberry Pi

Key design decisions:
  - Uses NetworkManager 'shared' mode which handles DHCP for WiFi
    clients internally (no separate dnsmasq config needed for wlan0)
  - autoconnect=no on the NM connection to prevent boot race conditions
  - A separate systemd service handles delayed activation after WiFi
    hardware is confirmed ready (replaces the old 300s sleep approach)
  - System dnsmasq remains untouched for wlan0 - it only handles
    USB Ethernet adapter DHCP reservations
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
        self.interface = 'wlan0'
        self.connection_name = 'pixelpi-ap'
        self.default_ssid = 'WLED-Manager-AP'
        self.default_channel = 6
        self.default_ip = '10.0.2.1'
        self.delayed_service = 'pixelpi-wifi-ap.service'
        self.startup_script = '/opt/pixelpi/scripts/wifi-ap-start.sh'
        
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
        
        value = fetch_func()
        self._status_cache[key] = (now, value)
        return value
    
    def _clear_cache(self):
        """Clear status cache after configuration changes"""
        self._status_cache = {}
    
    def is_installed(self) -> bool:
        """Check if WiFi AP connection exists in NetworkManager"""
        def _check():
            try:
                result = subprocess.run(
                    ['/usr/bin/nmcli', 'connection', 'show', self.connection_name],
                    capture_output=True, text=True
                )
                return result.returncode == 0
            except:
                return False
        
        return self._get_cached('is_installed', _check)
    
    def is_enabled(self) -> bool:
        """Check if WiFi AP delayed-start service is enabled (will start on boot)"""
        def _check():
            try:
                result = subprocess.run(
                    ['/usr/bin/systemctl', 'is-enabled', self.delayed_service],
                    capture_output=True, text=True
                )
                return result.stdout.strip() == 'enabled'
            except:
                return False
        
        return self._get_cached('is_enabled', _check)
    
    def is_active(self) -> bool:
        """Check if WiFi AP is currently running"""
        def _check():
            try:
                result = subprocess.run(
                    ['/usr/bin/nmcli', 'connection', 'show', '--active'],
                    capture_output=True, text=True
                )
                return self.connection_name in result.stdout
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
                ['/usr/bin/nmcli', '-t', '-f', '802-11-wireless.ssid',
                 'connection', 'show', self.connection_name],
                capture_output=True, text=True
            )
            if result.returncode == 0 and ':' in result.stdout.strip():
                config['ssid'] = result.stdout.strip().split(':', 1)[1]
            
            # Get channel
            result = subprocess.run(
                ['/usr/bin/nmcli', '-t', '-f', '802-11-wireless.channel',
                 'connection', 'show', self.connection_name],
                capture_output=True, text=True
            )
            if result.returncode == 0 and ':' in result.stdout.strip():
                try:
                    config['channel'] = int(result.stdout.strip().split(':', 1)[1])
                except ValueError:
                    pass
            
            # Get IP
            result = subprocess.run(
                ['/usr/bin/nmcli', '-t', '-f', 'ipv4.addresses',
                 'connection', 'show', self.connection_name],
                capture_output=True, text=True
            )
            if result.returncode == 0 and ':' in result.stdout.strip():
                ip_with_mask = result.stdout.strip().split(':', 1)[1]
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
            output = subprocess.run(
                ['/usr/sbin/ip', 'neigh', 'show', 'dev', self.interface],
                capture_output=True, text=True
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
        
        Uses ipv4.method=shared which makes NetworkManager handle DHCP
        for connected clients automatically - no separate dnsmasq config needed.
        
        autoconnect is set to 'no' to prevent boot race conditions.
        The delayed-start service handles activation after WiFi is ready.
        """
        try:
            # Validate inputs
            if len(password) < 8:
                logger.error("Password must be at least 8 characters")
                return False
            
            if not 1 <= channel <= 11:
                logger.error("Channel must be between 1 and 11")
                return False
            
            # Delete existing connection if it exists
            subprocess.run(
                ['/usr/bin/nmcli', 'connection', 'delete', self.connection_name],
                capture_output=True
            )
            
            # Create NetworkManager AP connection
            # autoconnect=no is critical - the systemd service handles boot activation
            cmd = [
                '/usr/bin/nmcli', 'connection', 'add',
                'type', 'wifi',
                'ifname', self.interface,
                'con-name', self.connection_name,
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
            
            # Clear cache after configuration change
            self._clear_cache()
            
            logger.info(f"WiFi AP configured: SSID={ssid}, Channel={channel}, IP={ip_address}")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring WiFi AP: {e}")
            return False
    
    def _install_startup_script(self) -> bool:
        """Create the WiFi AP startup script that waits for hardware readiness"""
        try:
            script_content = '''#!/bin/bash
# PixelPi WiFi AP Startup Script
# Waits for WiFi hardware to be ready before activating the AP
# This avoids race conditions that cause crashes on Pi 5

CONNECTION="pixelpi-ap"
INTERFACE="wlan0"
MAX_WAIT=60
WAIT_INTERVAL=3

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [pixelpi-wifi-ap] $1"
}

# Ensure WiFi is unblocked
/usr/sbin/rfkill unblock wifi 2>/dev/null

# Enable WiFi radio in NetworkManager (rfkill alone isn't always enough)
/usr/bin/nmcli radio wifi on 2>/dev/null

# Wait for wlan0 to appear
log_msg "Waiting for $INTERFACE to be available..."
waited=0
while [ $waited -lt $MAX_WAIT ]; do
    if /usr/sbin/ip link show "$INTERFACE" >/dev/null 2>&1; then
        log_msg "$INTERFACE is available"
        break
    fi
    sleep $WAIT_INTERVAL
    waited=$((waited + WAIT_INTERVAL))
done

if [ $waited -ge $MAX_WAIT ]; then
    log_msg "ERROR: $INTERFACE did not appear after ${MAX_WAIT}s - aborting"
    exit 1
fi

# Wait for NetworkManager to see wlan0 as ready (not "unavailable")
log_msg "Waiting for $INTERFACE to be ready in NetworkManager..."
waited=0
while [ $waited -lt $MAX_WAIT ]; do
    state=$(/usr/bin/nmcli -t -f DEVICE,STATE device 2>/dev/null | grep "^${INTERFACE}:" | cut -d: -f2)
    if [ "$state" = "disconnected" ] || [ "$state" = "connected" ]; then
        log_msg "$INTERFACE is ready (state: $state)"
        break
    fi
    sleep $WAIT_INTERVAL
    waited=$((waited + WAIT_INTERVAL))
done

# Wait for NetworkManager to be fully operational
log_msg "Waiting for NetworkManager..."
waited=0
while [ $waited -lt $MAX_WAIT ]; do
    if /usr/bin/nmcli general status >/dev/null 2>&1; then
        log_msg "NetworkManager is ready"
        break
    fi
    sleep $WAIT_INTERVAL
    waited=$((waited + WAIT_INTERVAL))
done

if [ $waited -ge $MAX_WAIT ]; then
    log_msg "ERROR: NetworkManager not ready after ${MAX_WAIT}s - aborting"
    exit 1
fi

# Check the connection exists
if ! /usr/bin/nmcli connection show "$CONNECTION" >/dev/null 2>&1; then
    log_msg "ERROR: Connection '$CONNECTION' does not exist"
    exit 1
fi

# Additional delay for Pi 5 WiFi firmware to fully initialise
sleep 5

# Activate the AP with retries
log_msg "Activating WiFi AP..."
for attempt in 1 2 3; do
    if /usr/bin/nmcli connection up "$CONNECTION" 2>&1; then
        log_msg "WiFi AP activated successfully on attempt $attempt"
        exit 0
    fi
    log_msg "Attempt $attempt failed, retrying in 5s..."
    sleep 5
done

log_msg "ERROR: Failed to activate WiFi AP after 3 attempts"
exit 1
'''
            os.makedirs(os.path.dirname(self.startup_script), exist_ok=True)
            with open(self.startup_script, 'w') as f:
                f.write(script_content)
            os.chmod(self.startup_script, 0o755)
            
            logger.info(f"Installed WiFi AP startup script: {self.startup_script}")
            return True
            
        except Exception as e:
            logger.error(f"Error installing startup script: {e}")
            return False
    
    def _install_delayed_service(self) -> bool:
        """Create systemd service for delayed WiFi AP activation"""
        try:
            service_content = f"""[Unit]
Description=PixelPi WiFi AP Activation
After=NetworkManager.service network-online.target
Wants=NetworkManager.service network-online.target

[Service]
Type=oneshot
ExecStart={self.startup_script}
RemainAfterExit=yes
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
"""
            service_path = f'/etc/systemd/system/{self.delayed_service}'
            with open(service_path, 'w') as f:
                f.write(service_content)
            
            subprocess.run(['/usr/bin/systemctl', 'daemon-reload'], capture_output=True)
            
            logger.info(f"Installed delayed-start service: {self.delayed_service}")
            return True
            
        except Exception as e:
            logger.error(f"Error installing delayed service: {e}")
            return False
    
    def _cleanup_old_service(self):
        """Remove old wifi-ap-delayed-start.service from previous versions"""
        old_service = 'wifi-ap-delayed-start.service'
        old_path = f'/etc/systemd/system/{old_service}'
        
        try:
            subprocess.run(
                ['/usr/bin/systemctl', 'stop', old_service],
                capture_output=True
            )
            subprocess.run(
                ['/usr/bin/systemctl', 'disable', old_service],
                capture_output=True
            )
            if os.path.exists(old_path):
                os.remove(old_path)
                logger.info(f"Cleaned up old service: {old_service}")
            
            subprocess.run(['/usr/bin/systemctl', 'daemon-reload'], capture_output=True)
        except:
            pass
    
    def _cleanup_wlan0_dnsmasq(self):
        """Ensure system dnsmasq doesn't conflict with WiFi AP.
        
        NetworkManager runs its own dnsmasq for WiFi AP shared mode.
        The system dnsmasq must not bind to wlan0 on either port 53 (DNS)
        or port 67 (DHCP), or NM's dnsmasq fails with 'Address already in use'.
        
        Two directives are needed:
          - bind-dynamic: Only bind to configured interfaces, not 0.0.0.0.
            Frees port 67 on wlan0. Handles USB adapters appearing/disappearing.
          - except-interface=wlan0: Explicitly exclude wlan0 from DNS.
        
        Uses idempotent sed+append: remove existing line, then add fresh.
        """
        dnsmasq_conf = '/etc/dnsmasq.conf'
        try:
            if not os.path.exists(dnsmasq_conf):
                return
            
            with open(dnsmasq_conf, 'r') as f:
                config = f.read()
            
            has_bind_dynamic = False
            has_except = False
            has_old_interface = False
            
            for line in config.split('\n'):
                stripped = line.strip()
                if stripped == 'bind-dynamic':
                    has_bind_dynamic = True
                if stripped == 'except-interface=wlan0':
                    has_except = True
                if stripped == f'interface={self.interface}':
                    has_old_interface = True
            
            restart_needed = False
            
            # Ensure bind-dynamic is present (frees DHCP port 67 on wlan0)
            if not has_bind_dynamic:
                subprocess.run(
                    ['sed', '-i', '/^bind-dynamic$/d', dnsmasq_conf],
                    capture_output=True
                )
                with open(dnsmasq_conf, 'a') as f:
                    f.write('\nbind-dynamic\n')
                restart_needed = True
                logger.info("Added bind-dynamic to dnsmasq.conf")
            
            # Ensure except-interface=wlan0 is present (frees DNS port 53 on wlan0)
            if not has_except:
                subprocess.run(
                    ['sed', '-i', '/^except-interface=wlan0$/d', dnsmasq_conf],
                    capture_output=True
                )
                with open(dnsmasq_conf, 'a') as f:
                    f.write('except-interface=wlan0\n')
                restart_needed = True
                logger.info("Added except-interface=wlan0 to dnsmasq.conf")
            
            # Remove any old interface=wlan0 config from previous versions
            if has_old_interface:
                subprocess.run(
                    ['sed', '-i', f'/^interface={self.interface}$/d', dnsmasq_conf],
                    capture_output=True
                )
                restart_needed = True
                logger.info("Removed old interface=wlan0 from dnsmasq.conf")
            
            if restart_needed:
                subprocess.run(
                    ['/usr/bin/systemctl', 'restart', 'dnsmasq'],
                    capture_output=True
                )
                
        except Exception as e:
            logger.warning(f"Error updating dnsmasq config: {e}")
    
    def enable(self) -> bool:
        """Enable WiFi AP - activate now and configure auto-start on boot"""
        try:
            if not self.is_installed():
                logger.error("WiFi AP not configured - run configure() first")
                return False
            
            # Unblock WiFi
            subprocess.run(
                ['/usr/sbin/rfkill', 'unblock', 'wifi'],
                capture_output=True
            )
            
            # Enable WiFi radio in NetworkManager (rfkill alone isn't always enough)
            subprocess.run(
                ['/usr/bin/nmcli', 'radio', 'wifi', 'on'],
                capture_output=True
            )
            
            # Wait for wlan0 to become available
            import time
            for _ in range(10):
                result = subprocess.run(
                    ['/usr/bin/nmcli', '-t', '-f', 'DEVICE,STATE', 'device'],
                    capture_output=True, text=True
                )
                if 'wlan0:disconnected' in (result.stdout or ''):
                    break
                time.sleep(1)
            
            
            # Ensure autoconnect is OFF on the NM connection
            # (the systemd service handles boot activation instead)
            subprocess.run(
                ['/usr/bin/nmcli', 'connection', 'modify',
                 self.connection_name, 'autoconnect', 'no'],
                capture_output=True
            )
            
            # Clean up old service and dnsmasq config from previous versions
            self._cleanup_old_service()
            self._cleanup_wlan0_dnsmasq()
            
            # Install the startup script and systemd service
            if not self._install_startup_script():
                return False
            if not self._install_delayed_service():
                return False
            
            # Enable the delayed-start service for boot
            subprocess.run(
                ['/usr/bin/systemctl', 'enable', self.delayed_service],
                capture_output=True
            )
            
            # Ensure NetworkManager-wait-online.service is enabled
            # This is required for the network-online.target dependency to work
            # Without it, systemd never reaches network-online.target and our
            # service won't start on boot
            subprocess.run(
                ['/usr/bin/systemctl', 'enable', 'NetworkManager-wait-online.service'],
                capture_output=True
            )
            
            # Activate WiFi AP NOW for immediate use
            success, _, error = self._run_command([
                '/usr/bin/nmcli', 'connection', 'up', self.connection_name
            ])
            
            if not success:
                logger.error(f"Failed to activate WiFi AP: {error}")
                return False
            
            # Clear cache
            self._clear_cache()
            
            logger.info("WiFi AP enabled and active - will auto-start on boot")
            return True
                
        except Exception as e:
            logger.error(f"Error enabling WiFi AP: {e}")
            return False
    
    def disable(self) -> bool:
        """Disable WiFi AP - deactivate and remove auto-start"""
        try:
            # Deactivate the NetworkManager AP connection
            success, _, error = self._run_command([
                '/usr/bin/nmcli', 'connection', 'down', self.connection_name
            ])
            
            if not success:
                logger.warning(f"Could not deactivate WiFi AP (may not be active): {error}")
            
            # Ensure autoconnect stays off
            subprocess.run(
                ['/usr/bin/nmcli', 'connection', 'modify',
                 self.connection_name, 'autoconnect', 'no'],
                capture_output=True
            )
            
            # Disable and remove the delayed-start service
            subprocess.run(
                ['/usr/bin/systemctl', 'stop', self.delayed_service],
                capture_output=True
            )
            subprocess.run(
                ['/usr/bin/systemctl', 'disable', self.delayed_service],
                capture_output=True
            )
            
            service_path = f'/etc/systemd/system/{self.delayed_service}'
            try:
                if os.path.exists(service_path):
                    os.remove(service_path)
            except:
                pass
            
            subprocess.run(['/usr/bin/systemctl', 'daemon-reload'], capture_output=True)
            
            # Also clean up any old service from previous versions
            self._cleanup_old_service()
            
            # Clear cache
            self._clear_cache()
            
            logger.info("WiFi AP disabled - will not auto-start on boot")
            return True
                
        except Exception as e:
            logger.error(f"Error disabling WiFi AP: {e}")
            return False
    
    def restart(self) -> bool:
        """Restart WiFi AP by cycling the NetworkManager connection"""
        try:
            # Bring down
            subprocess.run(
                ['/usr/bin/nmcli', 'connection', 'down', self.connection_name],
                capture_output=True
            )
            
            # Brief pause for interface to settle
            time.sleep(2)
            
            # Bring back up
            success, _, error = self._run_command([
                '/usr/bin/nmcli', 'connection', 'up', self.connection_name
            ])
            
            # Clear cache
            self._clear_cache()
            
            if success:
                logger.info("WiFi AP restarted")
                return True
            else:
                logger.error(f"Failed to restart WiFi AP: {error}")
                return False
                
        except Exception as e:
            logger.error(f"Error restarting WiFi AP: {e}")
            return False
