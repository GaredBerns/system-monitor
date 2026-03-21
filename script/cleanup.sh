#!/bin/bash
# Automated cleanup cron job for C2 server
# Add to crontab: 0 2 * * * /path/to/cleanup_cron.sh

cd "$(dirname "$0")/.."

echo "[$(date)] Starting C2 cleanup..."

# Run Python cleanup script
python3 core/cleanup.py >> data/cleanup.log 2>&1

# Cleanup old screenshots (older than 24 hours)
find data/screenshots -name "*.jpg" -mtime +1 -delete 2>/dev/null
find data/screenshots -name "*.png" -mtime +1 -delete 2>/dev/null

# Cleanup old tunnel logs
if [ -f data/tunnel.log ]; then
    tail -n 1000 data/tunnel.log > data/tunnel.log.tmp
    mv data/tunnel.log.tmp data/tunnel.log
fi

# Cleanup old server logs
if [ -f server.log ]; then
    tail -n 5000 server.log > server.log.tmp
    mv server.log.tmp server.log
fi

echo "[$(date)] Cleanup complete"
