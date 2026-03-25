#!/bin/bash
# Cloudflare Tunnel - Free permanent URL

echo "🚀 Starting Cloudflare Tunnel..."
echo "📍 Local server: http://localhost:5000"
echo ""

# Kill existing tunnel
pkill -f "cloudflared tunnel" 2>/dev/null

# Start tunnel in background
cloudflared tunnel --url http://localhost:5000 2>&1 | tee /tmp/tunnel.log &

# Wait for URL
echo "⏳ Waiting for tunnel URL..."
sleep 5

# Extract URL
URL=$(grep -o 'https://[^ ]*\.trycloudflare\.com' /tmp/tunnel.log | head -1)

if [ -n "$URL" ]; then
    echo ""
    echo "✅ Tunnel created!"
    echo "🌐 Public URL: $URL"
    echo ""
    echo "📝 Save this URL - it will work while server is running"
    echo ""
    # Save to file
    echo "$URL" > /tmp/tunnel_url.txt
else
    echo "❌ Failed to get tunnel URL"
    echo "Check logs: cat /tmp/tunnel.log"
fi
