#!/bin/bash
# C2 Server Installation Script

set -e

echo "╔══════════════════════════════════════════╗"
echo "║     C2 SERVER - INSTALLATION SCRIPT      ║"
echo "╚══════════════════════════════════════════╝"

# Check root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root"
    exit 1
fi

PROJECT_DIR="/mnt/F/C2_server-main"
cd "$PROJECT_DIR" || exit 1

echo ""
echo "📦 Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv wget curl firefox-esr

echo ""
echo "🐍 Installing Python packages..."
pip3 install -q -r requirements.txt

echo ""
echo "🔧 Setting up directories..."
mkdir -p data/backups data/uploads logs

echo ""
echo "🔐 Generating SSL certificates..."
if [ ! -f "data/cert.pem" ]; then
    openssl req -x509 -newkey rsa:2048 -keyout data/key.pem -out data/cert.pem \
        -days 365 -nodes -subj "/CN=c2server" 2>/dev/null
    echo "✓ SSL certificates generated"
fi

echo ""
echo "📋 Installing systemd service..."
cp scripts/c2-server.service /etc/systemd/system/
systemctl daemon-reload
echo "✓ Service installed"

echo ""
echo "🔥 Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 5000/tcp
    echo "✓ Firewall configured (port 5000)"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Start server:  systemctl start c2-server"
echo "   2. Enable autostart:  systemctl enable c2-server"
echo "   3. Check status:  systemctl status c2-server"
echo "   4. View logs:  journalctl -u c2-server -f"
echo ""
echo "🌐 Access dashboard: http://$(hostname -I | awk '{print $1}'):5000"
echo "🔑 Default login: admin / admin"
