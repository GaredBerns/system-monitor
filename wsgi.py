#!/usr/bin/env python3
"""
WSGI Entry Point for Production Server
Entry point for Gunicorn/Eventlet
"""
import os
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Import and configure app
from src.c2.server import app, socketio
from src.c2.orchestrator import Integration
from src.utils.logger import get_logger

log = get_logger('wsgi')

# Initialize integration modules
integration = Integration()
integration.start()
log.info("✓ Integration modules started")

# Export for WSGI servers
application = app

if __name__ == "__main__":
    # Development mode
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    socketio.run(app, host=host, port=port, debug=False)
