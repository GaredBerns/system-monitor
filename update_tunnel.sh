#!/bin/bash
# Update tunnel URL in GitHub and restart tunnel

NEW_URL="${1:-}"

if [ -z "$NEW_URL" ]; then
    echo "Starting new cloudflare tunnel..."
    pkill -f cloudflared 2>/dev/null
    cloudflared tunnel --url http://localhost:5000 > /tmp/cloudflared.log 2>&1 &
    sleep 5
    NEW_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log | head -1)
fi

if [ -z "$NEW_URL" ]; then
    echo "ERROR: Could not get tunnel URL"
    exit 1
fi

echo "New tunnel URL: $NEW_URL"

# Update tunnel.json
cd /mnt/F/C2_server-main
cat > public/tunnel.json << EOF
{
  "tunnel_url": "$NEW_URL",
  "updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# Push to GitHub
git add public/tunnel.json
git commit -m "Update tunnel URL: $NEW_URL"
git push origin main

echo ""
echo "✅ Tunnel URL updated!"
echo "   URL: $NEW_URL"
echo "   Public: https://gbctwoserver.pages.dev"
echo ""
echo "Worker will pick up new URL within 60 seconds"
