// Common JavaScript functions for WLED Manager

/**
 * Show alert message to user
 */
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container');
    const alertId = 'alert-' + Date.now();
    
    const alertHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert" id="${alertId}">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    alertContainer.insertAdjacentHTML('beforeend', alertHTML);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alert = document.getElementById(alertId);
        if (alert) {
            const bsAlert = bootstrap.Alert.getInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }
    }, 5000);
}

/**

/**
 * Update system status indicator in navbar
 */
function updateSystemStatus() {
    fetch('/api/system/status')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const status = data.status;
                const allOk = status.networkmanager && status.dnsmasq;
                
                const statusText = document.getElementById('status-text');
                
                if (statusText) {
                    if (allOk) {
                        statusText.className = 'text-success fw-bold';
                        statusText.textContent = '✓ System OK';
                    } else {
                        statusText.className = 'text-danger fw-bold';
                        statusText.textContent = '✗ Issues Detected';
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error updating system status:', error);
            const statusText = document.getElementById('status-text');
            if (statusText) {
                statusText.className = 'text-warning';
                statusText.textContent = 'Status Unknown';
            }
        });
}

/**
 * Format MAC address to standard format
 */
function formatMacAddress(mac) {
    return mac.toLowerCase().replace(/[^a-f0-9]/g, '').match(/.{1,2}/g).join(':');
}

/**
 * Validate IP address format
 */
function isValidIP(ip) {
    const pattern = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!pattern.test(ip)) return false;
    
    const octets = ip.split('.');
    for (let octet of octets) {
        const num = parseInt(octet);
        if (num < 0 || num > 255) return false;
    }
    return true;
}

/**
 * Validate MAC address format
 */
function isValidMAC(mac) {
    const pattern = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/;
    return pattern.test(mac);
}

/**
 * Format bytes to human readable format
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showAlert('Copied to clipboard', 'success');
    }).catch(err => {
        showAlert('Failed to copy to clipboard', 'danger');
    });
}

/**
 * Debounce function for input handlers
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize system status updates on page load
document.addEventListener('DOMContentLoaded', function() {
    updateSystemStatus();
    
    // Update status every 30 seconds
    setInterval(updateSystemStatus, 30000);
});

// Handle offline/online events
window.addEventListener('offline', function() {
    showAlert('Connection lost. Please check your network.', 'warning');
});

window.addEventListener('online', function() {
    showAlert('Connection restored.', 'success');
    updateSystemStatus();
});
