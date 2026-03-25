#!/usr/bin/env python3
"""
System Monitor Agent
Cross-platform monitoring agent
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Main entry point for system monitor agent."""
    print("[System Monitor] Starting agent...")
    
    # Import and run the universal agent
    try:
        from src.agents.universal import main as agent_main
        agent_main()
    except ImportError:
        print("[System Monitor] Agent module not found, running standalone mode")
        _standalone_mode()

def _standalone_mode():
    """Standalone mode without dependencies."""
    import urllib.request
    import json
    import threading
    import time
    
    class MonitorClient:
        def __init__(self, server_url="http://localhost:5000"):
            self.url = server_url
            threading.Thread(target=self._heartbeat, daemon=True).start()
            print(f"[System Monitor] Connected to {server_url}")
        
        def _heartbeat(self):
            while True:
                try:
                    urllib.request.urlopen(f"{self.url}/api/ping", timeout=5)
                except:
                    pass
                time.sleep(60)
    
    # Get server URL from env or default
    server_url = os.environ.get("SYSMON_SERVER", "http://localhost:5000")
    MonitorClient(server_url)
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[System Monitor] Stopped")

if __name__ == "__main__":
    main()
