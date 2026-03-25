#!/bin/bash
# Start C2 Server + Cloudflare Tunnel together

DOMAIN="gbctwoserver.net"
PORT="${1:-5000}"

# Kill existing processes
pkill -f "python.*run_unified" 2>/dev/null || true
pkill -f "cloudflared tunnel run" 2>/dev/null || true
sleep 1

# Start C2 server
echo "Starting C2 Server on port $PORT..."
cd "$(dirname "$0")/.."
python3 run_unified.py --port "$PORT" &
SERVER_PID=$!

sleep 2

# Start tunnel
echo "Starting Cloudflare Tunnel..."
cloudflared tunnel run c2-server &
TUNNEL_PID=$!

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  C2 Server + Tunnel Running!                          ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Public URL:  https://$DOMAIN"
echo "  Local URL:   http://localhost:$PORT"
echo "  Server PID:  $SERVER_PID"
echo "  Tunnel PID:  $TUNNEL_PID"
echo ""
echo "Press Ctrl+C to stop both"
echo ""

# Wait for either process
wait $SERVER_PID $TUNNEL_PID
