#!/usr/bin/env python3
# Pool Worker Monitor
import requests, time, json
from datetime import datetime

WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
POOL_API = "https://moneroocean.stream/api"

def check_workers():
    try:
        url = f"{POOL_API}/miner/{WALLET}/chart/hashrate/allWorkers"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            workers = [item.get('name') for item in data if 'name' in item]
            return workers
        return []
    except:
        return []

def check_stats():
    try:
        url = f"{POOL_API}/miner/{WALLET}/stats"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
        return None
    except:
        return None

print("🔍 CHECKING POOL...")
print(f"Wallet: {WALLET[:20]}...{WALLET[-10:]}")
print()

workers = check_workers()
stats = check_stats()

if workers:
    print(f"✅ WORKERS FOUND: {len(workers)}")
    for w in workers:
        print(f"   • {w}")
else:
    print("⏳ NO WORKERS YET")
    print("   Workers appear 2-5 min after kernel starts")

print()

if stats:
    hashrate = stats.get('hash', 0) or 0
    if hashrate > 0:
        print(f"⛏️  Hashrate: {hashrate:.2f} H/s")
    else:
        print("⛏️  Hashrate: 0 H/s")
else:
    print("📊 No stats yet")

print()
print("🌐 Check manually:")
print(f"   https://moneroocean.stream/#/dashboard")
