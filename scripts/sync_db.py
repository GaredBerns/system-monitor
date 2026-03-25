#!/usr/bin/env python3
"""
Database Sync Tool - Sync agents/tasks between local and remote C2 servers.

Usage:
  python scripts/sync_db.py --export                    # Export local to JSON
  python scripts/sync_db.py --import data.json          # Import from JSON
  python scripts/sync_db.py --pull https://server.com   # Pull from remote
  python scripts/sync_db.py --merge https://server.com  # Merge remote into local
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "c2.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def export_db(output_path=None):
    """Export all data to JSON."""
    conn = get_db()
    c = conn.cursor()
    
    export = {
        "exported_at": datetime.now().isoformat(),
        "agents": [],
        "tasks": [],
        "config": [],
        "users": [],
    }
    
    # Agents
    c.execute("SELECT * FROM agents")
    export["agents"] = [dict(r) for r in c.fetchall()]
    
    # Tasks
    c.execute("SELECT * FROM tasks")
    export["tasks"] = [dict(r) for r in c.fetchall()]
    
    # Config
    c.execute("SELECT * FROM config")
    export["config"] = [dict(r) for r in c.fetchall()]
    
    # Users (without passwords)
    c.execute("SELECT id, username, role, created_at FROM users")
    export["users"] = [dict(r) for r in c.fetchall()]
    
    conn.close()
    
    if output_path:
        Path(output_path).write_text(json.dumps(export, indent=2, default=str))
        print(f"✓ Exported to {output_path}")
    else:
        print(json.dumps(export, indent=2, default=str))
    
    return export


def import_db(input_path, merge=True):
    """Import data from JSON."""
    data = json.loads(Path(input_path).read_text())
    conn = get_db()
    c = conn.cursor()
    
    # Import agents
    for agent in data.get("agents", []):
        existing = c.execute("SELECT id FROM agents WHERE id=?", (agent["id"],)).fetchone()
        if existing and merge:
            # Update existing
            c.execute("""
                UPDATE agents SET 
                    hostname=?, username=?, os=?, arch=?, 
                    ip_external=?, ip_internal=?, platform_type=?,
                    last_seen=?, is_alive=?
                WHERE id=?
            """, (
                agent.get("hostname"), agent.get("username"), agent.get("os"),
                agent.get("arch"), agent.get("ip_external"), agent.get("ip_internal"),
                agent.get("platform_type"), agent.get("last_seen"), agent.get("is_alive", 1),
                agent["id"]
            ))
        else:
            # Insert new
            c.execute("""
                INSERT OR REPLACE INTO agents 
                (id, hostname, username, os, arch, ip_external, ip_internal, platform_type, last_seen, is_alive)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent["id"], agent.get("hostname"), agent.get("username"), agent.get("os"),
                agent.get("arch"), agent.get("ip_external"), agent.get("ip_internal"),
                agent.get("platform_type"), agent.get("last_seen"), agent.get("is_alive", 1)
            ))
    
    # Import tasks
    for task in data.get("tasks", []):
        c.execute("""
            INSERT OR REPLACE INTO tasks 
            (id, agent_id, command, status, result, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            task["id"], task.get("agent_id"), task.get("command"),
            task.get("status"), task.get("result"), task.get("created_at"),
            task.get("completed_at")
        ))
    
    conn.commit()
    conn.close()
    
    print(f"✓ Imported {len(data.get('agents', []))} agents, {len(data.get('tasks', []))} tasks")


def pull_from_remote(url, token=None):
    """Pull data from remote server."""
    # Ensure URL format
    if not url.startswith("http"):
        url = f"https://{url}"
    
    # Fetch agents
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        req = Request(f"{url.rstrip('/')}/api/agents", headers=headers)
        resp = urlopen(req, timeout=10)
        agents = json.loads(resp.read().decode())
        
        print(f"✓ Fetched {len(agents)} agents from {url}")
        return {"agents": agents, "exported_at": datetime.now().isoformat()}
    except URLError as e:
        print(f"✗ Failed to connect: {e.reason}")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def merge_from_remote(url, token=None):
    """Merge remote data into local."""
    data = pull_from_remote(url, token)
    if not data:
        return
    
    conn = get_db()
    c = conn.cursor()
    
    for agent in data.get("agents", []):
        existing = c.execute("SELECT id FROM agents WHERE id=?", (agent["id"],)).fetchone()
        if not existing:
            c.execute("""
                INSERT INTO agents (id, hostname, username, os, arch, ip_external, ip_internal, platform_type, last_seen, is_alive)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent["id"], agent.get("hostname"), agent.get("username"),
                agent.get("os"), agent.get("arch"), agent.get("ip_external"),
                agent.get("ip_internal"), agent.get("platform_type"),
                agent.get("last_seen"), agent.get("is_alive", 1)
            ))
    
    conn.commit()
    conn.close()
    print(f"✓ Merged {len(data.get('agents', []))} agents into local DB")


def main():
    parser = argparse.ArgumentParser(description="C2 Database Sync Tool")
    parser.add_argument("--export", action="store_true", help="Export local DB to JSON")
    parser.add_argument("--import", dest="import_file", help="Import from JSON file")
    parser.add_argument("--pull", metavar="URL", help="Pull data from remote server")
    parser.add_argument("--merge", metavar="URL", help="Merge remote data into local")
    parser.add_argument("--output", "-o", default="db_export.json", help="Output file for export")
    parser.add_argument("--token", "-t", help="Auth token for remote server")
    
    args = parser.parse_args()
    
    if args.export:
        export_db(args.output)
    elif args.import_file:
        import_db(args.import_file)
    elif args.pull:
        pull_from_remote(args.pull, args.token)
    elif args.merge:
        merge_from_remote(args.merge, args.token)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
