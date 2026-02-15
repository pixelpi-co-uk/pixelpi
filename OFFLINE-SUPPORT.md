# Adding Offline CSS Support

By default, PixelPi uses CDN links for Bootstrap CSS and icons. This requires devices to have internet access (cellular data or WiFi) to display the interface correctly.

For completely offline use (devices with no internet connection), you can download and serve Bootstrap locally.

## Quick Setup (On Pi with Internet)

```bash
# Navigate to static directories
cd /opt/wled-manager/web/static

# Download Bootstrap CSS
curl -sL https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css -o css/bootstrap.min.css

# Download Bootstrap JavaScript
curl -sL https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js -o js/bootstrap.bundle.min.js

# Download Bootstrap Icons
curl -sL https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.min.css -o css/bootstrap-icons.min.css

# Download Bootstrap Icons fonts (required for icons to work)
mkdir -p fonts
cd fonts
curl -sL https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/fonts/bootstrap-icons.woff2 -o bootstrap-icons.woff2
curl -sL https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/fonts/bootstrap-icons.woff -o bootstrap-icons.woff
```

## Update Templates

Edit `/opt/wled-manager/web/templates/base.html`:

**Change:**
```html
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
```

**To:**
```html
<link href="{{ url_for('static', filename='css/bootstrap.min.css') }}" rel="stylesheet">
<link rel="stylesheet" href="{{ url_for('static', filename='css/bootstrap-icons.min.css') }}">
```

**And change:**
```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
```

**To:**
```html
<script src="{{ url_for('static', filename='js/bootstrap.bundle.min.js') }}"></script>
```

## Restart Service

```bash
sudo systemctl restart wled-manager
```

## Alternative: Pre-download on Development Machine

If your Pi doesn't have internet access:

1. Download the files on a computer with internet
2. Copy them to the Pi via USB drive or SCP
3. Place them in the correct directories as shown above
4. Update the templates
5. Restart the service

## File Sizes

- bootstrap.min.css: ~190 KB
- bootstrap.bundle.min.js: ~260 KB  
- bootstrap-icons.min.css: ~80 KB
- bootstrap-icons.woff2: ~160 KB

Total: ~690 KB (very small)

## When is This Needed?

**NOT needed if:**
- Devices accessing dashboard have cellular data (iPads, iPhones)
- Devices have WiFi connection to internet while connected to Pi's WiFi AP
- Acceptable to have unstyled interface on offline devices

**Needed if:**
- Devices have NO internet access at all (WiFi-only laptops/tablets)
- Working in environments without cellular coverage
- Want guaranteed offline functionality
