#!/bin/bash
# Generate a CA and server certificate so the panel doesn't look suspicious.
# After running: install data/ca.crt as trusted root (see end of script).
# Run from C2_server: sudo bash scripts/gen_trusted_cert.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$BASE_DIR/data"
DOMAIN="c2panel.rog"
DAYS=825

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

# 1) Local CA (looks like internal corp CA)
echo "[*] Creating root CA..."
openssl genrsa -out ca.key 2048 2>/dev/null
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt -nodes \
  -subj "/C=US/ST=California/L=San Francisco/O=ROG Panel Services/OU=Security/CN=ROG Panel Root CA" \
  -addext "basicConstraints=critical,CA:true" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"

# 2) Server key
echo "[*] Creating server key..."
openssl genrsa -out server.key 2048 2>/dev/null

# 3) SAN config for server cert
LAN_IP=""
command -v ip &>/dev/null && LAN_IP=$(ip -4 route get 8.8.8.8 2>/dev/null | grep -oP 'src \K\S+' || true)
[ -z "$LAN_IP" ] && LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
# SAN: domain, localhost, IPs
SAN="DNS:${DOMAIN},DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:::1"
[ -n "$LAN_IP" ] && SAN="${SAN},IP:${LAN_IP}"

# 4) Server CSR and sign with CA
echo "[*] Signing server certificate..."
openssl req -new -key server.key -out server.csr -nodes \
  -subj "/C=US/ST=California/O=ROG Panel Services/OU=IT/CN=${DOMAIN}" \
  -addext "subjectAltName=${SAN}" \
  -addext "extendedKeyUsage=serverAuth" \
  -addext "keyUsage=digitalSignature,keyEncipherment"

cat > _ext.cnf << EOF
subjectAltName=$SAN
extendedKeyUsage=serverAuth
keyUsage=digitalSignature,keyEncipherment
EOF
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days "$DAYS" -extfile _ext.cnf
rm -f _ext.cnf

# 5) Install as cert.pem / key.pem for the server
cp server.crt cert.pem
cp server.key key.pem
rm -f server.csr

echo ""
echo "[+] Certificate created. Server will use cert.pem and key.pem."
echo ""
echo "=== To stop browser 'untrusted' warnings, install the CA as trusted: ==="
echo ""
echo "  Linux (system):"
echo "    sudo cp $DATA_DIR/ca.crt /usr/local/share/ca-certificates/rog-panel-ca.crt"
echo "    sudo update-ca-certificates"
echo ""
echo "  Firefox (this profile only):"
echo "    Settings → Privacy & Security → Certificates → View Certificates → Authorities → Import"
echo "    Select: $DATA_DIR/ca.crt"
echo ""
echo "  Windows:"
echo "    Double-click ca.crt → Install Certificate → Local Machine → Place in 'Trusted Root Certification Authorities'"
echo ""
echo "  macOS:"
echo "    Double-click ca.crt → Add to Keychain → mark 'ROG Panel Root CA' as Always Trust"
echo ""
echo "CA cert path: $DATA_DIR/ca.crt"
echo ""
