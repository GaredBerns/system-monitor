#!/bin/bash
# Start C2 Server with Cloudflare Tunnel

echo "╔══════════════════════════════════════════════════════╗"
echo "║     C2 Server + Cloudflare Tunnel                     ║"
echo "╚══════════════════════════════════════════════════════╝"

# Start C2 server in background
echo "🚀 Starting C2 Server..."
bash server.sh start &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Start Cloudflare tunnel
echo "🌐 Starting Cloudflare Tunnel..."
bash tunnel.sh 5000 &
TUNNEL_PID=$!

# Handle shutdown
trap "kill $SERVER_PID $TUNNEL_PID 2>/dev/null" EXIT

# Keep running
wait
