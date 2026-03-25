#!/bin/bash
# Cloudflare Tunnel Setup for gbctwoserver.net
# This script sets up a permanent tunnel pointing to your local C2 server

set -e

DOMAIN="gbctwoserver.net"
TUNNEL_NAME="c2-server"
LOCAL_PORT="${1:-5000}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Cloudflare Tunnel Setup - $DOMAIN${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo -e "${YELLOW}Installing cloudflared...${NC}"
    if command -v apt &> /dev/null; then
        curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
        sudo dpkg -i /tmp/cloudflared.deb
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y cloudflared
    else
        curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o ~/.local/bin/cloudflared
        chmod +x ~/.local/bin/cloudflared
    fi
fi

echo -e "${GREEN}✓ cloudflared installed${NC}"

# Check if already logged in
if [ ! -f ~/.cloudflared/cert.pem ]; then
    echo -e "${YELLOW}Logging into Cloudflare...${NC}"
    echo -e "${YELLOW}A browser will open. Please authenticate.${NC}"
    cloudflared tunnel login
fi

echo -e "${GREEN}✓ Authenticated with Cloudflare${NC}"

# Create tunnel if not exists
TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}' || true)

if [ -z "$TUNNEL_ID" ]; then
    echo -e "${YELLOW}Creating tunnel '$TUNNEL_NAME'...${NC}"
    cloudflared tunnel create "$TUNNEL_NAME"
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
fi

echo -e "${GREEN}✓ Tunnel ID: $TUNNEL_ID${NC}"

# Route DNS
echo -e "${YELLOW}Configuring DNS for $DOMAIN...${NC}"
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" 2>/dev/null || true

# Also add www subdomain
cloudflared tunnel route dns "$TUNNEL_NAME" "www.$DOMAIN" 2>/dev/null || true

echo -e "${GREEN}✓ DNS configured${NC}"

# Create tunnel config
CONFIG_DIR="$HOME/.cloudflared"
CONFIG_FILE="$CONFIG_DIR/config.yml"

mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_FILE" << EOF
tunnel: $TUNNEL_ID
credentials-file: $CONFIG_DIR/$TUNNEL_ID.json

ingress:
  - hostname: $DOMAIN
    service: http://localhost:$LOCAL_PORT
  - hostname: www.$DOMAIN
    service: http://localhost:$LOCAL_PORT
  - service: http_status:404
EOF

echo -e "${GREEN}✓ Config created: $CONFIG_FILE${NC}"

# Create systemd service for auto-start
SERVICE_FILE="/tmp/cloudflared.service"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Cloudflare Tunnel for $DOMAIN
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=$(command -v cloudflared) tunnel run $TUNNEL_NAME
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              SETUP COMPLETE!${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Domain:     ${GREEN}https://$DOMAIN${NC}"
echo -e "Tunnel:     ${GREEN}$TUNNEL_NAME ($TUNNEL_ID)${NC}"
echo -e "Local:      ${GREEN}http://localhost:$LOCAL_PORT${NC}"
echo ""
echo -e "${YELLOW}To start the tunnel now:${NC}"
echo "  cloudflared tunnel run $TUNNEL_NAME"
echo ""
echo -e "${YELLOW}To auto-start on boot:${NC}"
echo "  sudo cp $SERVICE_FILE /etc/systemd/system/"
echo "  sudo systemctl enable --now cloudflared"
echo ""
echo -e "${YELLOW}To start both server + tunnel:${NC}"
echo "  ./scripts/start-with-tunnel.sh"
