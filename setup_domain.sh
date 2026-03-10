#!/bin/bash
# Setup local domain c2panel.rog on this machine and prepare for LAN access.
# Run: sudo ./setup_domain.sh

set -e
DOMAIN="c2panel.rog"
DATA_DIR="$(dirname "$0")/data"
PORT=8443

echo "[*] Domain: $DOMAIN (https://${DOMAIN}:${PORT})"

# 1) Hosts: add 127.0.0.1 c2panel.rog
if grep -q "c2panel.rog" /etc/hosts 2>/dev/null; then
  echo "[*] /etc/hosts already contains c2panel.rog"
else
  echo "127.0.0.1 $DOMAIN" >> /etc/hosts
  echo "[+] Added 127.0.0.1 $DOMAIN to /etc/hosts"
fi

# 2) SSL cert for c2panel.rog (SAN so browser accepts the name)
mkdir -p "$DATA_DIR"
openssl req -x509 -newkey rsa:2048 \
  -keyout "$DATA_DIR/key.pem" -out "$DATA_DIR/cert.pem" \
  -days 365 -nodes \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1"
echo "[+] SSL certificate generated for $DOMAIN"

# 3) LAN IP for other devices
LAN_IP=""
if command -v ip &>/dev/null; then
  LAN_IP=$(ip -4 route get 8.8.8.8 2>/dev/null | grep -oP 'src \K\S+' || true)
fi
if [ -z "$LAN_IP" ]; then
  LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi

echo ""
echo "=== Done ==="
echo "On THIS machine open:  https://${DOMAIN}:${PORT}"
echo ""
if [ -n "$LAN_IP" ]; then
  echo "On OTHER devices in the same network:"
  echo "  1. Add to their hosts file:  $LAN_IP  $DOMAIN"
  echo "     Windows: C:\\Windows\\System32\\drivers\\etc\\hosts"
  echo "     Linux/Mac: /etc/hosts"
  echo "  2. Open in browser: https://${DOMAIN}:${PORT}"
  echo ""
  echo "One-line for Linux/Mac (run on the other PC):"
  echo "  echo '$LAN_IP $DOMAIN' | sudo tee -a /etc/hosts"
fi
echo ""
