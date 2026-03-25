#!/bin/bash
# Dynamic Tunnel Manager
# Starts cloudflared tunnel and updates tunnel.json on GitHub
# Worker automatically picks up new URL from GitHub
#
# Usage: ./scripts/update_tunnel.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PUBLIC_DIR="$PROJECT_ROOT/public"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║           DYNAMIC TUNNEL MANAGER v2.0                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Kill existing tunnels
echo "[1/4] Stopping existing tunnels..."
pkill -f cloudflared 2>/dev/null || true
pkill -f serveo 2>/dev/null || true
sleep 1
echo "      Done"

# Start tunnel
echo "[2/4] Starting cloudflare tunnel..."
nohup cloudflared tunnel --url http://localhost:5000 > /tmp/tunnel.log 2>&1 &
sleep 6

TUNNEL_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/tunnel.log | head -1)

if [ -z "$TUNNEL_URL" ]; then
    echo "      ERROR: Could not get tunnel URL"
    echo "      Check if cloudflared is installed and working"
    exit 1
fi

echo "      URL: $TUNNEL_URL"

# Update tunnel.json
echo "[3/4] Updating tunnel.json..."
cat > "$PUBLIC_DIR/tunnel.json" << EOF
{
  "tunnel_url": "$TUNNEL_URL",
  "updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
echo "      Done"

# Commit and push to GitHub
echo "[4/4] Pushing to GitHub..."
cd "$PROJECT_ROOT"
git add public/tunnel.json
git commit -m "Update tunnel: $TUNNEL_URL" 2>/dev/null || echo "      No changes"
git push origin main 2>/dev/null || echo "      Push failed (check git config)"
echo "      Done"

# Verify tunnel
echo ""
echo "Verifying tunnel..."
if curl -s --max-time 5 "$TUNNEL_URL/api/health" | grep -q "ok"; then
    echo "      ✅ Tunnel is working"
else
    echo "      ⚠️  Tunnel may need a moment to start"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ TUNNEL ACTIVE                                          ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Direct: $TUNNEL_URL"
echo "║  Public: https://gbctwoserver.pages.dev                    ║"
echo "║  Config: public/tunnel.json                                ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Worker fetches tunnel URL from GitHub automatically       ║"
echo "║  Cache TTL: 1 minute                                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
