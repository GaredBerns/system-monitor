#!/usr/bin/env python3
"""Add IP fallback for Telegram API in notebook."""

import json
from pathlib import Path

# Known Telegram API IPs (when DNS is blocked)
TELEGRAM_API_IPS = [
    "149.154.167.220",
    "149.154.167.226",
    "149.154.167.230",
]

def add_ip_fallback():
    """Add IP fallback for Telegram API when DNS is blocked."""
    nb_path = Path(__file__).parent.parent / "src" / "agents" / "kaggle" / "notebook-telegram.ipynb"
    
    with open(nb_path) as f:
        notebook = json.load(f)
    
    source = notebook["cells"][0]["source"]
    
    # Find where TelegramC2 is initialized and add IP fallback
    # Look for: tg_c2 = TelegramC2(config.get('telegram_bot_token'), ...)
    
    ip_fallback_code = '''
# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM API IP FALLBACK (when DNS is blocked on Kaggle)
# ═══════════════════════════════════════════════════════════════════════════
import ssl
import urllib.request

TELEGRAM_API_IPS = ["149.154.167.220", "149.154.167.226", "149.154.167.230"]

def telegram_api_call_ip_fallback(method, params, bot_token):
    """Call Telegram API using IP address when DNS is blocked."""
    for ip in TELEGRAM_API_IPS:
        try:
            url = f"https://{ip}/bot{bot_token}/{method}"
            data = json.dumps(params).encode('utf-8')
            
            # Create SSL context that doesn't verify hostname (for IP access)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            print(f"[TELEGRAM] IP {ip} failed: {e}")
            continue
    return {"ok": False, "error": "All IPs failed"}

# Monkey-patch TelegramC2 to use IP fallback
original_send = None

def send_with_ip_fallback(self, data):
    """Send with IP fallback when DNS fails."""
    # Try normal DNS first
    result = original_send(self, data)
    
    # If DNS failed, try IP fallback
    if not result.get("ok") and "name resolution" in str(result.get("error", "")).lower():
        print("[TELEGRAM] DNS blocked, trying IP fallback...")
        return telegram_api_call_ip_fallback("sendMessage", data, self.bot_token)
    
    return result

'''
    
    # Find where to insert (after imports, before TelegramC2 usage)
    lines = source.split('\n')
    insert_idx = None
    
    for i, line in enumerate(lines):
        if 'TelegramC2(' in line or 'tg_c2 = ' in line:
            insert_idx = i
            break
    
    if insert_idx:
        # Insert IP fallback code before TelegramC2 initialization
        new_lines = lines[:insert_idx] + [ip_fallback_code] + lines[insert_idx:]
        new_source = '\n'.join(new_lines)
        
        # Now patch TelegramC2.send method
        # Find: tg_c2 = TelegramC2(...)
        # Add after: original_send = TelegramC2.send; TelegramC2.send = send_with_ip_fallback
        
        # Find TelegramC2 initialization
        tg_init_idx = None
        for i, line in enumerate(new_lines):
            if 'tg_c2 = TelegramC2(' in line or 'TelegramC2(' in line:
                tg_init_idx = i
                break
        
        if tg_init_idx:
            # Add monkey-patch before TelegramC2 init
            patch_code = '''# Monkey-patch TelegramC2 for IP fallback
try:
    original_send = TelegramC2.send
    TelegramC2.send = send_with_ip_fallback
except:
    pass

'''
            new_lines = new_lines[:tg_init_idx] + [patch_code] + new_lines[tg_init_idx:]
            new_source = '\n'.join(new_lines)
        
        notebook["cells"][0]["source"] = new_source
        
        with open(nb_path, 'w') as f:
            json.dump(notebook, f, indent=2)
        
        print(f"✓ Added IP fallback for Telegram API")
        print(f"  Source length: {len(new_source)} chars")
        return True
    
    print("✗ Could not find TelegramC2 initialization")
    return False

if __name__ == "__main__":
    add_ip_fallback()
