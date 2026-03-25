#!/bin/bash
# Update tunnel URL and deploy Worker to Cloudflare Pages
# Uses serveo.net (works with Cloudflare Workers)
# Usage: ./scripts/update_tunnel.sh [tunnel_url]

set -e

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PUBLIC_DIR="$PROJECT_ROOT/public"

NEW_URL="${1:-}"

echo "=== Tunnel Update Script ==="
echo ""

# Step 1: Start new tunnel if URL not provided
if [ -z "$NEW_URL" ]; then
    echo "[1/5] Starting serveo tunnel..."
    pkill -f cloudflared 2>/dev/null || true
    pkill -f "ssh.*serveo" 2>/dev/null || true
    sleep 1
    
    # Start serveo tunnel (works with Cloudflare Workers)
    nohup ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:localhost:5000 serveo.net > /tmp/serveo.log 2>&1 &
    sleep 5
    
    # Extract URL from serveo output
    NEW_URL=$(grep -oP 'https://[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+\.serveousercontent\.com' /tmp/serveo.log | head -1)
fi

if [ -z "$NEW_URL" ]; then
    echo "ERROR: Could not get tunnel URL"
    exit 1
fi

echo "    Tunnel URL: $NEW_URL"

# Step 2: Update tunnel.json
echo "[2/5] Updating tunnel.json..."
cat > "$PUBLIC_DIR/tunnel.json" << EOF
{
  "tunnel_url": "$NEW_URL",
  "updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
echo "    Done"

# Step 2b: Update Worker fallback URL
echo "[2.5/5] Updating Worker fallback URL..."
sed -i "s|const FALLBACK_URL = .*|const FALLBACK_URL = \"$NEW_URL\";|" "$PUBLIC_DIR/_worker.js"
echo "    Done"

# Step 3: Push to GitHub
echo "[3/5] Pushing to GitHub..."
cd "$PROJECT_ROOT"
git add public/tunnel.json public/_worker.js 2>/dev/null || git add public/tunnel.json
git commit -m "Update tunnel URL: $NEW_URL" || echo "    No changes to commit"
git push origin main
echo "    Done"

# Step 4: Deploy Worker to Cloudflare Pages
echo "[4/5] Deploying Worker to Cloudflare Pages..."
if [ -n "$CLOUDFLARE_API_TOKEN" ]; then
    cd "$PUBLIC_DIR"
    wrangler pages deploy . --project-name gbctwoserver --commit-dirty=true 2>&1 | tail -3
else
    echo "    Skipped (CLOUDFLARE_API_TOKEN not set)"
    echo "    Set it with: export CLOUDFLARE_API_TOKEN=your_token"
fi

# Step 5: Verify
echo "[5/5] Verifying..."
sleep 2
if curl -skL --max-time 5 "$NEW_URL/api/health" | grep -q "ok"; then
    echo "    ✅ Tunnel is working"
else
    echo "    ⚠️  Tunnel may need a moment to start"
fi

echo ""
echo "=== Complete ==="
echo "  Tunnel: $NEW_URL"
echo "  Public: https://gbctwoserver.pages.dev"
echo ""
