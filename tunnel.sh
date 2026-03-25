#!/bin/bash
# Cloudflare Tunnel - Permanent public URL for C2 Server

PORT=${1:-5000}

echo "╔══════════════════════════════════════════════════════╗"
echo "║     Cloudflare Tunnel - C2 Server                    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "🚀 Starting tunnel to http://localhost:$PORT"
echo "📌 Your public URL will appear below:"
echo ""

# Run cloudflared tunnel
cloudflared tunnel --url http://localhost:$PORT 2>&1 | while read -r line; do
    # Extract and highlight the public URL
    if [[ "$line" =~ https://[a-zA-Z0-9-]+\.trycloudflare\.com ]]; then
        URL=$(echo "$line" | grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | head -1)
        echo ""
        echo "═════════════════════════════════════════════════════════"
        echo "✅ PUBLIC URL: $URL"
        echo "═════════════════════════════════════════════════════════"
        echo ""
        echo "💡 Add this URL to config:"
        echo "   public_url: $URL"
        echo ""
    fi
    echo "$line"
done
