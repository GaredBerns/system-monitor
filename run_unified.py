#!/usr/bin/env python3
"""
System Monitor - Unified Launcher
"""
import os, sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from flask import Flask
from src.c2.server import app as main_app
from src.c2.orchestrator import Integration
from src.utils.logger import get_logger

log = get_logger('launcher')

def setup_app():
    """Setup Flask app with all modules"""
    log.section("System Monitor - Starting")
    
    log.subsection("Initializing")
    integration = Integration()
    integration.start()
    log.success("Integration started")
    
    log.subsection("Loading Modules")
    log.info("✓ Monitor Server")
    log.info("✓ Scanner Module")
    log.info("✓ Health Monitor")
    
    log.success("All modules loaded")
    return main_app

def main():
    """Entry point for pip install"""
    import argparse
    
    parser = argparse.ArgumentParser(description="System Monitor")
    parser.add_argument("--host", default="0.0.0.0", help="Host")
    parser.add_argument("--port", type=int, default=5000, help="Port")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    
    args = parser.parse_args()
    
    app = setup_app()
    
    log.section("STARTING SYSTEM MONITOR")
    
    log.table(
        ["Parameter", "Value"],
        [
            ["Host", args.host],
            ["Port", args.port],
            ["Debug", "Yes" if args.debug else "No"],
            ["URL", f"http://{args.host}:{args.port}"],
            ["Local", f"http://127.0.0.1:{args.port}"],
        ]
    )
    
    log.success("Server configuration ready")
    log.info("Starting server...")
    
    try:
        from src.c2.server import socketio
        socketio.run(app, host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        log.warning("\nServer stopped by user")
    except Exception as e:
        log.exception(f"Server error: {e}")

if __name__ == "__main__":
    main()
