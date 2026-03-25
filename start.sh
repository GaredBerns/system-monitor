#!/bin/bash
# System Monitor - Full Startup with Public Tunnel

echo "🚀 System Monitor - Starting..."
echo ""

# Kill existing processes
pkill -f "python.*run_unified" 2>/dev/null
pkill -f cloudflared 2>/dev/null
sleep 1

# Start server
echo "📡 Starting server..."
cd /mnt/F/C2_server-main
nohup python run_unified.py > /tmp/server.log 2>&1 &
SERVER_PID=$!
echo "   Server PID: $SERVER_PID"
sleep 3

# Start tunnel
echo "🌐 Starting Cloudflare Tunnel..."
nohup cloudflared tunnel --url http://localhost:5000 > /tmp/tunnel.log 2>&1 &
TUNNEL_PID=$!
echo "   Tunnel PID: $TUNNEL_PID"

# Wait for URL
echo ""
echo "⏳ Waiting for tunnel URL..."
sleep 8

# Extract URL
URL=$(grep -o 'https://[^ ]*\.trycloudflare\.com' /tmp/tunnel.log | head -1)

if [ -n "$URL" ]; then
    echo ""
    echo "✅ System Monitor is running!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🌐 Public URL: $URL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📍 Local:  http://localhost:5000"
    echo "🔧 PID:    Server=$SERVER_PID, Tunnel=$TUNNEL_PID"
    echo ""
    echo "📝 URL saved to: /tmp/tunnel_url.txt"
    echo "$URL" > /tmp/tunnel_url.txt
    
    # Update README with current URL
    sed -i "s|https://.*\.trycloudflare\.com|$URL|g" /mnt/F/C2_server-main/README.md 2>/dev/null
    echo "📝 README updated with current URL"
else
    echo "❌ Failed to get tunnel URL"
    echo "Check logs: cat /tmp/tunnel.log"
fi

echo ""
echo "💡 To stop: pkill -f 'python.*run_unified'; pkill cloudflared"
echo "💡 To restart: ./start.sh"
