#!/usr/bin/env python3
"""
System Monitor - Unified Launcher
"""
import os, sys, subprocess, threading, time, json, requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from flask import Flask
from src.c2.server import app as main_app
from src.c2.orchestrator import Integration
from src.utils.logger import get_logger

log = get_logger('launcher')

# Ngrok tunnel manager
class NgrokTunnel:
    def __init__(self, port=5000):
        self.port = port
        self.process = None
        self.public_url = None
        self.authtoken = os.getenv('NGROK_AUTHTOKEN', '')
        
    def start(self):
        """Start ngrok tunnel"""
        try:
            # Check if ngrok is installed
            result = subprocess.run(['which', 'ngrok'], capture_output=True)
            if result.returncode != 0:
                log.warning("ngrok not installed - skipping tunnel")
                return None
            
            # Kill existing ngrok processes
            subprocess.run(['pkill', '-9', '-f', 'ngrok'], capture_output=True)
            time.sleep(1)
            
            # Build ngrok command with authtoken if available
            ngrok_cmd = ['ngrok', 'http', str(self.port)]
            if self.authtoken:
                ngrok_cmd = ['ngrok', 'http', str(self.port), '--authtoken=' + self.authtoken]
            
            # Start ngrok
            self.process = subprocess.Popen(
                ngrok_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for ngrok to start
            time.sleep(3)
            
            # Get public URL from ngrok API
            try:
                response = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=5)
                data = response.json()
                if data.get('tunnels'):
                    self.public_url = data['tunnels'][0]['public_url']
                    log.success(f"Ngrok tunnel: {self.public_url}")
                    log.info(f"Login URL: {self.public_url}/login?pin=2409")
                    return self.public_url
            except Exception as e:
                log.warning(f"Could not get ngrok URL: {e}")
                
        except Exception as e:
            log.warning(f"Ngrok startup failed: {e}")
        
        return None
    
    def stop(self):
        """Stop ngrok tunnel"""
        if self.process:
            self.process.terminate()
            self.process = None
        subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)

ngrok_tunnel = None

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
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="Host")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")), help="Port")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--no-ngrok", action="store_true", help="Disable ngrok tunnel (enabled by default)")
    
    args = parser.parse_args()
    
    app = setup_app()
    
    # Start ngrok tunnel (enabled by default)
    global ngrok_tunnel
    tunnel_url = None
    if not args.no_ngrok:
        ngrok_tunnel = NgrokTunnel(args.port)
        tunnel_url = ngrok_tunnel.start()
    
    log.section("STARTING SYSTEM MONITOR")
    
    table_data = [
        ["Host", args.host],
        ["Port", args.port],
        ["Debug", "Yes" if args.debug else "No"],
        ["URL", f"http://{args.host}:{args.port}"],
        ["Local", f"http://127.0.0.1:{args.port}"],
    ]
    
    if tunnel_url:
        table_data.append(["Tunnel", tunnel_url])
        table_data.append(["Login", f"{tunnel_url}/login?pin=2409"])
    
    log.table(["Parameter", "Value"], table_data)
    
    log.success("Server configuration ready")
    log.info("Starting server...")
    
    try:
        from src.c2.server import socketio
        socketio.run(app, host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        log.warning("\nServer stopped by user")
        if ngrok_tunnel:
            ngrok_tunnel.stop()
    except Exception as e:
        log.exception(f"Server error: {e}")
        if ngrok_tunnel:
            ngrok_tunnel.stop()

if __name__ == "__main__":
    main()
