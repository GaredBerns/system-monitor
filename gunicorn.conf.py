#!/usr/bin/env python3
"""
Gunicorn Configuration for C2 Server
Production WSGI server with WebSocket support via eventlet
"""
import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent

# Server binding
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '5000')}"

# Workers - single worker for WebSocket compatibility
worker_class = "eventlet"
workers = 1
worker_connections = 10000

# Timeouts
timeout = 300
graceful_timeout = 30
keepalive = 5

# Process naming
proc_name = "c2-server"
pidfile = str(BASE_DIR / "data" / "c2-server.pid")

# Logging
accesslog = str(BASE_DIR / "logs" / "access.log")
errorlog = str(BASE_DIR / "logs" / "error.log")
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Performance
preload_app = False  # Required for eventlet
max_requests = 10000
max_requests_jitter = 500

# Daemon mode
daemon = False

# Temp directory
worker_tmp_dir = "/tmp"

def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"""
╔════════════════════════════════════════════╗
║         C2 SERVER - PRODUCTION             ║
╚════════════════════════════════════════════╝
Workers: {workers} (eventlet)
Address: {bind}
""")

def when_ready(server):
    """Called just after the server is started."""
    print("✓ Server ready to accept connections")

def on_exit(server):
    """Called just before the master process exits."""
    print("✓ Server shutting down...")
