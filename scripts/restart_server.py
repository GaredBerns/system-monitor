#!/usr/bin/env python3
import subprocess
import time
import sys

def restart_server():
    print("🔄 Stopping C2 server...")
    
    # Kill Flask server
    subprocess.run("pkill -9 -f 'python.*run_unified.py'", shell=True)
    subprocess.run("pkill -9 -f 'flask'", shell=True)
    subprocess.run("pkill -9 -f 'server.py'", shell=True)
    
    time.sleep(2)
    
    print("✓ Server stopped")
    print("🚀 Starting C2 server...")
    
    # Start server
    subprocess.Popen(
        ["python3", "run_unified.py", "--host", "0.0.0.0", "--port", "5000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd="/mnt/F/C2_server-main"
    )
    
    time.sleep(3)
    
    print("✓ Server started on http://0.0.0.0:5000")
    print("✓ Dashboard: http://localhost:5000")

if __name__ == "__main__":
    restart_server()
